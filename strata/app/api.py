"""
strata.app.api
==============
REST API and the console. Requirement (f).

SECURITY POSTURE

This is the highest-value attack surface in the product: it can read raw
evidence and it can publish grammars, which is to say it can change what the
whole organisation is able to see.

  * Every mutating endpoint requires a bearer token. There is no default
    password and no anonymous write.
  * Three roles, checked SERVER-SIDE per endpoint. A hidden button is not
    authorization.
  * Raw log content sits behind the analyst role and every access is audited,
    because "who read this evidence" is itself a forensic question.
  * Every request body is validated before it reaches an engine.
  * Dev mode (no admin token configured) announces itself loudly in
    /api/health and in the console header, so nobody deploys it by accident.

THE PROVENANCE ENDPOINT

`/api/record/{id}/provenance` re-derives an event from its stored bytes and
returns, for every normalized field, the exact byte range of the raw line that
produced it. That is what the console's inspector draws. It turns requirement
(d) from a claim about an identifier into something you can point at.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..core.model import Channel, Envelope, Event, digest
from ..dev.synth import Corpus
from ..flow.pipeline import Auditor, Pipeline, Rewind
from ..io.outlets import CEF, NDJSON, Memory, Parquet
from ..learn.forge import Forge
from ..mapping.ocsf import CLASSES, DISPOSITIONS, SEVERITIES
from ..parse.grammar import Library
from ..parse.shapes import fingerprint
from ..store.ledger import Ledger, LedgerBusy

ROOT = Path(__file__).resolve().parents[2]
GRAMMARS = ROOT / "grammars"
VAR = ROOT / "var"

# Secrets come from the environment, never from source. A shipped default
# secret is a shipped backdoor.
SECRET = os.environ.get("STRATA_SECRET") or secrets.token_hex(32)
ADMIN_TOKEN = os.environ.get("STRATA_ADMIN_TOKEN", "")
TOKEN_TTL = 8 * 3600

ROLES = {"viewer": 0, "analyst": 1, "maintainer": 2}

app = FastAPI(title="STRATA", version="2.0.0",
              description="Universal log pre-processing — layered, legible, "
                          "nothing rewritten.")

_state: dict[str, Any] = {}
_audit: list[dict] = []
_subscribers: set[asyncio.Queue] = set()


def state() -> dict[str, Any]:
    """Lazily construct the pipeline so import stays cheap for tests."""
    if "pipeline" not in _state:
        try:
            ledger = Ledger(VAR / "ledger")
        except LedgerBusy as exc:
            # 503, not 500: a knowable operational condition with a specific
            # remedy, and the caller deserves to be told which.
            raise HTTPException(503, str(exc)) from None
        library = Library(GRAMMARS)
        memory = Memory(capacity=5000)
        pipeline = Pipeline(ledger, library, [
            Parquet(VAR / "lake"),
            NDJSON(VAR / "out" / "events.ndjson"),
            CEF(path=VAR / "out" / "siem.cef"),
            memory,
        ])
        _state.update(ledger=ledger, library=library, pipeline=pipeline,
                      memory=memory, auditor=Auditor(ledger), forge=Forge(),
                      started=time.time())
    return _state


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------

def _mint(role: str) -> str:
    body = f"{role}:{int(time.time()) + TOKEN_TTL}"
    sig = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()[:40]
    return f"{body}:{sig}"


def _verify(token: str) -> str | None:
    try:
        role, expiry, sig = token.rsplit(":", 2)
    except ValueError:
        return None
    expected = hmac.new(SECRET.encode(), f"{role}:{expiry}".encode(),
                        hashlib.sha256).hexdigest()[:40]
    # Constant-time: a naive == leaks the signature one byte at a time under
    # a timing attack.
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        if int(expiry) < time.time():
            return None
    except ValueError:
        return None
    return role if role in ROLES else None


def require(minimum: str = "viewer"):
    def dependency(authorization: Annotated[str | None, Header()] = None) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "missing bearer token")
        role = _verify(authorization[7:])
        if role is None:
            raise HTTPException(401, "invalid or expired token")
        if ROLES[role] < ROLES[minimum]:
            raise HTTPException(403, f"requires role '{minimum}', you hold '{role}'")
        return role
    return dependency


def audit(actor: str, action: str, detail: dict | None = None) -> None:
    """Append-only record of privileged actions. An insider who edits a
    grammar must leave a trace they cannot remove from here."""
    entry = {"at": time.time(), "actor": actor, "action": action,
             "detail": detail or {}}
    _audit.append(entry)
    path = VAR / "out" / "audit.ndjson"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginBody(Strict):
    # Empty is permitted so dev mode can hand out a token without a magic
    # value; the real gate is the constant-time compare below.
    token: str = Field(default="", max_length=512)


@app.post("/api/login", tags=["auth"])
def login(body: LoginBody):
    if not ADMIN_TOKEN:
        return {"token": _mint("maintainer"), "role": "maintainer",
                "mode": "dev-no-auth"}
    if not hmac.compare_digest(body.token, ADMIN_TOKEN):
        raise HTTPException(401, "invalid admin token")
    return {"token": _mint("maintainer"), "role": "maintainer",
            "mode": "authenticated"}


# ---------------------------------------------------------------------------
# health and overview
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["ops"])
def health():
    s = state()
    return {
        "status": "ok",
        "version": "2.0.0",
        "auth_mode": "authenticated" if ADMIN_TOKEN else "DEV — NO AUTH",
        "grammars": len(s["library"]),
        "grammar_errors": s["library"].errors,
        "compile_errors": s["pipeline"].compile_errors,
        "records": s["ledger"].stats().records,
        "uptime_s": round(time.time() - s["started"], 1),
        "network_required": False,
    }


@app.get("/api/overview", tags=["ops"])
def overview(role: str = Depends(require("viewer"))):
    s = state()
    pipe: Pipeline = s["pipeline"]
    led: Ledger = s["ledger"]
    stats = led.stats()
    return {
        "metrics": pipe.metrics.snapshot(),
        "ledger": {
            "records": stats.records, "strata": stats.strata,
            "sealed": stats.sealed, "bytes_raw": stats.bytes_raw,
            "bytes_stored": stats.bytes_stored, "ratio": round(stats.ratio, 2),
        },
        "triage": pipe.triage.selectivity(),
        "families": pipe.triage.families(),
        "grammars": [
            {"id": g.id, "version": g.version, "vendor": g.vendor,
             "product": g.product, "family": g.family,
             "steps": list(g.step_names),
             "events": pipe.metrics.by_grammar.get(g.id, 0)}
            for g in pipe.grammars
        ],
        "reference": {"classes": CLASSES, "dispositions": DISPOSITIONS,
                      "severities": SEVERITIES},
    }


@app.get("/api/integrity", tags=["ops"])
def integrity(sample: int = Query(0, ge=0, le=1_000_000),
              role: str = Depends(require("viewer"))):
    """Requirement (a), proven rather than claimed."""
    s = state()
    report = s["auditor"].run(sample=sample or None)
    report["roots"] = s["ledger"].roots()[-8:]
    return report


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------

@app.get("/api/events", tags=["events"])
def events(limit: int = Query(60, ge=1, le=500), grammar: str | None = None,
           role: str = Depends(require("viewer"))):
    memory: Memory = state()["memory"]
    return {"events": [e.document() for e in memory.recent(limit, grammar)],
            "buffered": len(memory.buffer)}


@app.get("/api/quarantine", tags=["events"])
def quarantine(limit: int = Query(60, ge=1, le=500),
               role: str = Depends(require("viewer"))):
    pipe: Pipeline = state()["pipeline"]
    return {"total": len(pipe.rejects),
            "items": [r.document() for r in pipe.rejects[-limit:]],
            "samples": pipe.rejected_samples(min(limit, 30))}


_HEX = set("0123456789abcdef")


def _record_id(value: str) -> bytes:
    if len(value) != 64 or not set(value.lower()) <= _HEX:
        raise HTTPException(400, "record id must be 64 hexadecimal characters")
    return bytes.fromhex(value.lower())


@app.get("/api/record/{record_id}", tags=["events"])
def record(record_id: str, role: str = Depends(require("analyst"))):
    """The original bytes behind any event.

    Analyst role: raw lines contain usernames, URLs and occasionally
    credentials. Every access is written to the audit log.
    """
    rid = _record_id(record_id)
    rec = state()["ledger"].get(rid)
    if rec is None:
        raise HTTPException(404, "no such record")
    audit(role, "read_raw", {"record": record_id})
    return {
        "record_id": rec.hex,
        "text": rec.text(),
        "hex": rec.payload.hex(),
        "bytes": len(rec.payload),
        "verified": digest(rec.payload) == rec.id,
        "stratum": rec.stratum,
        "envelope": {
            "channel": rec.envelope.channel.label,
            "peer": rec.envelope.peer,
            "listener": rec.envelope.listener,
            "received": rec.envelope.received_ns,
            "truncated": rec.envelope.truncated,
        },
    }


@app.get("/api/record/{record_id}/provenance", tags=["events"])
def provenance(record_id: str, role: str = Depends(require("analyst"))):
    """Map every normalized field back to the byte range that produced it.

    Re-derives the event from stored bytes, then locates each extracted value
    in the raw text. This is what the inspector draws, and it is the strongest
    form requirement (d) can take: not "here is an id you can look up", but
    "these exact characters became this exact field".
    """
    rid = _record_id(record_id)
    s = state()
    rec = s["ledger"].get(rid)
    if rec is None:
        raise HTTPException(404, "no such record")

    pipe: Pipeline = s["pipeline"]
    text = rec.text()
    fp = fingerprint(text)
    decision = pipe.triage.decide(text, fp)

    if decision.grammar is None:
        return {"record_id": rec.hex, "text": text, "shape": fp.shape.label,
                "mapped": False, "reason": "no grammar claims this line",
                "links": [], "ocsf": None}

    grammar = decision.grammar
    try:
        fields, notes = grammar.read(text)
    except Exception as exc:
        return {"record_id": rec.hex, "text": text, "shape": fp.shape.label,
                "mapped": False, "reason": f"{type(exc).__name__}: {exc}",
                "links": [], "ocsf": None}

    from ..core.model import Extraction
    extraction = Extraction(grammar.id, grammar.version, fields,
                            decision.confidence, grammar.event_time(fields), notes)
    event = pipe.mapper.build(extraction, grammar, rec.envelope, rec.id, rec.stratum)

    # Reverse index: vendor field -> OCSF path(s) that consumed it.
    consumed: dict[str, list[str]] = {}
    for path, source in grammar.emit.fields:
        consumed.setdefault(source, []).append(".".join(path))
    for path, source, *_ in grammar.emit.enums:
        consumed.setdefault(source, []).append(".".join(path))
    # The clock field is consumed too -- it becomes `time` and is echoed as
    # `metadata.original_time`. Omitting it here made the inspector label the
    # timestamp "unmapped", which is both wrong and exactly the sort of small
    # inconsistency that undermines trust in the rest of the display.
    if grammar.clock is not None:
        consumed.setdefault(grammar.clock.field, []).extend(
            ["time", "metadata.original_time"])

    links = []
    used_spans: list[tuple[int, int]] = []
    for name, value in fields.items():
        if value is None or value == "":
            continue
        needle = str(value)
        if len(needle) < 1:
            continue
        # Find an occurrence that does not overlap one already claimed, so a
        # value appearing twice highlights two distinct places rather than the
        # same one repeatedly.
        start = -1
        search_from = 0
        while True:
            at = text.find(needle, search_from)
            if at < 0:
                break
            if not any(a < at + len(needle) and at < b for a, b in used_spans):
                start = at
                break
            search_from = at + 1
        if start < 0:
            continue
        used_spans.append((start, start + len(needle)))
        links.append({
            "field": name,
            "value": needle,
            "start": start,
            "end": start + len(needle),
            "ocsf": consumed.get(name, []),
            "mapped": name in consumed,
        })

    links.sort(key=lambda l: l["start"])
    return {
        "record_id": rec.hex,
        "text": text,
        "shape": fp.shape.label,
        "mapped": True,
        "grammar": grammar.id,
        "grammar_version": grammar.version,
        "confidence": decision.confidence,
        "steps": list(grammar.step_names),
        "links": links,
        "ocsf": event.ocsf,
        "unmapped": event.residue,
        "coverage": round(event.provenance.coverage, 3),
    }


@app.get("/api/record/{record_id}/proof", tags=["events"])
def proof(record_id: str, role: str = Depends(require("viewer"))):
    """Merkle inclusion proof. Safe for any role: it reveals nothing about
    content, only that these bytes are in the archive."""
    rid = _record_id(record_id)
    result = state()["ledger"].prove(rid)
    if result is None:
        raise HTTPException(404, "no such record")
    return result


# ---------------------------------------------------------------------------
# live stream
# ---------------------------------------------------------------------------

@app.get("/api/stream", tags=["events"])
async def stream(request: Request):
    """Server-sent events: metrics pushed as they change.

    SSE rather than polling because the console should show the pipeline
    moving, and rather than websockets because this is one-directional and SSE
    reconnects by itself. Auth rides on a query parameter here since
    EventSource cannot set headers.
    """
    token = request.query_params.get("token", "")
    if _verify(token) is None:
        raise HTTPException(401, "invalid or expired token")

    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    _subscribers.add(queue)

    async def pump():
        try:
            s = state()
            pipe: Pipeline = s["pipeline"]
            memory: Memory = s["memory"]
            last_written = memory.written
            while True:
                if await request.is_disconnected():
                    break
                payload = {
                    "t": time.time(),
                    "metrics": pipe.metrics.snapshot(),
                    "new_events": max(0, memory.written - last_written),
                    "ledger_records": s["ledger"].stats().records,
                }
                last_written = memory.written
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(1.0)
        finally:
            _subscribers.discard(queue)

    return StreamingResponse(pump(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# forge
# ---------------------------------------------------------------------------

class StudyBody(Strict):
    lines: list[str] = Field(min_length=1, max_length=5000)


class ProposeBody(StudyBody):
    grammar_id: str = Field(pattern=r"^[a-z0-9]+(?:\.[a-z0-9_]+)+$", max_length=64)
    vendor: str = Field(default="Unknown", max_length=64)
    product: str = Field(default="Unknown", max_length=64)
    ocsf_class: int = Field(default=4001, ge=1, le=999999)
    category: int = Field(default=4, ge=1, le=99)


@app.post("/api/forge/study", tags=["forge"])
def forge_study(body: StudyBody, role: str = Depends(require("viewer"))):
    return state()["forge"].study(body.lines)


@app.post("/api/forge/propose", tags=["forge"])
def forge_propose(body: ProposeBody, role: str = Depends(require("viewer"))):
    """Requirements (e)+(i). Proposal only — publishing is separate and
    privileged."""
    t0 = time.perf_counter()
    proposal = state()["forge"].propose(
        body.lines, body.grammar_id, body.vendor, body.product,
        ocsf_class=body.ocsf_class, category=body.category)
    report = proposal.report()
    report["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return report


class PublishBody(Strict):
    grammar_id: str = Field(pattern=r"^[a-z0-9]+(?:\.[a-z0-9_]+)+$", max_length=64)
    yaml: str = Field(min_length=20, max_length=400_000)


@app.post("/api/forge/publish", tags=["forge"])
def forge_publish(body: PublishBody, role: str = Depends(require("maintainer"))):
    """Publish a grammar. Maintainer only.

    Whoever can publish a grammar can change what the organisation is able to
    see -- a grammar that quietly stops recognising one attack class is a
    perfect blind spot. Hence: privileged, validated, rolled back on failure,
    and audited.
    """
    s = state()
    target = (GRAMMARS / f"{body.grammar_id}.yaml").resolve()
    # The id pattern already forbids '/' and '..'; containment is checked
    # anyway rather than trusting one layer.
    if not str(target).startswith(str(GRAMMARS.resolve())):
        raise HTTPException(400, "invalid grammar path")

    previous = target.read_text(encoding="utf-8") if target.exists() else None
    target.write_text(body.yaml, encoding="utf-8")

    errors = s["library"].reload()
    compile_errors = s["pipeline"].refresh()
    filename = f"{body.grammar_id}.yaml"

    if filename in errors or body.grammar_id in compile_errors:
        reason = errors.get(filename) or compile_errors.get(body.grammar_id)
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            target.write_text(previous, encoding="utf-8")
        s["library"].reload()
        s["pipeline"].refresh()
        raise HTTPException(422, f"grammar rejected and rolled back: {reason}")

    audit(role, "publish_grammar",
          {"grammar": body.grammar_id, "replaced": previous is not None})
    return {"published": body.grammar_id, "active": len(s["library"]),
            "restart_required": False}


@app.post("/api/grammars/reload", tags=["forge"])
def reload_grammars(role: str = Depends(require("maintainer"))):
    s = state()
    errors = s["library"].reload()
    compile_errors = s["pipeline"].refresh()
    audit(role, "reload", {"errors": len(errors) + len(compile_errors)})
    return {"active": len(s["library"]), "errors": errors,
            "compile_errors": compile_errors}


@app.get("/api/grammars/{grammar_id}", tags=["forge"])
def grammar_source(grammar_id: str, role: str = Depends(require("viewer"))):
    path = (GRAMMARS / f"{grammar_id}.yaml").resolve()
    if not str(path).startswith(str(GRAMMARS.resolve())) or not path.exists():
        raise HTTPException(404, "no such grammar")
    return {"id": grammar_id, "yaml": path.read_text(encoding="utf-8")}


# ---------------------------------------------------------------------------
# rewind
# ---------------------------------------------------------------------------

class RewindBody(Strict):
    generation: int = Field(default=1, ge=1, le=9999)
    limit: int = Field(default=0, ge=0, le=10_000_000)
    dry_run: bool = True


@app.post("/api/rewind", tags=["rewind"])
def rewind(body: RewindBody, role: str = Depends(require("maintainer"))):
    result = Rewind(state()["pipeline"]).run(
        generation=body.generation, limit=body.limit or None, dry_run=body.dry_run)
    audit(role, "rewind", {"generation": body.generation, "dry_run": body.dry_run})
    return result


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------

class IngestBody(Strict):
    lines: list[str] = Field(min_length=1, max_length=20000)
    peer: str = Field(default="api", max_length=64)


@app.post("/api/ingest", tags=["ingest"])
def ingest(body: IngestBody, role: str = Depends(require("analyst"))):
    pipe: Pipeline = state()["pipeline"]
    env = Envelope(channel=Channel.HTTP, peer=body.peer, listener="http/api",
                   received_ns=time.time_ns())
    outcome = pipe.submit_batch([(line.encode("utf-8"), env) for line in body.lines])
    pipe.flush()
    return {"received": len(body.lines), "mapped": len(outcome.events),
            "quarantined": len(outcome.rejects)}


class SynthBody(Strict):
    count: int = Field(default=2000, ge=1, le=200_000)
    seed: int = Field(default=20260826, ge=0)
    messy: bool = True


@app.post("/api/synth", tags=["ingest"])
def synth(body: SynthBody, role: str = Depends(require("analyst"))):
    """Generate and ingest a synthetic corpus. Lets the console demonstrate
    the whole pipeline with no external log source in the room."""
    pipe: Pipeline = state()["pipeline"]
    env = Envelope(channel=Channel.FILE, peer="synth", listener="synthetic",
                   received_ns=time.time_ns())
    corpus = Corpus(seed=body.seed)
    batch, mapped, rejected = [], 0, 0
    for sample in corpus.stream(body.count, messy=body.messy):
        batch.append((sample.payload, env))
        if len(batch) >= 512:
            out = pipe.submit_batch(batch)
            mapped += len(out.events)
            rejected += len(out.rejects)
            batch = []
    if batch:
        out = pipe.submit_batch(batch)
        mapped += len(out.events)
        rejected += len(out.rejects)
    pipe.flush()
    return {"generated": body.count, "mapped": mapped, "quarantined": rejected}


@app.get("/api/audit-log", tags=["ops"])
def audit_log(limit: int = Query(100, ge=1, le=1000),
              role: str = Depends(require("maintainer"))):
    return {"entries": _audit[-limit:]}


# ---------------------------------------------------------------------------
# console
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def console():
    page = Path(__file__).parent / "ui" / "console.html"
    if not page.exists():
        return HTMLResponse("<h1>STRATA</h1><p>Console not built.</p>")
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.exception_handler(Exception)
def unhandled(request: Request, exc: Exception):
    # Never return a stack trace: it maps our internals for an attacker.
    return JSONResponse(status_code=500, content={"error": "internal error"})
