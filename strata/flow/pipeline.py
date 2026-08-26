"""
strata.flow.pipeline
====================
The pipeline, plus the two capabilities that follow from treating the ledger
as canonical.

    Pipeline   bytes -> ledger -> triage -> read -> map -> outlets
    Auditor    proves reconstruction is byte-exact, continuously
    Rewind     re-derives history from the ledger after a grammar changes

BATCHED, NOT ONE AT A TIME

Events arrive in batches and stay in batches through every stage. In Python
the per-call overhead of a function is a real fraction of the work when the
work is small, so processing 512 lines through one loop instead of 512 loops
through one line is worth a measurable amount. It also lets the ledger
amortise one fsync across the whole batch rather than paying per record.

ORDER OF OPERATIONS, WHICH IS NOT NEGOTIABLE

Bytes go to the ledger FIRST, before anything can fail. If we parsed first and
crashed, we would lose the evidence of what crashed us -- and the line that
crashes a parser is exactly the line an investigator most wants to see.

REWIND IS ~60 LINES

That is the whole argument for the architecture. Because the ledger was never
a backup, correcting three months of history is a loop, not a data-recovery
project.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, Iterator

from ..core.model import (Channel, Envelope, Event, Extraction, Outcome,
                          Record, Rejection, Verdict)
from ..io.outlets import Outlet
from ..mapping.ocsf import Mapper, validate
from ..parse.compiler import CompiledGrammar, compile_all
from ..parse.extractors import ExtractError
from ..parse.grammar import Library
from ..parse.shapes import fingerprint
from ..parse.triage import Triage
from ..store.ledger import Ledger

DEFAULT_BATCH = 512


@dataclass(slots=True)
class Metrics:
    received: int = 0
    stored: int = 0
    mapped: int = 0
    rejected: int = 0
    bytes_in: int = 0
    by_grammar: dict[str, int] = field(default_factory=dict)
    by_verdict: dict[str, int] = field(default_factory=dict)
    started: float = field(default_factory=time.perf_counter)
    _last_report: float = field(default=0.0)

    @property
    def elapsed(self) -> float:
        return max(time.perf_counter() - self.started, 1e-9)

    @property
    def eps(self) -> float:
        return self.received / self.elapsed

    @property
    def map_rate(self) -> float:
        return self.mapped / self.received if self.received else 0.0

    def snapshot(self) -> dict:
        return {
            "received": self.received,
            "stored": self.stored,
            "mapped": self.mapped,
            "rejected": self.rejected,
            "bytes_in": self.bytes_in,
            "eps": round(self.eps, 1),
            "map_rate": round(self.map_rate, 4),
            "elapsed_s": round(self.elapsed, 2),
            "by_grammar": dict(sorted(self.by_grammar.items(), key=lambda kv: -kv[1])),
            "by_verdict": dict(self.by_verdict),
        }


class Pipeline:
    """Ingest -> preserve -> triage -> read -> map -> emit."""

    def __init__(
        self,
        ledger: Ledger,
        library: Library,
        outlets: list[Outlet] | None = None,
        floor: float = 0.70,
        batch_size: int = DEFAULT_BATCH,
    ) -> None:
        self.ledger = ledger
        self.library = library
        self.outlets = outlets or []
        self.batch_size = batch_size
        self.floor = floor
        self.mapper = Mapper()
        self.metrics = Metrics()
        self.rejects: list[Rejection] = []
        self._reject_cap = 5000
        self.compile_errors: dict[str, str] = {}
        self._library_generation = -1
        self.triage: Triage = Triage([], floor)
        self.refresh()

    # ------------------------------------------------------------ grammar set

    def refresh(self) -> dict[str, str]:
        """Recompile from the library. Called on start and after a publish.

        This is requirement (e) at runtime: a grammar file appears, this runs,
        and the new source begins parsing. No restart.
        """
        compiled, errors = compile_all(self.library.all())
        self.triage = Triage(compiled, self.floor)
        self.compile_errors = errors
        self._library_generation = self.library.generation
        return errors

    @property
    def grammars(self) -> list[CompiledGrammar]:
        return self.triage._all

    # ---------------------------------------------------------------- process

    def submit(self, payload: bytes, envelope: Envelope | None = None,
               generation: int = 0, store: bool = True) -> Event | Rejection:
        """One line, end to end."""
        out = self.submit_batch([(payload, envelope or Envelope())],
                                generation=generation, store=store)
        return out.events[0] if out.events else out.rejects[0]

    def submit_batch(self, items: list[tuple[bytes, Envelope]],
                     generation: int = 0, store: bool = True) -> Outcome:
        """A batch of lines, end to end. The hot path."""
        outcome = Outcome()
        m = self.metrics

        # --- 1. PRESERVE. Before anything can fail. ------------------------
        if store:
            records = self.ledger.extend(items)
        else:
            from ..core.model import digest
            records = [Record(p, e, digest(p)) for p, e in items]
        m.stored += len(records) if store else 0

        for record in records:
            m.received += 1
            m.bytes_in += len(record.payload)

            line = record.payload.decode("utf-8", "replace").rstrip("\r\n")
            if not line:
                self._reject(outcome, record, Verdict.UNCLAIMED, "empty line")
                continue

            # --- 2. TRIAGE ------------------------------------------------
            fp = fingerprint(line)
            decision = self.triage.decide(line, fp)

            if decision.grammar is None:
                self._reject(outcome, record, Verdict.UNCLAIMED,
                             f"no grammar claims a {fp.shape.label} line")
                continue
            if decision.confidence < self.floor:
                self._reject(outcome, record, Verdict.AMBIGUOUS,
                             f"confidence {decision.confidence} below floor {self.floor}"
                             + (f"; runner-up {decision.runner_up}" if decision.runner_up else ""),
                             decision.grammar.id, decision.confidence)
                continue

            grammar = decision.grammar

            # --- 3. READ --------------------------------------------------
            try:
                fields, notes = grammar.read(line)
            except ExtractError as exc:
                self._reject(outcome, record, Verdict.EXTRACT_FAILED, str(exc)[:200],
                             grammar.id, decision.confidence)
                continue
            except Exception as exc:
                # A grammar must never be able to kill the pipeline. Users
                # write these; a bad regex is a quarantine, not an outage.
                self._reject(outcome, record, Verdict.EXTRACT_FAILED,
                             f"{type(exc).__name__}: {exc}"[:200],
                             grammar.id, decision.confidence)
                continue

            if not fields:
                self._reject(outcome, record, Verdict.EXTRACT_FAILED,
                             "pipeline produced no fields", grammar.id,
                             decision.confidence)
                continue

            extraction = Extraction(
                grammar_id=grammar.id, grammar_version=grammar.version,
                fields=fields, confidence=decision.confidence,
                event_ns=grammar.event_time(fields), notes=notes)

            # --- 4. MAP ---------------------------------------------------
            event = self.mapper.build(extraction, grammar, record.envelope,
                                      record.id, record.stratum, generation)

            problems = validate(event.ocsf)
            if problems:
                self._reject(outcome, record, Verdict.INVALID, "; ".join(problems)[:200],
                             grammar.id, decision.confidence)
                continue

            outcome.events.append(event)
            m.mapped += 1
            m.by_grammar[grammar.id] = m.by_grammar.get(grammar.id, 0) + 1

        # --- 5. EMIT -----------------------------------------------------
        if outcome.events:
            for outlet in self.outlets:
                outlet.write_many(outcome.events)

        return outcome

    def _reject(self, outcome: Outcome, record: Record, verdict: Verdict,
                detail: str, guess: str | None = None, conf: float = 0.0) -> None:
        r = Rejection(record.id, verdict, detail, guess, conf)
        outcome.rejects.append(r)
        self.rejects.append(r)
        if len(self.rejects) > self._reject_cap:
            del self.rejects[:len(self.rejects) - self._reject_cap]
        self.metrics.rejected += 1
        key = verdict.label
        self.metrics.by_verdict[key] = self.metrics.by_verdict.get(key, 0) + 1

    # ------------------------------------------------------------- streaming

    def run(self, source: Iterable[bytes], envelope: Envelope | None = None,
            limit: int = 0) -> Iterator[Outcome]:
        """Consume an iterable of raw lines, yielding one Outcome per batch."""
        env = envelope or Envelope()
        batch: list[tuple[bytes, Envelope]] = []
        seen = 0

        for payload in source:
            if not payload.strip():
                continue
            batch.append((payload, env))
            seen += 1
            if len(batch) >= self.batch_size:
                yield self.submit_batch(batch)
                batch = []
            if limit and seen >= limit:
                break

        if batch:
            yield self.submit_batch(batch)

    def drain(self, source: Iterable[bytes], envelope: Envelope | None = None,
              limit: int = 0) -> Metrics:
        """Consume everything, discard the per-batch results, return metrics.
        What the CLI wants when it is ingesting a file."""
        for _ in self.run(source, envelope, limit):
            pass
        self.flush()
        return self.metrics

    def rejected_samples(self, limit: int = 200) -> list[str]:
        """Raw text of rejected lines -- the Forge's input queue. What is
        quarantined today becomes a grammar tomorrow."""
        out = []
        for r in self.rejects[-limit:]:
            rec = self.ledger.get(r.record_id)
            if rec:
                out.append(rec.text())
        return out

    def flush(self) -> None:
        for outlet in self.outlets:
            outlet.flush()

    def close(self) -> None:
        for outlet in self.outlets:
            outlet.close()


# ---------------------------------------------------------------------------
# Requirement (a), proven continuously
# ---------------------------------------------------------------------------

class Auditor:
    """Independent verifier of the ledger.

    Runs against the ledger directly rather than through the pipeline, so it
    cannot be fooled by the thing it audits. This is what turns "lossless"
    from a bullet point into a number somebody can watch move.
    """

    __slots__ = ("ledger",)

    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger

    def run(self, sample: int | None = None) -> dict:
        report = self.ledger.audit(sample=sample)
        report["verdict"] = "intact" if report["ok"] else "COMPROMISED"
        return report

    def spot_check(self, record_ids: list[bytes]) -> dict:
        """Reconstruct specific records and byte-compare. Used by the UI to
        show that the record on screen really is the one on disk."""
        from ..core.model import digest
        ok = bad = 0
        for rid in record_ids:
            payload = self.ledger.raw(rid)
            if payload is not None and digest(payload) == rid:
                ok += 1
            else:
                bad += 1
        return {"checked": ok + bad, "exact": ok, "failed": bad,
                "fidelity": ok / (ok + bad) if (ok + bad) else 1.0}


# ---------------------------------------------------------------------------
# Requirement (a) + (d) + (i): fix the grammar, fix the past
# ---------------------------------------------------------------------------

class Rewind:
    """Re-derives events from the ledger under the current grammar set.

    Idempotent by construction: record ids are content addresses, so rewinding
    the same range twice produces the same events. `generation` increments so
    a downstream consumer can distinguish v1 output from v2 and keep or drop
    either.
    """

    __slots__ = ("pipeline",)

    def __init__(self, pipeline: Pipeline) -> None:
        self.pipeline = pipeline

    def run(self, generation: int = 1, limit: int | None = None,
            stratum: int | None = None, dry_run: bool = True) -> dict:
        pipe = self.pipeline
        saved_outlets = pipe.outlets
        saved_metrics = pipe.metrics
        saved_rejects = pipe.rejects

        if dry_run:
            pipe.outlets = []            # derive and compare, emit nothing
        pipe.metrics = Metrics()
        pipe.rejects = []

        processed = 0
        batch: list[tuple[bytes, Envelope]] = []
        changed: list[dict] = []

        try:
            for record in pipe.ledger.scan(stratum=stratum):
                env = Envelope(channel=Channel.REPLAY, peer=record.envelope.peer,
                               listener="rewind",
                               received_ns=record.envelope.received_ns,
                               truncated=record.envelope.truncated)
                batch.append((record.payload, env))
                processed += 1

                if len(batch) >= pipe.batch_size:
                    out = pipe.submit_batch(batch, generation=generation, store=False)
                    _sample(out, changed)
                    batch = []
                if limit and processed >= limit:
                    break

            if batch:
                out = pipe.submit_batch(batch, generation=generation, store=False)
                _sample(out, changed)

            result = {
                "generation": generation,
                "dry_run": dry_run,
                "records": processed,
                "remapped": pipe.metrics.mapped,
                "still_rejected": pipe.metrics.rejected,
                "by_grammar": dict(pipe.metrics.by_grammar),
                "sample": changed[:20],
            }
        finally:
            pipe.outlets = saved_outlets
            pipe.metrics = saved_metrics
            pipe.rejects = saved_rejects

        return result


def _sample(outcome: Outcome, into: list[dict]) -> None:
    for ev in outcome.events[:2]:
        if len(into) < 20:
            into.append({
                "record": ev.provenance.record_id.hex()[:16],
                "grammar": ev.provenance.grammar_id,
                "version": ev.provenance.grammar_version,
                "coverage": round(ev.provenance.coverage, 3),
            })
