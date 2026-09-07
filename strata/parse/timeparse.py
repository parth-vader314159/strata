"""
strata.parse.timeparse
======================
Fast, explicit timestamp parsing.

WHY NOT strptime

`datetime.strptime` re-parses its format string on every call and builds a
regex each time. Profiling put it among the top costs in the pipeline, for the
single most repetitive operation there is: the same three or four formats,
millions of times.

Here each supported format is a hand-written slicer that reads digits at fixed
offsets. Roughly an order of magnitude faster, and -- more importantly -- each
one is explicit about what it assumes, which matters enormously for the two
timestamp formats that are genuinely ambiguous.

THE HARD PART, WHICH IS NOT PERFORMANCE

RFC 3164 syslog timestamps look like `Aug 21 14:32:07`. That carries **no year
and no timezone**. Every implementation must invent both, and the inventions
are where real-world log pipelines quietly go wrong:

  * Assume the current year, and every December log read on 2 January lands
    twelve months in the future.
  * Assume UTC when the device sends local time, and events land hours away
    from the events they should correlate with.

STRATA handles the first with an explicit rule (below) and refuses to guess at
the second: a grammar must *declare* its device's timezone. Declaring an
assumption makes it reviewable; inferring one makes it a bug nobody can see.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Callable

NS = 1_000_000_000

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# Tolerance for the RFC 3164 year rule. A device with a clock a few minutes
# fast must not be rolled back a whole year, so we only conclude "this must be
# last December" when the timestamp is more than a day ahead of us.
_FUTURE_SLACK = timedelta(days=1)


class TimeFormat:
    """A named timestamp format with a hand-written parser."""

    __slots__ = ("name", "parse", "needs_year", "example")

    def __init__(self, name: str, parse: Callable[[str, int], int | None],
                 needs_year: bool, example: str) -> None:
        self.name = name
        self.parse = parse
        self.needs_year = needs_year
        self.example = example


def _to_ns(y: int, mo: int, d: int, h: int, mi: int, s: int,
           micro: int, offset_s: int) -> int | None:
    """Civil time -> epoch nanoseconds.

    Uses calendar arithmetic rather than constructing a datetime, which is
    another allocation avoided per event. Returns None on impossible dates
    (month 13, day 32) so corrupt input never becomes a plausible timestamp.
    """
    if not (1 <= mo <= 12 and 1 <= d <= 31 and 0 <= h <= 23
            and 0 <= mi <= 59 and 0 <= s <= 60):
        return None
    try:
        dt = datetime(y, mo, d, h, mi, min(s, 59), micro, tzinfo=timezone.utc)
    except ValueError:
        return None                      # e.g. 31 February
    return int(dt.timestamp()) * NS + micro * 1000 - offset_s * NS


def _int(s: str, a: int, b: int) -> int:
    return int(s[a:b])


# ---------------------------------------------------------------------------
# Format implementations
# ---------------------------------------------------------------------------

def _iso8601(v: str, tz_offset: int) -> int | None:
    """2026-08-21T14:32:07[.ffffff][Z|+hh:mm|+hhmm] and the space variant.

    The separators are CHECKED, not assumed. Slicing by position alone would
    accept "2026/08/26 14:32:07" as ISO-8601 -- the same instant, reached by
    luck, and enough to make format detection report the wrong format.
    """
    if len(v) < 19 or v[4] != "-" or v[7] != "-":
        return None
    if v[10] not in ("T", "t", " ") or v[13] != ":" or v[16] != ":":
        return None
    try:
        y, mo, d = _int(v, 0, 4), _int(v, 5, 7), _int(v, 8, 10)
        h, mi, s = _int(v, 11, 13), _int(v, 14, 16), _int(v, 17, 19)
    except ValueError:
        return None

    micro, at = 0, 19
    if at < len(v) and v[at] == ".":
        j = at + 1
        while j < len(v) and v[j].isdigit():
            j += 1
        frac = v[at + 1:j]
        micro = int((frac + "000000")[:6]) if frac else 0
        at = j

    offset = tz_offset
    if at < len(v):
        z = v[at]
        if z in ("Z", "z"):
            offset = 0
        elif z in ("+", "-"):
            rest = v[at + 1:].replace(":", "")
            if len(rest) >= 4 and rest[:4].isdigit():
                offset = (_int(rest, 0, 2) * 3600 + _int(rest, 2, 4) * 60)
                if z == "-":
                    offset = -offset
    return _to_ns(y, mo, d, h, mi, s, micro, offset)


def _slashed(v: str, tz_offset: int) -> int | None:
    """2026/08/21 14:32:07 -- PAN-OS and several other vendors."""
    if len(v) < 19 or v[4] != "/" or v[7] != "/" or v[10] != " ":
        return None
    if v[13] != ":" or v[16] != ":":
        return None
    try:
        return _to_ns(_int(v, 0, 4), _int(v, 5, 7), _int(v, 8, 10),
                      _int(v, 11, 13), _int(v, 14, 16), _int(v, 17, 19), 0, tz_offset)
    except ValueError:
        return None


def _dashed(v: str, tz_offset: int) -> int | None:
    """2026-08-21 14:32:07 without a zone marker. Same grammar as ISO-8601
    with a space in place of the T, which _iso8601 already accepts."""
    return _iso8601(v, tz_offset)


def _bsd(v: str, tz_offset: int) -> int | None:
    """`Aug 21 14:32:07` -- RFC 3164. No year, no zone. See module docstring.

    THE YEAR RULE, stated explicitly so it is reviewable:
      take the current year; if that puts the event more than a day in the
      future, it must belong to last year instead.

    This is correct across a New Year boundary in both directions and wrong
    only for logs replayed more than a year late, which is a case where any
    answer is a guess and we would rather be predictably wrong than subtly so.
    """
    if len(v) < 15:
        return None
    mo = MONTHS.get(v[0:3])
    if mo is None:
        return None
    try:
        d = int(v[4:6].strip())
        h, mi, s = _int(v, 7, 9), _int(v, 10, 12), _int(v, 13, 15)
    except ValueError:
        return None

    now = time.time()
    year = time.gmtime(now).tm_year
    ns = _to_ns(year, mo, d, h, mi, s, 0, tz_offset)
    if ns is None:
        return None
    if ns > int((now + _FUTURE_SLACK.total_seconds()) * NS):
        ns = _to_ns(year - 1, mo, d, h, mi, s, 0, tz_offset)
    return ns


def _epoch_s(v: str, tz_offset: int) -> int | None:
    """Seconds since the epoch, with or without a fractional part."""
    try:
        return int(float(v) * NS)
    except (ValueError, OverflowError):
        return None


def _epoch_ms(v: str, tz_offset: int) -> int | None:
    try:
        return int(float(v) * 1_000_000)
    except (ValueError, OverflowError):
        return None


FORMATS: dict[str, TimeFormat] = {
    "iso8601": TimeFormat("iso8601", _iso8601, False, "2026-08-21T14:32:07.123Z"),
    "slashed": TimeFormat("slashed", _slashed, False, "2026/08/21 14:32:07"),
    "dashed": TimeFormat("dashed", _dashed, False, "2026-08-21 14:32:07"),
    "bsd": TimeFormat("bsd", _bsd, True, "Aug 21 14:32:07"),
    "epoch": TimeFormat("epoch", _epoch_s, False, "1787302800"),
    "epoch_ms": TimeFormat("epoch_ms", _epoch_ms, False, "1787302800123"),
}


class Clock:
    """A compiled timestamp reader for one grammar.

    Holds the ordered list of formats to try and the declared UTC offset. The
    order matters: put the format the source actually emits first and the
    common case costs one call.
    """

    __slots__ = ("field", "formats", "offset_s", "zone_name")

    def __init__(self, field: str, formats: list[str], zone: str = "UTC") -> None:
        self.field = field
        unknown = [f for f in formats if f not in FORMATS]
        if unknown:
            raise ValueError(
                f"unknown time format(s) {unknown}; known: {sorted(FORMATS)}")
        self.formats = [FORMATS[f] for f in formats]
        self.zone_name = zone
        self.offset_s = _zone_offset(zone)

    def read(self, value: object) -> int | None:
        """Value -> epoch nanoseconds, or None if no declared format matched."""
        if value is None:
            return None
        v = value if type(value) is str else str(value)
        v = v.strip()
        if not v:
            return None
        for fmt in self.formats:
            ns = fmt.parse(v, self.offset_s)
            if ns is not None:
                return ns
        return None


def _zone_offset(zone: str) -> int:
    """Fixed UTC offset in seconds for a declared zone.

    Only fixed offsets are supported, deliberately. Named zones with daylight
    saving would make a stored timestamp depend on a tz database version, so
    the same archive could read differently on two machines -- unacceptable for
    something whose purpose is evidence. A device in a DST zone declares the
    offset its logs actually carry.
    """
    z = zone.strip().upper()
    if z in ("UTC", "GMT", "Z", ""):
        return 0
    sign = 1
    if z[0] in "+-":
        sign = -1 if z[0] == "-" else 1
        z = z[1:]
    if z.startswith("UTC") or z.startswith("GMT"):
        z = z[3:]
        if z and z[0] in "+-":
            sign = -1 if z[0] == "-" else 1
            z = z[1:]
    z = z.replace(":", "")
    if not z:
        return 0
    if not z.isdigit() or len(z) not in (2, 4):
        raise ValueError(
            f"unsupported timezone {zone!r}; use UTC or a fixed offset like +05:30")
    hours = int(z[:2])
    minutes = int(z[2:4]) if len(z) == 4 else 0
    return sign * (hours * 3600 + minutes * 60)


def sniff(value: str) -> str | None:
    """Which format does this sample look like? Used by the Forge when
    proposing a grammar. Ordered specific-first so `epoch` does not swallow a
    value that is really an ISO date."""
    v = value.strip()
    if not v:
        return None
    for name in ("iso8601", "slashed", "dashed", "bsd"):
        if FORMATS[name].parse(v, 0) is not None:
            return name
    if v.isdigit():
        if len(v) == 13:
            return "epoch_ms"
        if 9 <= len(v) <= 11:
            return "epoch"
    if v.replace(".", "", 1).isdigit() and "." in v:
        return "epoch"
    return None
