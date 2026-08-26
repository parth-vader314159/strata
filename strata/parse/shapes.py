"""
strata.parse.shapes
===================
Cheap structural fingerprinting of a log line.

WHY THIS EXISTS

The naive classifier evaluates every grammar's rules against every line. With
G grammars and R rules each that is G x R regex operations per event, and it
grows linearly as you onboard sources -- exactly backwards, since the whole
promise is that adding sources is free.

A log line's *structure* is decidable far more cheaply than its *identity*.
One pass of character counting tells you it is JSON, or CEF, or has 34 commas,
or holds 12 `key=value` pairs. That single pass narrows the candidate grammars
from "all of them" to "the two that could possibly match", and only those get
their literal and regex rules evaluated.

The result: classification cost is roughly constant in the number of grammars
instead of linear. Onboarding the fiftieth source costs the pipeline nothing.

The fingerprint is computed once per line and handed to triage, the compiler,
and the Forge, so the scan is paid for once and reused three times.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Shape(IntEnum):
    """Structural families a log line can belong to. A grammar declares which
    one it handles, and triage only considers grammars whose family matches."""

    UNKNOWN = 0
    JSON = 1          # a JSON object per line
    CEF = 2           # ArcSight: pipe header + key=value extension
    LEEF = 3          # QRadar: pipe header + tab-separated key=value
    KV = 4            # key=value pairs, separator varies
    CSV = 5           # positional, comma-separated, no names on the wire
    DELIMITED = 6     # positional, whitespace-separated
    FREEFORM = 7      # values embedded in a human sentence

    @property
    def label(self) -> str:
        return _SHAPE_LABELS[self]


_SHAPE_LABELS = {
    Shape.UNKNOWN: "unknown", Shape.JSON: "json", Shape.CEF: "cef",
    Shape.LEEF: "leef", Shape.KV: "kv", Shape.CSV: "csv",
    Shape.DELIMITED: "delimited", Shape.FREEFORM: "freeform",
}

SHAPE_BY_NAME = {s.label: s for s in Shape}


@dataclass(slots=True, frozen=True)
class Fingerprint:
    """Everything one cheap pass can tell us about a line."""

    shape: Shape
    length: int
    commas: int
    equals: int
    pipes: int
    tabs: int
    spaces: int
    syslog_pri: int      # -1 when the line has no <PRI> prefix
    body_at: int         # index where the payload starts, past any <PRI>

    @property
    def has_syslog(self) -> bool:
        return self.syslog_pri >= 0


def fingerprint(line: str) -> Fingerprint:
    """One pass over the line. Deliberately no regex.

    Counting characters in a tight loop beats even a compiled regex here,
    because we want six different facts and a regex would need six passes.
    """
    n = len(line)
    commas = equals = pipes = tabs = spaces = 0

    # --- syslog <PRI> prefix -------------------------------------------------
    pri, at = -1, 0
    if n > 2 and line[0] == "<":
        close = line.find(">", 1, 6)          # PRI is at most 3 digits
        if close > 1:
            token = line[1:close]
            if token.isdigit():
                pri, at = int(token), close + 1

    # --- one counting pass ---------------------------------------------------
    # Scanned from the body so a hostname full of dots cannot skew the counts.
    for ch in line[at:]:
        if ch == ",":
            commas += 1
        elif ch == "=":
            equals += 1
        elif ch == "|":
            pipes += 1
        elif ch == "\t":
            tabs += 1
        elif ch == " ":
            spaces += 1

    body = line[at:]
    shape = _classify(body, commas, equals, pipes, tabs, spaces)
    return Fingerprint(shape=shape, length=n, commas=commas, equals=equals,
                       pipes=pipes, tabs=tabs, spaces=spaces,
                       syslog_pri=pri, body_at=at)


def _classify(body: str, commas: int, equals: int, pipes: int,
              tabs: int, spaces: int) -> Shape:
    """Decide the structural family. Ordered most-specific first, because a
    CEF line also contains `key=value` pairs and would otherwise be called KV."""
    stripped = body.strip()
    if not stripped:
        return Shape.UNKNOWN

    # Unambiguous markers first.
    if stripped[0] == "{" and stripped[-1] == "}":
        return Shape.JSON
    if pipes >= 5 and "CEF:" in body:
        return Shape.CEF
    if pipes >= 4 and "LEEF:" in body:
        return Shape.LEEF

    # Structured-but-unmarked. A line that is mostly `k=v` is KV even if it also
    # has commas, because the keys carry the meaning and commas are incidental.
    if equals >= 4 and equals * 6 >= _words(body):
        return Shape.KV

    # Positional. A high comma count with no keys means columns.
    if commas >= 8 and equals < 3:
        return Shape.CSV

    # Whitespace-positional: many short tokens, few of them prose.
    if tabs >= 4:
        return Shape.DELIMITED
    words = _words(body)
    if 5 <= words <= 24 and commas <= 2 and equals <= 1 and _looks_positional(body):
        return Shape.DELIMITED

    return Shape.FREEFORM


def _words(body: str) -> int:
    return body.count(" ") + 1


def _looks_positional(body: str) -> bool:
    """Positional records are mostly non-alphabetic tokens -- timestamps, IPs,
    ports, status codes. Human sentences are mostly words.

    Sampling the first sixteen tokens is enough to tell them apart and keeps
    this O(1) rather than O(line length)."""
    tokens = body.split()[:16]
    if len(tokens) < 5:
        return False
    numeric = sum(1 for t in tokens if any(c.isdigit() for c in t))
    return numeric * 2 >= len(tokens)
