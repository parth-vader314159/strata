"""
strata.io.intake
================
The only component that touches the outside world. Requirement (b), and the
whole of the security boundary.

Everything here assumes the input is hostile, because it is. Syslog over UDP
has no authentication of any kind: anyone who can route a packet to port 514
can write whatever they like into the organisation's evidence. So the controls
are not extras bolted onto an ingest routine -- they ARE the component.

  admission list   only known device addresses are accepted
  token bucket     one flooding source cannot starve the others, so
                   "attacker makes noise" does not become "SOC goes blind"
  hard size cap    absurd lines are refused before any regex sees them
  truncation flag  RFC 3164 caps at 1024 bytes, so a field may be cut in
                   half; the parser is TOLD rather than left to guess
  observed peer    we record the address we actually saw, which is the one
                   part of the record a forged line cannot control

Rejections are counted and surfaced, never swallowed. A silent drop is the
difference between having the logs and believing you have the logs.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

from ..core.model import Channel, Envelope

MAX_DATAGRAM = 65535
RFC3164_LIMIT = 1024

Handler = Callable[[bytes, Envelope], None]


class Bucket:
    """Per-source token bucket. No dependencies, no background timer -- tokens
    are computed from elapsed time on demand, so an idle source costs nothing."""

    __slots__ = ("rate", "burst", "_tokens", "_last")

    def __init__(self, rate: float, burst: float) -> None:
        self.rate = rate
        self.burst = burst
        self._tokens = burst
        self._last = time.monotonic()

    def take(self, n: float = 1.0) -> bool:
        now = time.monotonic()
        self._tokens = min(self.burst, self._tokens + (now - self._last) * self.rate)
        self._last = now
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False


@dataclass(slots=True)
class IntakeStats:
    accepted: int = 0
    refused_unknown_source: int = 0
    refused_rate_limit: int = 0
    refused_oversize: int = 0
    truncated: int = 0
    by_peer: dict[str, int] = field(default_factory=dict)

    def snapshot(self) -> dict:
        return {
            "accepted": self.accepted,
            "refused_unknown_source": self.refused_unknown_source,
            "refused_rate_limit": self.refused_rate_limit,
            "refused_oversize": self.refused_oversize,
            "truncated": self.truncated,
            "sources": len(self.by_peer),
            "top_sources": dict(sorted(self.by_peer.items(),
                                       key=lambda kv: -kv[1])[:10]),
        }


class Gate:
    """Admission control, shared by every listener."""

    def __init__(self, allow: set[str] | None = None, rate: float = 50_000.0,
                 burst: float = 100_000.0, max_bytes: int = MAX_DATAGRAM) -> None:
        # An empty allow-list means accept everything. That is right for a lab
        # and wrong for production, so /api/health reports which mode is live
        # rather than letting it be discovered later.
        self.allow = allow or set()
        self.rate, self.burst = rate, burst
        self.max_bytes = max_bytes
        self.buckets: dict[str, Bucket] = {}
        self.stats = IntakeStats()

    @property
    def open_to_all(self) -> bool:
        return not self.allow

    def admit(self, peer: str, payload: bytes) -> bool:
        if self.allow and peer not in self.allow:
            self.stats.refused_unknown_source += 1
            return False
        if len(payload) > self.max_bytes:
            self.stats.refused_oversize += 1
            return False
        bucket = self.buckets.get(peer)
        if bucket is None:
            bucket = self.buckets[peer] = Bucket(self.rate, self.burst)
        if not bucket.take():
            self.stats.refused_rate_limit += 1
            return False
        self.stats.accepted += 1
        self.stats.by_peer[peer] = self.stats.by_peer.get(peer, 0) + 1
        return True

    def envelope(self, peer: str, payload: bytes, channel: Channel,
                 listener: str) -> Envelope:
        truncated = (len(payload) >= RFC3164_LIMIT
                     and channel in (Channel.SYSLOG_UDP, Channel.SYSLOG_TCP))
        if truncated:
            self.stats.truncated += 1
        return Envelope(channel=channel, peer=peer, listener=listener,
                        received_ns=time.time_ns(), truncated=truncated)


# ---------------------------------------------------------------------------
# File intake -- the offline path, and what the demo and tests use
# ---------------------------------------------------------------------------

def read_lines(path: str | Path, chunk: int = 1 << 20) -> Iterator[bytes]:
    """Yield one line at a time AS BYTES.

    Opened in binary mode deliberately. A text-mode read decodes, and decoding
    a log file that contains invalid UTF-8 either raises or silently
    substitutes replacement characters -- destroying the original before it
    ever reaches the ledger. This one `"rb"` is requirement (a) at the front
    door.
    """
    with open(path, "rb") as fh:
        remainder = b""
        while True:
            block = fh.read(chunk)
            if not block:
                break
            lines = (remainder + block).split(b"\n")
            remainder = lines.pop()
            for line in lines:
                stripped = line.rstrip(b"\r")
                if stripped:
                    yield stripped
        if remainder.strip():
            yield remainder.rstrip(b"\r")


# ---------------------------------------------------------------------------
# Network listeners
# ---------------------------------------------------------------------------

class _UDP(asyncio.DatagramProtocol):
    def __init__(self, gate: Gate, handler: Handler, listener: str) -> None:
        self.gate, self.handler, self.listener = gate, handler, listener

    def datagram_received(self, data: bytes, addr) -> None:
        peer = addr[0]
        if not self.gate.admit(peer, data):
            return
        env = self.gate.envelope(peer, data, Channel.SYSLOG_UDP, self.listener)
        self.handler(data.rstrip(b"\r\n"), env)

    def error_received(self, exc) -> None:
        pass          # an ICMP unreachable must not kill the listener


async def listen_udp(host: str, port: int, gate: Gate, handler: Handler):
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _UDP(gate, handler, f"udp/{port}"), local_addr=(host, port))
    return transport


async def listen_tcp(host: str, port: int, gate: Gate, handler: Handler):
    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        addr = peer[0] if peer else "?"
        try:
            while True:
                try:
                    # readuntil with a limit, never readline: a client sending a
                    # gigabyte without a newline must not exhaust memory.
                    line = await reader.readuntil(b"\n")
                except asyncio.LimitOverrunError:
                    await reader.read(MAX_DATAGRAM)
                    gate.stats.refused_oversize += 1
                    continue
                except asyncio.IncompleteReadError as exc:
                    line = exc.partial
                    if not line:
                        break
                payload = line.rstrip(b"\r\n")
                if payload and gate.admit(addr, payload):
                    handler(payload, gate.envelope(addr, payload,
                                                   Channel.SYSLOG_TCP, f"tcp/{port}"))
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            writer.close()

    return await asyncio.start_server(serve, host, port, limit=MAX_DATAGRAM)
