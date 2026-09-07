"""
strata.parse.extractors
=======================
The extraction primitives. Each is a plain function over a working dict.

These are the ONLY operations a grammar can invoke. That is the security
design, not a limitation: grammar files are untrusted input (the Forge writes
them, users edit them, and in a real deployment they arrive over an API). A
grammar format expressive enough to compute is a remote-code-execution hole
with a friendly name. Here a grammar can only name one of these and supply
arguments, so there is nothing dangerous for it to say.

Adding a primitive is a deliberate, reviewed change to this file -- which is
exactly the property that makes loading a stranger's grammar safe.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Field name reserved for "the part of the line not yet consumed". Steps read
# from it and write the remainder back, so a pipeline can peel a syslog
# envelope and then treat what is left as CSV.
BODY = "__body__"


class ExtractError(Exception):
    """A step could not do its job. Fatal unless the step is marked optional."""


# ---------------------------------------------------------------------------
# Syslog envelopes
# ---------------------------------------------------------------------------
# RFC 3164:  <PRI>Mmm dd hh:mm:ss HOST TAG: message
# Note what is absent: year, timezone, sub-second precision. See timeparse.
_RFC3164 = re.compile(
    r"^<(?P<pri>\d{1,3})>\s*"
    r"(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+(?P<rest>.*)$", re.S)

# RFC 5424: <PRI>1 TIMESTAMP HOST APP PROCID MSGID [SD] message
_RFC5424 = re.compile(
    r"^<(?P<pri>\d{1,3})>1\s+(?P<ts>\S+)\s+(?P<host>\S+)\s+(?P<app>\S+)\s+"
    r"(?P<procid>\S+)\s+(?P<msgid>\S+)\s+(?P<sd>-|(?:\[[^\]]*\])+)\s*"
    r"(?P<rest>.*)$", re.S)

_SEVERITY = ("emerg", "alert", "crit", "err", "warning", "notice", "info", "debug")


def syslog3164(state: dict[str, Any]) -> None:
    m = _RFC3164.match(state[BODY])
    if not m:
        raise ExtractError("not RFC 3164")
    pri = int(m["pri"])
    state["log_facility"] = pri >> 3
    state["log_severity"] = _SEVERITY[pri & 7]
    state["log_time"] = m["ts"]
    state["log_host"] = m["host"]
    state[BODY] = m["rest"]


def syslog5424(state: dict[str, Any]) -> None:
    m = _RFC5424.match(state[BODY])
    if not m:
        raise ExtractError("not RFC 5424")
    pri = int(m["pri"])
    state["log_facility"] = pri >> 3
    state["log_severity"] = _SEVERITY[pri & 7]
    state["log_time"] = m["ts"]
    state["log_host"] = m["host"]
    state["log_app"] = m["app"]
    if m["procid"] != "-":
        state["log_procid"] = m["procid"]
    if m["msgid"] != "-":
        state["log_msgid"] = m["msgid"]
    state[BODY] = m["rest"]


def syslog_auto(state: dict[str, Any]) -> None:
    """Accept either RFC. Real estates run both, often from the same vendor."""
    body = state[BODY]
    if body.startswith("<") and ">1 " in body[:8]:
        syslog5424(state)
    else:
        syslog3164(state)


# ---------------------------------------------------------------------------
# Positional
# ---------------------------------------------------------------------------

def split_quoted(text: str, sep: str, quote: str = '"') -> list[str]:
    """Split on `sep`, ignoring separators inside `quote`.

    This is the difference between a parser that works and one that fails
    silently. PAN-OS rule names and proxy URLs routinely contain commas; a
    naive `str.split(",")` shifts every subsequent column and produces a
    perfectly plausible, entirely wrong record. Nothing alerts, because
    nothing crashed.
    """
    if quote not in text:
        return text.split(sep)

    out: list[str] = []
    buf: list[str] = []
    inside = False
    for ch in text:
        if ch == quote:
            inside = not inside
        elif ch == sep and not inside:
            out.append("".join(buf))
            buf.clear()
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def columns(state: dict[str, Any], names: tuple[str, ...], sep: str,
            quote: str) -> None:
    """Positional columns named by `names`.

    Columns beyond the declared list are NOT discarded -- a firmware update
    that appends a field must be visible in the output, not silently dropped.
    A name of "-" marks a column deliberately unnamed (vendor padding).
    """
    parts = split_quoted(state[BODY], sep, quote) if quote else state[BODY].split(sep)
    n = len(names)
    for i, value in enumerate(parts):
        if i < n:
            name = names[i]
            if name and name != "-":
                v = value.strip()
                if v:
                    state[name] = v
        else:
            v = value.strip()
            if v:
                state[f"overflow_{i}"] = v
    state[BODY] = ""


def whitespace(state: dict[str, Any], names: tuple[str, ...], maxsplit: int) -> None:
    """Whitespace-positional columns. `maxsplit` lets the final column absorb
    the rest of the line, which is how most access logs end."""
    parts = state[BODY].split(None, maxsplit) if maxsplit else state[BODY].split()
    for i, value in enumerate(parts):
        if i < len(names) and names[i] and names[i] != "-":
            if value and value != "-":
                state[names[i]] = value
    state[BODY] = ""


# ---------------------------------------------------------------------------
# Key/value
# ---------------------------------------------------------------------------

def kv(state: dict[str, Any], pattern: re.Pattern, lower: bool) -> None:
    """`key=value` pairs. The pattern is built at compile time for the
    grammar's declared pair separator -- see compiler._kv_pattern."""
    body = state[BODY]
    found = False
    for m in pattern.finditer(body):
        key = m.group(1)
        val = m.group(2)
        if val is None:
            val = m.group(3)
        if key:
            state[key.lower() if lower else key] = val
            found = True
    if not found:
        raise ExtractError("no key=value pairs found")
    state[BODY] = ""


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def json_object(state: dict[str, Any], prefix_sep: str, max_depth: int) -> None:
    """Parse the body as JSON and flatten it to dotted keys.

    Lists are preserved as their JSON text rather than dropped or exploded:
    dropping loses data, and exploding invents field names that no mapping can
    predict. Keeping the text means the value survives into `unmapped` intact.
    """
    body = state[BODY].strip()
    start = body.find("{")
    if start < 0:
        raise ExtractError("no JSON object present")
    try:
        obj = json.loads(body[start:])
    except json.JSONDecodeError as exc:
        raise ExtractError(f"invalid JSON: {exc.msg}") from None
    if not isinstance(obj, dict):
        raise ExtractError("JSON payload is not an object")
    _flatten(obj, state, "", prefix_sep, max_depth)
    state[BODY] = ""


