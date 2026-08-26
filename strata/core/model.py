"""
strata.core.model
=================
The data model. Every stage of STRATA speaks these types and nothing else.

DESIGN NOTE -- why plain slotted dataclasses and not a validation library:

These objects are constructed once per log line. At 30,000 lines a second that
is 30,000 constructions a second, and a validating model charges a schema walk
for each one -- to validate data we just produced ourselves, in the same
process, from code we control. That is a tax with no benefit.

Validation belongs at the *trust boundary*: grammar files written by humans,
and JSON arriving at the HTTP API. Both of those are validated strictly (see
`parse.grammar` and `app.api`). Internal objects are not re-validated, because
nothing untrusted ever constructs one.

`__slots__` on every class: no per-instance __dict__, roughly 40% less memory
per event and measurably faster attribute access. It also makes a typo an
AttributeError instead of a silently-created field, which is the sort of bug
that produces a plausible-looking wrong answer.

THE PIPELINE

    bytes  ->  Record   ->  Extraction  ->  Event  ->  outlets
               (ledger)     (parse)         (mapping)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any

# Bumped only on a breaking change to the on-disk or in-flight shape. Stamped
# into every stored record so a future STRATA can still read today's archive.
MODEL_VERSION = 2


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def digest(payload: bytes) -> bytes:
    """Content address of a raw log line: sha256 of the payload bytes.

    Returns RAW BYTES, not hex. Everything internal compares and stores the
    32-byte form; hex is produced only at the display boundary. Hex doubles
    the memory and the comparison cost for no gain, and at a few million
    records that is real.

    The envelope is deliberately excluded: the same bytes received twice are
    the same record, which is what makes replay idempotent for free.
    """
    return hashlib.sha256(payload).digest()


def hexid(d: bytes) -> str:
    """Display form of a digest."""
    return d.hex()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Channel(IntEnum):
    """How the bytes reached us. Part of the evidentiary envelope: a line
    claiming to be from a firewall that arrived over HTTP from a laptop is
    self-contradicting, and we can only notice if we wrote down how it came."""

    FILE = 0
    SYSLOG_UDP = 1
    SYSLOG_TCP = 2
    SYSLOG_TLS = 3
    HTTP = 4
    REPLAY = 5          # re-derived from the ledger, not newly received

    @property
    def label(self) -> str:
        return _CHANNEL_LABELS[self]


_CHANNEL_LABELS = {
    Channel.FILE: "file",
    Channel.SYSLOG_UDP: "syslog/udp",
    Channel.SYSLOG_TCP: "syslog/tcp",
    Channel.SYSLOG_TLS: "syslog/tls",
    Channel.HTTP: "http",
    Channel.REPLAY: "replay",
}


class Verdict(IntEnum):
    """Outcome of processing one line. Explicit rather than implied by which
    object came back, so counters and dashboards have one thing to group by."""

    MAPPED = 0            # fully understood and normalized
    UNCLAIMED = 1         # no grammar recognised it
    AMBIGUOUS = 2         # more than one grammar claimed it, none convincingly
    EXTRACT_FAILED = 3    # recognised, then extraction blew up
    INVALID = 4           # extracted, but the result is not valid OCSF

    @property
    def label(self) -> str:
        return _VERDICT_LABELS[self]

    @property
    def is_quarantine(self) -> bool:
        return self is not Verdict.MAPPED


_VERDICT_LABELS = {
    Verdict.MAPPED: "mapped",
    Verdict.UNCLAIMED: "unclaimed",
    Verdict.AMBIGUOUS: "ambiguous",
    Verdict.EXTRACT_FAILED: "extract_failed",
    Verdict.INVALID: "invalid",
}


class Disposition(IntEnum):
    """OCSF disposition_id values STRATA emits.

    Vendors have dozens of words for 'blocked'. Collapsing them is the entire
    point of normalization -- but the vendor's own word is evidence, so every
    grammar that uses this table also names a field to keep the original in.
    """

    UNKNOWN = 0
    ALLOWED = 1
    BLOCKED = 2
    DROPPED = 3
    RESET = 8
    OTHER = 99


# ---------------------------------------------------------------------------
# Stage 1 -- what arrived
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class Envelope:
    """Facts about the RECEIPT of a line, as opposed to its content.

    The line itself is attacker-influenced text and cannot be trusted about its
    own origin. This is the part WE observed, so it is the part that can
    contradict a forgery.
    """

    channel: Channel = Channel.FILE
    peer: str = ""                  # address seen at the socket, not claimed in the line
    listener: str = ""              # which listener accepted it, e.g. "udp/514"
    # Defaults to NOW, never to zero. A record that exists was received at some
    # moment, and a zero here silently becomes a 1970 timestamp that fails
    # validation far downstream where the cause is no longer visible.
    received_ns: int = field(default_factory=lambda: __import__("time").time_ns())
    truncated: bool = False         # hit a transport limit; a field may be cut in half

    @staticmethod
    def now(channel: Channel = Channel.FILE, peer: str = "", listener: str = "") -> "Envelope":
        import time
        return Envelope(channel=channel, peer=peer, listener=listener,
                        received_ns=time.time_ns())

    @property
    def received_at(self) -> datetime:
        return datetime.fromtimestamp(self.received_ns / 1e9, tz=timezone.utc)


@dataclass(slots=True)
class Record:
    """One original log line, exactly as received, plus how it arrived.

    This is the unit the ledger stores and the system's source of truth.
    Everything downstream is a derived, disposable view of these.

    `payload` is bytes and stays bytes. Real logs contain sequences that are
    not valid UTF-8 -- a device with failing memory, a non-ASCII hostname, an
    attacker sending binary deliberately. Decoding on receipt and storing the
    result destroys the original irreversibly.
    """

    payload: bytes
    envelope: Envelope
    id: bytes = b""                 # 32-byte digest; filled by __post_init__
    stratum: int = -1               # which segment holds it; -1 until stored
    offset: int = -1                # byte offset within that segment

    def __post_init__(self) -> None:
        if not self.id:
            self.id = digest(self.payload)

    @property
    def hex(self) -> str:
        return self.id.hex()

    def text(self) -> str:
        """A lossy decoded COPY, for parsing only.

        `errors="replace"` guarantees this never raises, so one bad byte can
        never take down the pipeline. The original is untouched in `payload` --
        that separation is the whole point.
        """
        return self.payload.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# Stage 2 -- what we pulled out of it
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Extraction:
    """Flat, typed fields still in the VENDOR's vocabulary.

    Deliberately not yet OCSF. Keeping extraction and mapping apart means
    "we could not read the line" stays distinguishable from "we read it and
    filed it wrong" -- two different bugs with two different fixes.
    """

    grammar_id: str
    grammar_version: str
    fields: dict[str, Any]
    confidence: float = 1.0
    event_ns: int | None = None     # the event's own time, UTC ns; None if absent
    notes: list[str] = field(default_factory=list)   # non-fatal problems


# ---------------------------------------------------------------------------
# Stage 3 -- the product
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Event:
    """An OCSF 1.8 document plus STRATA's provenance envelope.

    `ocsf` holds standard fields only, so anything that speaks OCSF consumes it
    untouched. Everything STRATA-specific lives under `provenance`, so we never
    pollute the standard -- which is what lets the vendor-agnostic claim stand
    up.
    """

    ocsf: dict[str, Any]
    residue: dict[str, Any]         # extracted but unclaimed by any mapping
    provenance: "Provenance"

    def document(self) -> dict[str, Any]:
        """Flattened for outlets. `unmapped` is an OCSF base-class field, so
        the residue goes there under its standard name -- we are using the
        schema, not extending it."""
        doc = dict(self.ocsf)
        doc["unmapped"] = self.residue
        doc["strata"] = self.provenance.document()
        return doc


@dataclass(slots=True)
class Provenance:
    """The chain of custody for one event. This is requirement (d) made real.

    Every field here answers a question an investigator or auditor will ask:
    which bytes produced this, where are they, what read them, how sure was it,
    and has this been re-derived since.
    """

    record_id: bytes
    stratum: int
    grammar_id: str
    grammar_version: str
    confidence: float
    generation: int = 0             # increments on each replay
    coverage: float = 0.0           # share of extracted fields the mapping claimed
    channel: Channel = Channel.FILE
    peer: str = ""
    received_ns: int = 0
    notes: list[str] = field(default_factory=list)

    def document(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "record_id": self.record_id.hex(),
            "stratum": self.stratum,
            "grammar": self.grammar_id,
            "grammar_version": self.grammar_version,
            "confidence": round(self.confidence, 3),
            "generation": self.generation,
            "coverage": round(self.coverage, 3),
            "channel": self.channel.label,
            "peer": self.peer,
            "received": self.received_ns,
        }
        if self.notes:
            d["notes"] = self.notes
        return d


@dataclass(slots=True)
class Rejection:
    """A line STRATA declined to interpret.

    Rejected, never discarded: the bytes are already safe in the ledger. This
    records *why* we declined, and it is the input queue for the Forge -- what
    is rejected today becomes a grammar tomorrow.
    """

    record_id: bytes
    verdict: Verdict
    detail: str = ""
    best_guess: str | None = None
    confidence: float = 0.0

    def document(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id.hex(),
            "verdict": self.verdict.label,
            "detail": self.detail,
            "best_guess": self.best_guess,
            "confidence": round(self.confidence, 3),
        }


# A batch result: what one call to the pipeline produced.
@dataclass(slots=True)
class Outcome:
    events: list[Event] = field(default_factory=list)
    rejects: list[Rejection] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.events) + len(self.rejects)
