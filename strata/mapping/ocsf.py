"""
strata.mapping.ocsf
===================
Vendor vocabulary -> OCSF 1.8. Requirements (c) and (d).

WHY OCSF RATHER THAN OUR OWN SCHEMA

The Open Cybersecurity Schema Framework is vendor-neutral, governed by the
Linux Foundation, and at version 1.8.0 as of March 2026. Its base event class
already defines `unmapped` and `raw_data` -- so requirements (a), (c) and (d)
land on fields that already exist in a published standard rather than on our
opinion. Inventing a schema would cost weeks, produce something worse, and
quietly undermine the one claim the problem statement cares most about.

TWO RULES THE MAPPER ENFORCES, RATHER THAN TRUSTING AUTHORS TO REMEMBER

1. Every extracted field either lands at a named OCSF path or lands in
   `unmapped`. Residue is computed as a SET DIFFERENCE against what the
   mapping claimed, so forgetting to map a field shows up in the output
   instead of vanishing.

2. Enum collapse always keeps the vendor's original word alongside the
   normalized integer. Five vendors have thirty words for "blocked";
   collapsing them is the point, and losing them is not.

THREE TIMES, NEVER CONFLATED

    time           when the event happened, per the device
    original_time  the device's own string, verbatim and unparsed
    logged_time    when WE received it, from our clock

Most pipelines keep one and lose the argument later. Keeping all three is what
lets an investigator reason about clock skew instead of guessing at it.
"""

from __future__ import annotations

import time
from typing import Any

from ..core.model import Envelope, Event, Extraction, Provenance
from ..parse.compiler import CompiledEmit, CompiledGrammar

OCSF_VERSION = "1.8.0"
NS_PER_MS = 1_000_000


def _place(doc: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    """Write a value at a pre-split OCSF path, creating intermediates.

    Paths arrive already split by the compiler, so this does no string work
    per event -- only dictionary walks.
    """
    node = doc
    for key in path[:-1]:
        child = node.get(key)
        if type(child) is not dict:
            child = {}
            node[key] = child
        node = child
    node[path[-1]] = value


class Mapper:
    """Turns an Extraction into an Event."""

    __slots__ = ()

    def build(
        self,
        extraction: Extraction,
        grammar: CompiledGrammar,
        envelope: Envelope,
        record_id: bytes,
        stratum: int,
        generation: int = 0,
    ) -> Event:
        emit: CompiledEmit = grammar.emit
        fields = extraction.fields

        now_ms = time.time_ns() // NS_PER_MS
        doc: dict[str, Any] = {
            "class_uid": emit.cls,
            "category_uid": emit.category,
            "metadata": {
                "version": OCSF_VERSION,
                "product": {
                    "vendor_name": grammar.vendor,
                    "name": grammar.product,
                    "feature": {"name": grammar.id},
                },
                "logged_time": envelope.received_ns // NS_PER_MS,
                "processed_time": now_ms,
            },
        }

        for path, value in emit.const:
            _place(doc, path, value)

        for path, source in emit.fields:
            value = fields.get(source)
            if value is not None:
                _place(doc, path, value)

        for path, source, table, default, keep in emit.enums:
            raw = fields.get(source)
            if raw is None:
                continue
            _place(doc, path, table.get(str(raw).strip().lower(), default))
            if keep is not None:
                _place(doc, keep, raw)

        # ---- time ----------------------------------------------------------
        if extraction.event_ns is not None:
            doc["time"] = extraction.event_ns // NS_PER_MS
            if grammar.clock is not None:
                original = fields.get(grammar.clock.field)
                if original is not None:
                    doc["metadata"]["original_time"] = str(original)
        else:
            # No usable device time. Fall back to receipt time and SAY SO --
            # an invented timestamp silently corrupts every correlation that
            # touches this event.
            doc["time"] = envelope.received_ns // NS_PER_MS
            doc["metadata"]["time_source"] = "receipt_fallback"

        # ---- requirement (a) at the field level, enforced -------------------
        claims, ignore = emit.claims, emit.ignore
        clock_field = grammar.clock.field if grammar.clock else None
        residue = {
            k: v for k, v in fields.items()
            if k not in claims and k not in ignore and k != clock_field
        }

        claimed = len(fields) - len(residue)
        provenance = Provenance(
            record_id=record_id,
            stratum=stratum,
            grammar_id=grammar.id,
            grammar_version=grammar.version,
            confidence=extraction.confidence,
            generation=generation,
            coverage=(claimed / len(fields)) if fields else 0.0,
            channel=envelope.channel,
            peer=envelope.peer,
            received_ns=envelope.received_ns,
            notes=extraction.notes,
        )
        return Event(ocsf=doc, residue=residue, provenance=provenance)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# Fields the OCSF base event class requires. Kept minimal and explicit rather
# than shipping the full 1.8 JSON schema: validating every event against a
# multi-megabyte schema would dominate the pipeline, and these four are the
# ones whose absence actually breaks a downstream consumer.
REQUIRED = ("class_uid", "category_uid", "time", "metadata")


def validate(doc: dict[str, Any]) -> list[str]:
    """Structural check. Returns a list of problems; empty means valid."""
    problems = []
    for key in REQUIRED:
        if key not in doc:
            problems.append(f"missing required field {key!r}")
    cls = doc.get("class_uid")
    if not isinstance(cls, int) or cls <= 0:
        problems.append("class_uid must be a positive integer")
    t = doc.get("time")
    if not isinstance(t, int):
        problems.append("time must be an integer (epoch milliseconds)")
    elif not (946_684_800_000 < t < 4_102_444_800_000):    # 2000..2100
        problems.append(f"time {t} is outside a plausible range; check the clock spec")
    return problems


# ---------------------------------------------------------------------------
# Class catalogue -- for the UI and the docs
# ---------------------------------------------------------------------------

CLASSES = {
    4001: ("Network Activity", 4),
    4002: ("HTTP Activity", 4),
    4003: ("DNS Activity", 4),
    4004: ("DHCP Activity", 4),
    4005: ("RDP Activity", 4),
    4009: ("Email Activity", 4),
    2004: ("Detection Finding", 2),
}

DISPOSITIONS = {
    0: "Unknown", 1: "Allowed", 2: "Blocked", 3: "Dropped",
    4: "Quarantined", 8: "Reset", 99: "Other",
}

SEVERITIES = {
    0: "Unknown", 1: "Informational", 2: "Low", 3: "Medium",
    4: "High", 5: "Critical", 6: "Fatal",
}
