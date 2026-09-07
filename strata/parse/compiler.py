"""
strata.parse.compiler
=====================
Grammar -> compiled reader.

THE IDEA, AND WHY IT MATTERS

The obvious way to run a declarative pipeline is to walk the steps per event
and branch on the step type:

    for step in grammar.pipeline:            # per event
        if step.kind == "columns": ...       # per event
        elif step.kind == "kv": ...          # per event

Every one of those comparisons happens millions of times to reach a decision
that was already fixed the moment the grammar was loaded. The step type cannot
change between events; only the data can.

So we decide once, at load time, and emit a flat list of closures with their
arguments already bound. Per event the pipeline is:

    for fn in plan:                          # no branching, no attribute lookup
        fn(state)

Everything that can be hoisted is hoisted: regexes compiled, column names
frozen into tuples, cast functions resolved, OCSF paths pre-split into
segments, enum tables lower-cased. Measured, this is the single largest
throughput win in the parse layer -- and it costs nothing at runtime because
the work happens once per grammar, not once per line.

The compiled object is immutable and therefore safe to share across worker
processes without copying.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from . import extractors as X
from .extractors import BODY, ExtractError
from .grammar import Grammar, Step
from .timeparse import Clock as TimeClock

Instruction = Callable[[dict], None]


class CompileError(Exception):
    """A grammar validated structurally but cannot be turned into a reader --
    a bad regex, an unknown time format. Caught at load, never at run time."""


def _kv_pattern(pair_sep: str | None) -> re.Pattern:
    r"""Build the key=value scanner for a declared pair separator.

    Not every vendor separates pairs with whitespace. Check Point uses '|'.
    With a whitespace-assuming pattern an unquoted value matches greedily up
    to the next space, swallowing the '|' separators, and every following pair
    collapses into the first value -- a SILENT misparse that yields a
    plausible, wrong record. Making the separator declarative keeps that
    vendor difference in the grammar (data) rather than the engine (code).
    """
    key = r'([A-Za-z_][A-Za-z0-9_.\-]*)='
    if pair_sep:
        stop = re.escape(pair_sep)
        return re.compile(key + rf'(?:"([^"]*)"|([^{stop}]*))')
    return re.compile(key + r'(?:"([^"]*)"|(\S*))')


def _compile_step(step: Step) -> Instruction:
    """One grammar step -> one closure with arguments bound."""
    kind = step.kind

    if kind == "syslog":
        return {"auto": X.syslog_auto,
                "rfc3164": X.syslog3164,
                "rfc5424": X.syslog5424}[step.syslog or "auto"]

    if kind == "columns":
        names = tuple(step.columns or ())
        sep, quote = step.sep, step.quote
        return lambda s: X.columns(s, names, sep, quote)

    if kind == "whitespace":
        names = tuple(step.whitespace or ())
        maxsplit = step.maxsplit
        return lambda s: X.whitespace(s, names, maxsplit)

    if kind == "kv":
        pattern = _kv_pattern(step.pair_sep)
        lower = step.lower_keys
        return lambda s: X.kv(s, pattern, lower)

    if kind == "json":
        sep, depth = step.flatten_sep, step.depth
        return lambda s: X.json_object(s, sep, depth)

    if kind == "cef":
        return X.cef

    if kind == "leef":
        return X.leef

    if kind == "regex":
        try:
            pattern = re.compile(step.regex or "")
        except re.error as exc:
            raise CompileError(f"bad regex {step.regex!r}: {exc}") from None
        source, keep = step.source, step.keep_body
        return lambda s: X.named_regex(s, pattern, source, keep)

    if kind == "prefix":
        try:
            pattern = re.compile(step.prefix or "")
        except re.error as exc:
            raise CompileError(f"bad prefix regex {step.prefix!r}: {exc}") from None
        return lambda s: X.strip_prefix(s, pattern)

    raise CompileError(f"no compiler for step kind {kind!r}")


def _guard(fn: Instruction, label: str) -> Instruction:
    """Wrap an optional step so its failure is silent.

    Optional steps exist because real estates are inconsistent: some sites
    strip the syslog envelope upstream and some do not, and one grammar must
    read both.
    """
    def run(state: dict) -> None:
        try:
            fn(state)
        except ExtractError:
            pass
        except Exception:
            pass          # an optional step must never be able to fail the line
    run.__name__ = f"optional[{label}]"
    return run


class CompiledEmit:
    """Pre-resolved OCSF mapping.

    Dotted paths are split into segment tuples once, enum tables are
    lower-cased once, and the const block is frozen. Per event the mapper does
    dictionary walks and nothing else.
    """

    __slots__ = ("cls", "category", "const", "fields", "enums", "ignore", "claims")

    def __init__(self, grammar: Grammar) -> None:
        e = grammar.emit
        self.cls = e.cls
        self.category = e.category
        self.const: tuple[tuple[tuple[str, ...], Any], ...] = tuple(
            (tuple(path.split(".")), value) for path, value in e.const.items())
        self.fields: tuple[tuple[tuple[str, ...], str], ...] = tuple(
            (tuple(path.split(".")), source) for path, source in e.fields.items())
        self.enums: tuple[tuple[tuple[str, ...], str, dict, Any, tuple[str, ...] | None], ...] = tuple(
            (tuple(path.split(".")), m.source,
             {str(k).lower(): v for k, v in m.table.items()},
             m.default,
             tuple(m.keep.split(".")) if m.keep else None)
            for path, m in e.enums.items())
        self.ignore = frozenset(e.ignore)
        # Every vendor field the mapping consumes -- used to compute residue
        # as a set difference, so a forgotten mapping is visible rather than
        # silently absent.
        self.claims = frozenset(
            [src for _, src in self.fields] + [m.source for m in e.enums.values()])


class CompiledGrammar:
    """A grammar ready to run. Immutable; safe to share between processes."""

    __slots__ = ("id", "version", "vendor", "product", "title", "family", "shape",
                 "plan", "casts", "clock", "emit", "weight", "must", "any_of",
                 "pattern", "step_names")

    def __init__(self, g: Grammar) -> None:
        self.id = g.id
        self.version = g.version
        self.vendor = g.vendor
        self.product = g.product
        self.title = g.title or f"{g.vendor} {g.product}"
        self.family = g.family
        self.shape = g.shape

        self.plan: tuple[Instruction, ...] = tuple(
            _guard(_compile_step(s), s.kind) if s.optional else _compile_step(s)
            for s in g.pipeline)
        self.step_names: tuple[str, ...] = tuple(
            f"{s.kind}{'?' if s.optional else ''}" for s in g.pipeline)

        self.casts: tuple[tuple[str, Any], ...] = tuple(
            (name, X.CASTS[kind]) for name, kind in g.coerce.items())

        if g.clock:
            try:
                self.clock: TimeClock | None = TimeClock(
                    g.clock.field, g.clock.formats, g.clock.zone)
            except ValueError as exc:
                raise CompileError(f"{g.id}: {exc}") from None
        else:
            self.clock = None

        self.emit = CompiledEmit(g)

        sig = g.signature
        self.weight = sig.weight
        self.must: tuple[str, ...] = tuple(sig.must)
        self.any_of: tuple[str, ...] = tuple(sig.any)
        try:
            self.pattern = re.compile(sig.pattern) if sig.pattern else None
        except re.error as exc:
            raise CompileError(f"{g.id}: bad signature regex: {exc}") from None

    # ---------------------------------------------------------------- running

    def matches(self, line: str) -> float:
        """Signature score for a line. Shape has already been checked by
        triage, so this only runs on plausible candidates.

        `must` literals are tested first because a literal `in` is the cheapest
        test available and rejects almost everything immediately.
        """
        for literal in self.must:
            if literal not in line:
                return 0.0
        if self.any_of and not any(a in line for a in self.any_of):
            return 0.0
        if self.pattern is not None and not self.pattern.search(line):
            return 0.0
        return self.weight

    def read(self, line: str) -> tuple[dict[str, Any], list[str]]:
        """Run the compiled pipeline. Returns (fields, notes).

        Raises ExtractError only if a NON-optional step fails, which the
        pipeline turns into a quarantine rather than a crash.
        """
        state: dict[str, Any] = {BODY: line}
        notes: list[str] = []

        for fn in self.plan:
            fn(state)

        state.pop(BODY, None)
        if self.casts:
            X.coerce(state, self.casts, notes)
        return state, notes

    def event_time(self, fields: dict[str, Any]) -> int | None:
        if self.clock is None:
            return None
        return self.clock.read(fields.get(self.clock.field))


def compile_all(grammars: list[Grammar]) -> tuple[list[CompiledGrammar], dict[str, str]]:
    """Compile a library. Returns (compiled, {grammar_id: error}).

    A grammar that fails to compile is excluded and reported rather than
    raising, for the same reason a malformed file is: one bad grammar must not
    stop the other forty from working.
    """
    ok: list[CompiledGrammar] = []
    bad: dict[str, str] = {}
    for g in grammars:
        try:
            ok.append(CompiledGrammar(g))
        except CompileError as exc:
            bad[g.id] = str(exc)
        except Exception as exc:                     # defensive: never fatal
            bad[g.id] = f"{type(exc).__name__}: {exc}"
    return ok, bad