def _flatten(obj: dict, out: dict, prefix: str, sep: str, depth: int) -> None:
    for key, value in obj.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict) and depth > 0:
            _flatten(value, out, f"{name}{sep}", sep, depth - 1)
        elif isinstance(value, (list, tuple)):
            out[name] = json.dumps(value, separators=(",", ":"))
        elif value is not None and value != "":
            out[name] = value


# ---------------------------------------------------------------------------
# CEF / LEEF
# ---------------------------------------------------------------------------

_CEF_EXT = re.compile(r"([A-Za-z][A-Za-z0-9_]*)=((?:[^=\\]|\\.)*?)(?=\s+[A-Za-z][A-Za-z0-9_]*=|$)")

_CEF_HEADERS = ("cef_version", "cef_vendor", "cef_product",
                "cef_device_version", "cef_signature_id", "cef_name", "cef_severity")


def cef(state: dict[str, Any]) -> None:
    """CEF:0|Vendor|Product|Version|SigID|Name|Severity|extension

    The extension is `key=value` separated by spaces, but values may contain
    spaces themselves -- so the pattern above ends a value at the next
    `key=`, not at the next space. Splitting on spaces is the classic CEF
    parsing bug and truncates every multi-word value.
    """
    body = state[BODY]
    at = body.find("CEF:")
    if at < 0:
        raise ExtractError("no CEF header")
    parts = body[at:].split("|", 7)
    if len(parts) < 7:
        raise ExtractError("truncated CEF header")

    parts[0] = parts[0][4:]                       # drop the literal "CEF:"
    for name, value in zip(_CEF_HEADERS, parts):
        v = value.strip()
        if v:
            state[name] = v

    if len(parts) == 8:
        for m in _CEF_EXT.finditer(parts[7]):
            value = m.group(2).replace("\\=", "=").replace("\\\\", "\\").strip()
            if value:
                state[m.group(1)] = value
    state[BODY] = ""


_LEEF_HEADERS = ("leef_version", "leef_vendor", "leef_product",
                 "leef_device_version", "leef_event_id")


def leef(state: dict[str, Any]) -> None:
    """LEEF:x.y|Vendor|Product|Version|EventID|[delim]|tab-separated key=value"""
    body = state[BODY]
    at = body.find("LEEF:")
    if at < 0:
        raise ExtractError("no LEEF header")
    parts = body[at:].split("|", 5)
    if len(parts) < 6:
        raise ExtractError("truncated LEEF header")

    parts[0] = parts[0][5:]
    for name, value in zip(_LEEF_HEADERS, parts):
        v = value.strip()
        if v:
            state[name] = v

    payload = parts[5]
    chunks = payload.split("\t") if "\t" in payload else payload.split()
    for chunk in chunks:
        key, sep, value = chunk.partition("=")
        if sep and value.strip():
            state[key.strip()] = value.strip()
    state[BODY] = ""


# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

def named_regex(state: dict[str, Any], pattern: re.Pattern, source: str,
                keep_body: bool) -> None:
    """Named capture groups into fields. The workhorse for freeform sources
    where values sit inside an English sentence."""
    text = state.get(source, "")
    if not isinstance(text, str):
        text = str(text)
    m = pattern.search(text)
    if not m:
        raise ExtractError("pattern did not match")
    for key, value in m.groupdict().items():
        if value is not None and value != "":
            state[key] = value
    if not keep_body:
        state[BODY] = ""


def strip_prefix(state: dict[str, Any], pattern: re.Pattern) -> None:
    """Consume a leading fragment and keep the remainder as the body. Used to
    peel a vendor tag off before handing what is left to another step."""
    m = pattern.match(state[BODY])
    if not m:
        raise ExtractError("prefix did not match")
    for key, value in (m.groupdict() or {}).items():
        if value is not None and value != "":
            state[key] = value
    state[BODY] = state[BODY][m.end():]


# ---------------------------------------------------------------------------
# Type coercion
# ---------------------------------------------------------------------------

def _to_bool(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on", "enable", "enabled")


CASTS = {"int": int, "float": float, "bool": _to_bool, "str": str}


def coerce(state: dict[str, Any], plan: tuple[tuple[str, Any], ...],
           notes: list[str]) -> None:
    """Apply declared types.

    A failed cast KEEPS THE ORIGINAL STRING rather than dropping the field or
    substituting a zero. Requirement (a) applies to bad data too: a port of
    "unknown" is information, and quietly turning it into 0 is a lie the
    analyst has no way to detect.
    """
    for name, cast in plan:
        value = state.get(name)
        if value is None:
            continue
        try:
            state[name] = cast(value)
        except (ValueError, TypeError):
            notes.append(f"{name}: could not cast to {cast.__name__}, kept as text")
