"""
strata.learn.induction
======================
Working out the structure of a log source nobody has described.

STRATEGY BY SHAPE, WHICH IS THE IMPROVEMENT

The usual approach to this problem is template mining (DRAIN and its
relatives): cluster lines by token similarity and call the disagreeing
positions variables. It works, and for genuinely freeform prose it is the only
thing that works.

But it is the wrong tool for most log sources, because most log sources are
already structured -- they just are not structured in a way anybody told us
about. A `key=value` line does not need clustering; it needs its keys read. A
CSV line does not need clustering; it needs its columns counted and profiled.
Running a clusterer over them throws away information that is sitting in plain
sight and produces a worse answer more slowly.

So induction dispatches on the fingerprint:

    json / kv / cef / leef  ->  enumerate keys, profile values
    csv / delimited         ->  profile each column position
    freeform                ->  token clustering, then profile the slots

VALUE PROFILING IS WHERE THE REAL LEVERAGE IS

Knowing a column is named `field_08` tells you nothing. Knowing that every
value in it is an IPv4 address, that there are 137 distinct ones, and that the
column two positions later is always an integer between 1 and 65535 tells you
it is a source endpoint followed by its port -- regardless of what it is
called or whether it is called anything at all.

That is how a human reads an unfamiliar log, and it is why the Forge can
propose useful mappings for columns that have no names to match against.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ..parse.shapes import Shape, fingerprint
from ..parse.timeparse import sniff as sniff_time

# ---------------------------------------------------------------------------
# Value classification
# ---------------------------------------------------------------------------

_IPV4 = re.compile(r"^(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
                   r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$")
_IPV6 = re.compile(r"^(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}$")
_MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
_URL = re.compile(r"^[a-z][a-z0-9+.-]*://\S+$", re.I)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HEXID = re.compile(r"^[0-9A-Fa-f]{16,}$")
_HOSTNAME = re.compile(r"^[A-Za-z][A-Za-z0-9.-]{2,}$")


def kind_of(value: str) -> str:
    """What sort of thing is this, judged from the value alone."""
    v = value.strip()
    if not v or v in ("-", "--", "n/a", "N/A", "null", "NULL"):
        return "empty"
    if _IPV4.match(v):
        return "ipv4"
    if _MAC.match(v):
        return "mac"
    if _URL.match(v):
        return "url"
    if _EMAIL.match(v):
        return "email"
    if v.isdigit():
        n = int(v)
        if 1 <= n <= 65535 and len(v) <= 5:
            return "port_or_int"
        if len(v) in (10, 13):
            return "epoch_or_int"
        return "int"
    if _HEXID.match(v):
        return "hexid"
    try:
        float(v)
        return "float"
    except ValueError:
        pass
    if sniff_time(v):
        return "timestamp"
    if ":" in v and _IPV6.match(v):
        return "ipv6"
    if v.lower() in ("true", "false", "yes", "no", "enable", "disable"):
        return "bool"
    if _HOSTNAME.match(v) and "." in v:
        return "hostname"
    return "text"


@dataclass(slots=True)
class Profile:
    """What we learned about one field or column position."""

    key: str                        # a name if it had one, else a position label
    position: int = -1
    samples: list[str] = field(default_factory=list)
    kinds: Counter = field(default_factory=Counter)
    distinct: int = 0
    total: int = 0
    empties: int = 0

    def observe(self, value: Any) -> None:
        text = value if type(value) is str else str(value)
        self.total += 1
        k = kind_of(text)
        self.kinds[k] += 1
        if k == "empty":
            self.empties += 1
        elif len(self.samples) < 12:
            self.samples.append(text)

    @property
    def kind(self) -> str:
        """The dominant kind, ignoring empties. A column that is 90% IPv4 and
        10% "-" is an IPv4 column with gaps, not a mixed column."""
        for k, _ in self.kinds.most_common():
            if k != "empty":
                return k
        return "empty"

    @property
    def purity(self) -> float:
        """How consistently this field holds one kind. Low purity means the
        column is not what it looks like, and the Forge should say so instead
        of proposing a confident mapping."""
        real = self.total - self.empties
        if real <= 0:
            return 0.0
        return self.kinds[self.kind] / real

    @property
    def constant(self) -> bool:
        """A field with exactly one value across the whole sample. These are
        gold for signatures -- a constant column is what identifies the source."""
        return self.distinct == 1 and self.total > 2

    def coerce_type(self) -> str | None:
        k = self.kind
        if k in ("int", "port_or_int", "epoch_or_int"):
            return "int"
        if k == "float":
            return "float"
        if k == "bool":
            return "bool"
        return None

    def report(self) -> dict[str, Any]:
        return {
            "key": self.key, "position": self.position, "kind": self.kind,
            "purity": round(self.purity, 3), "distinct": self.distinct,
            "fill": round(1 - self.empties / self.total, 3) if self.total else 0.0,
            "samples": self.samples[:4],
        }


@dataclass(slots=True)
class Induction:
    """The complete result of studying a sample of lines."""

    shape: Shape
    lines: int
    profiles: list[Profile]
    templates: list[dict] = field(default_factory=list)
    signature_literals: list[str] = field(default_factory=list)
    syslog_wrapped: bool = False
    notes: list[str] = field(default_factory=list)

    def report(self) -> dict[str, Any]:
        return {
            "shape": self.shape.label,
            "lines": self.lines,
            "syslog_wrapped": self.syslog_wrapped,
            "fields_found": len(self.profiles),
            "signature_literals": self.signature_literals,
            "profiles": [p.report() for p in self.profiles],
            "templates": self.templates,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Structured strategies
# ---------------------------------------------------------------------------

_KV_SCAN = re.compile(r'([A-Za-z_][A-Za-z0-9_.\-]*)=(?:"([^"]*)"|([^\s|]*))')


def _strip_syslog(line: str) -> tuple[str, bool]:
    from ..parse.extractors import _RFC3164, _RFC5424
    m = _RFC5424.match(line) or _RFC3164.match(line)
    return (m["rest"], True) if m else (line, False)


def _profile_kv(bodies: list[str]) -> list[Profile]:
    byname: dict[str, Profile] = {}
    values: dict[str, set] = {}
    for body in bodies:
        for m in _KV_SCAN.finditer(body):
            key = m.group(1)
            val = m.group(2) if m.group(2) is not None else (m.group(3) or "")
            p = byname.get(key)
            if p is None:
                p = byname[key] = Profile(key=key)
                values[key] = set()
            p.observe(val)
            if len(values[key]) < 500:
                values[key].add(val)
    for key, p in byname.items():
        p.distinct = len(values[key])
    return list(byname.values())


def _profile_json(bodies: list[str]) -> list[Profile]:
    import json
    from ..parse.extractors import _flatten
    byname: dict[str, Profile] = {}
    values: dict[str, set] = {}
    for body in bodies:
        start = body.find("{")
        if start < 0:
            continue
        try:
            obj = json.loads(body[start:])
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        flat: dict[str, Any] = {}
        _flatten(obj, flat, "", ".", 6)
        for key, val in flat.items():
            p = byname.get(key)
            if p is None:
                p = byname[key] = Profile(key=key)
                values[key] = set()
            p.observe(val)
            if len(values[key]) < 500:
                values[key].add(str(val))
    for key, p in byname.items():
        p.distinct = len(values[key])
    return list(byname.values())


def _profile_columns(bodies: list[str], sep: str) -> list[Profile]:
    """Profile each column POSITION. Names come later, from a human or from
    the value-shape heuristics in the proposer."""
    from ..parse.extractors import split_quoted
    profiles: dict[int, Profile] = {}
    values: dict[int, set] = {}
    for body in bodies:
        parts = split_quoted(body, sep) if sep != " " else body.split()
        for i, val in enumerate(parts):
            p = profiles.get(i)
            if p is None:
                p = profiles[i] = Profile(key=f"col_{i:02d}", position=i)
                values[i] = set()
            p.observe(val)
            if len(values[i]) < 500:
                values[i].add(val.strip())
    for i, p in profiles.items():
        p.distinct = len(values[i])
    return [profiles[i] for i in sorted(profiles)]


# ---------------------------------------------------------------------------
# Freeform strategy: token clustering
# ---------------------------------------------------------------------------

_MASKS: list[tuple[re.Pattern, str]] = [
    (_IPV4, "<IP>"), (_MAC, "<MAC>"), (_URL, "<URL>"),
    (re.compile(r"^\d+$"), "<NUM>"),
    (re.compile(r"^[0-9A-Fa-f]{16,}$"), "<HEX>"),
    (re.compile(r"^\d{2}:\d{2}:\d{2}$"), "<TIME>"),
]
WILDCARD = "<*>"


def _mask(token: str) -> str:
    for pattern, tag in _MASKS:
        if pattern.match(token):
            return tag
    return token


def _split_tokens(line: str) -> list[str]:
    return [t for t in re.split(r"(\s+|[,;|=\[\]])", line) if t and not t.isspace()]


def cluster(bodies: list[str], similarity: float = 0.55) -> list[dict]:
    """Group lines by token template.

    Split first, then mask each token. Masking the whole line before splitting
    changes the token count whenever a mask spans a delimiter, which silently
    misaligns the raw and masked sequences -- so the sample values recorded for
    a slot end up belonging to a different slot.
    """
    groups: dict[int, list[dict]] = {}

    for body in bodies:
        raw = _split_tokens(body)
        masked = [_mask(t) for t in raw]
        bucket = groups.setdefault(len(masked), [])

        best, best_score = None, 0.0
        for g in bucket:
            tpl = g["template"]
            hits = sum(1 for a, b in zip(tpl, masked) if a == b or a == WILDCARD)
            score = hits / len(masked) if masked else 0.0
            if score >= similarity and score > best_score:
                best, best_score = g, score

        if best is None:
            bucket.append({"template": list(masked), "count": 1,
                           "examples": [body], "slots": {}, "raws": [raw]})
            best = bucket[-1]
        else:
            for i, (a, b) in enumerate(zip(best["template"], masked)):
                if a != b and a != WILDCARD:
                    best["template"][i] = WILDCARD
            best["count"] += 1
            if len(best["examples"]) < 4:
                best["examples"].append(body)
            if len(best["raws"]) < 200:
                best["raws"].append(raw)

    out = []
    for bucket in groups.values():
        for g in bucket:
            slots = {}
            for i, tok in enumerate(g["template"]):
                if tok == WILDCARD or (tok.startswith("<") and tok.endswith(">")):
                    vals = [r[i] for r in g["raws"] if i < len(r)]
                    if vals:
                        slots[i] = vals
            g["slots"] = slots
            g.pop("raws")
            out.append(g)
    return sorted(out, key=lambda g: -g["count"])


# ---------------------------------------------------------------------------
# Signature discovery
# ---------------------------------------------------------------------------

_STOP = re.compile(r"^[\d.:/-]+$")


def find_signature(bodies: list[str], profiles: list[Profile],
                   limit: int = 3) -> list[str]:
    """Literals that identify this source.

    A constant column or a constant key is the best possible signature: it is
    present in every line by construction, it is cheap to test, and a human
    reviewing the grammar can see immediately why it works.
    """
    literals: list[str] = []

    for p in profiles:
        if p.constant and p.samples:
            value = p.samples[0].strip()
            if len(value) >= 4 and not _STOP.match(value) and value not in literals:
                literals.append(value)
        if len(literals) >= limit:
            return literals

    # Fall back to any token common to every sampled line.
    if not literals and bodies:
        sample = bodies[: min(len(bodies), 60)]
        candidates = [t for t in _split_tokens(sample[0])
                      if len(t) >= 5 and not _STOP.match(t)]
        for token in candidates:
            if all(token in b for b in sample):
                literals.append(token)
                if len(literals) >= limit:
                    break
    return literals


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def induce(lines: list[str], sep_hint: str | None = None) -> Induction:
    """Study a sample of lines and report everything we can determine."""
    clean = [l.rstrip("\r\n") for l in lines if l.strip()]
    if not clean:
        return Induction(Shape.UNKNOWN, 0, [], notes=["no non-empty lines supplied"])

    fps = [fingerprint(l) for l in clean[:400]]
    shape = Counter(f.shape for f in fps).most_common(1)[0][0]
    wrapped = sum(1 for f in fps if f.has_syslog) > len(fps) * 0.6

    bodies_and_flags = [_strip_syslog(l) for l in clean]
    bodies = [b for b, _ in bodies_and_flags]

    notes: list[str] = []
    templates: list[dict] = []

    if shape is Shape.JSON:
        profiles = _profile_json(bodies)
    elif shape in (Shape.KV, Shape.CEF, Shape.LEEF):
        profiles = _profile_kv(bodies)
        if shape is Shape.CEF:
            notes.append("CEF header fields are added by the cef extractor, not by key scan")
    elif shape is Shape.CSV:
        sep = sep_hint or ","
        profiles = _profile_columns(bodies, sep)
        widths = Counter(len(b.split(sep)) for b in bodies)
        if len(widths) > 1:
            notes.append(
                f"column count varies across the sample {dict(widths.most_common(3))} "
                "-- likely more than one message subtype; consider one grammar per subtype")
    elif shape is Shape.DELIMITED:
        profiles = _profile_columns(bodies, " ")
    else:
        templates = cluster(bodies)[:10]
        profiles = []
        for g in templates[:1]:
            for pos, vals in sorted(g["slots"].items()):
                p = Profile(key=f"var_{pos:02d}", position=pos)
                for v in vals:
                    p.observe(v)
                p.distinct = len(set(vals))
                profiles.append(p)
        if len(templates) > 6:
            notes.append(f"{len(templates)} distinct templates found -- this source "
                         "emits several message types; the proposal covers the most common")

    signature = find_signature(bodies, profiles)
    if not signature:
        notes.append("no stable identifying literal found; the proposed signature "
                     "falls back to a structural pattern and may need tightening")

    return Induction(shape=shape, lines=len(clean), profiles=profiles,
                     templates=templates, signature_literals=signature,
                     syslog_wrapped=wrapped, notes=notes)
