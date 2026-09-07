"""
strata.io.outlets
=================
Where normalized events go. Requirement (g).

Two audiences with genuinely different needs, which is why there is more than
one outlet:

  A SIEM wants a STREAM, one event at a time, in a format it already parses --
  so we emit CEF over syslog. (Yes: we normalize logs and then re-serialize to
  a log format. That is what integration means. The SIEM already speaks CEF,
  so meeting it there is cheaper and more reliable than making it learn OCSF.)

  A DATA LAKE wants COLUMNS -- so we emit Parquet, partitioned by date and
  source. Roughly ten times smaller than JSON, and it is what every ML tool
  reads natively, which is most of requirement (h) satisfied by a file format.

Every outlet is bounded and isolated. A dead downstream must never apply
backpressure all the way to ingest, because that turns "the SIEM is slow" into
"the SOC is blind".
"""

from __future__ import annotations

import json
import socket
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.model import Event


class Outlet(ABC):
    name = "outlet"

    def __init__(self) -> None:
        self.written = 0
        self.failures = 0

    @abstractmethod
    def write_many(self, events: list[Event]) -> None: ...

    def flush(self) -> None: ...

    def close(self) -> None:
        self.flush()

    def status(self) -> dict[str, Any]:
        return {"outlet": self.name, "written": self.written, "failures": self.failures}


class NDJSON(Outlet):
    """One JSON document per line. The universal fallback, and the easiest
    thing to eyeball while developing."""

    name = "ndjson"

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8", buffering=1 << 16)

    def write_many(self, events: list[Event]) -> None:
        lines = []
        for ev in events:
            try:
                lines.append(json.dumps(ev.document(), default=str, separators=(",", ":")))
            except (TypeError, ValueError):
                self.failures += 1
        if lines:
            self._fh.write("\n".join(lines) + "\n")
            self.written += len(lines)

    def flush(self) -> None:
        self._fh.flush()

    def close(self) -> None:
        self.flush()
        self._fh.close()


class Parquet(Outlet):
    """The data lake. Batched, partitioned by date and source.

    SCHEMA DESIGN NOTE. Flat typed columns for the fields a SOC actually
    filters on; the full OCSF document alongside as JSON text. The alternative
    -- one Arrow column per possible OCSF field -- either drops fields or
    explodes into thousands of mostly-null columns, because OCSF documents are
    sparse and differ per source. This way the common queries are columnar and
    fast, nothing is lost, and DuckDB reads the JSON column fine when a query
    needs a rare field.
    """

    name = "parquet"

    COLUMNS: list[tuple[str, str]] = [
        ("time", "int64"), ("class_uid", "int32"), ("activity_id", "int32"),
        ("disposition_id", "int32"), ("severity_id", "int32"),
        ("src_ip", "string"), ("src_port", "int32"),
        ("dst_ip", "string"), ("dst_port", "int32"),
        ("protocol", "string"), ("app", "string"),
        ("bytes_total", "int64"), ("bytes_in", "int64"), ("bytes_out", "int64"),
        ("user", "string"), ("rule", "string"), ("device", "string"),
        ("vendor", "string"), ("product", "string"),
        ("grammar", "string"), ("grammar_version", "string"),
        ("confidence", "float"), ("coverage", "float"),
        ("record_id", "string"), ("stratum", "int32"), ("generation", "int32"),
        ("ocsf", "string"), ("unmapped", "string"),
    ]

    def __init__(self, root: str | Path, batch: int = 4096) -> None:
        super().__init__()
        import pyarrow as pa
        self._pa = pa
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.batch = batch
        types = {"int64": pa.int64(), "int32": pa.int32(),
                 "string": pa.string(), "float": pa.float32()}
        self.schema = pa.schema([(n, types[t]) for n, t in self.COLUMNS])
        self._buf: list[dict] = []

    @staticmethod
    def _dig(doc: dict, *path: str) -> Any:
        node: Any = doc
        for key in path:
            if type(node) is not dict:
                return None
            node = node.get(key)
            if node is None:
                return None
        return node

    @staticmethod
    def _int(v: Any) -> int | None:
        if type(v) is int:
            return v
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def write_many(self, events: list[Event]) -> None:
        d = self._dig
        for ev in events:
            o, p = ev.ocsf, ev.provenance
            self._buf.append({
                "time": self._int(o.get("time")),
                "class_uid": self._int(o.get("class_uid")),
                "activity_id": self._int(o.get("activity_id")),
                "disposition_id": self._int(o.get("disposition_id")),
                "severity_id": self._int(o.get("severity_id")),
                "src_ip": d(o, "src_endpoint", "ip"),
                "src_port": self._int(d(o, "src_endpoint", "port")),
                "dst_ip": d(o, "dst_endpoint", "ip"),
                "dst_port": self._int(d(o, "dst_endpoint", "port")),
                "protocol": d(o, "connection_info", "protocol_name"),
                "app": o.get("app_name"),
                "bytes_total": self._int(d(o, "traffic", "bytes")),
                "bytes_in": self._int(d(o, "traffic", "bytes_in")),
                "bytes_out": self._int(d(o, "traffic", "bytes_out")),
                "user": d(o, "actor", "user", "name"),
                "rule": d(o, "firewall_rule", "name"),
                "device": d(o, "device", "hostname"),
                "vendor": d(o, "metadata", "product", "vendor_name"),
                "product": d(o, "metadata", "product", "name"),
                "grammar": p.grammar_id,
                "grammar_version": p.grammar_version,
                "confidence": p.confidence,
                "coverage": p.coverage,
                "record_id": p.record_id.hex(),
                "stratum": p.stratum,
                "generation": p.generation,
                "ocsf": json.dumps(o, default=str, separators=(",", ":")),
                "unmapped": json.dumps(ev.residue, default=str, separators=(",", ":")),
            })
        self.written += len(events)
        if len(self._buf) >= self.batch:
            self.flush()

    def flush(self) -> None:
        if not self._buf:
            return
        import pyarrow.parquet as pq
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        source = (self._buf[0].get("grammar") or "unknown").split(".")[0]
        target = self.root / f"date={day}" / f"source={source}"
        target.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%H%M%S%f")
        table = self._pa.Table.from_pylist(self._buf, schema=self.schema)
        pq.write_table(table, target / f"part-{stamp}.parquet", compression="zstd")
        self._buf.clear()


class CEF(Outlet):
    """CEF over syslog, for the SIEM.

    ESCAPING IS NOT DECORATION. An unescaped '=' or '|' in a value silently
    corrupts every field after it in the receiving SIEM -- the exact class of
    silent misparse this whole project exists to eliminate. Committing it on
    the way out would be embarrassing.
    """

    name = "cef"

    EXTENSION = {
        "src": ("src_endpoint", "ip"), "spt": ("src_endpoint", "port"),
        "dst": ("dst_endpoint", "ip"), "dpt": ("dst_endpoint", "port"),
        "proto": ("connection_info", "protocol_name"),
        "in": ("traffic", "bytes_in"), "out": ("traffic", "bytes_out"),
        "suser": ("actor", "user", "name"),
        "deviceInboundInterface": ("src_endpoint", "interface_name"),
    }

    def __init__(self, path: str | Path | None = None,
                 host: str | None = None, port: int = 514) -> None:
        super().__init__()
        self.path = Path(path) if path else None
        self.host, self.port = host, port
        self._fh = None
        self._sock = None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self.path, "a", encoding="utf-8", buffering=1 << 16)
        if host:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    @staticmethod
    def _header(v: Any) -> str:
        return str(v).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")

    @staticmethod
    def _ext(v: Any) -> str:
        return (str(v).replace("\\", "\\\\").replace("=", "\\=")
                .replace("\n", "\\n").replace("\r", ""))

    def _render(self, ev: Event) -> str:
        o, p = ev.ocsf, ev.provenance
        dig = Parquet._dig
        head = "|".join([
            "CEF:0",
            self._header(dig(o, "metadata", "product", "vendor_name") or "Unknown"),
            self._header(dig(o, "metadata", "product", "name") or "Unknown"),
            self._header(p.grammar_version),
            self._header(o.get("class_uid", 0)),
            self._header(o.get("activity_name") or p.grammar_id),
            self._header(o.get("severity_id", 1)),
        ])
        parts = [f"rt={o.get('time', '')}"]
        for key, path in self.EXTENSION.items():
            value = dig(o, *path)
            if value is not None:
                parts.append(f"{key}={self._ext(value)}")
        act = o.get("disposition_orig") or o.get("disposition_id")
        if act is not None:
            parts.append(f"act={self._ext(act)}")
        # Traceability survives the hop into the SIEM: requirement (d) does not
        # stop at our boundary.
        parts.append(f"strataRecordId={p.record_id.hex()}")
        return f"{head}|{' '.join(parts)}"

    def write_many(self, events: list[Event]) -> None:
        lines = []
        for ev in events:
            try:
                lines.append(self._render(ev))
            except Exception:
                self.failures += 1
        if not lines:
            return
        if self._fh:
            self._fh.write("\n".join(lines) + "\n")
        if self._sock and self.host:
            for line in lines:
                try:
                    self._sock.sendto(f"<134>{line}".encode()[:65000], (self.host, self.port))
                except OSError:
                    self.failures += 1
        self.written += len(lines)

    def flush(self) -> None:
        if self._fh:
            self._fh.flush()

    def close(self) -> None:
        self.flush()
        if self._fh:
            self._fh.close()
        if self._sock:
            self._sock.close()


class Memory(Outlet):
    """Keeps the most recent N events in RAM for the dashboard.

    Bounded on purpose: an unbounded buffer behind a live UI is a slow memory
    leak that only shows up during a long demo.
    """

    name = "memory"

    def __init__(self, capacity: int = 2000) -> None:
        super().__init__()
        from collections import deque
        self.buffer: deque = deque(maxlen=capacity)

    def write_many(self, events: list[Event]) -> None:
        self.buffer.extend(events)
        self.written += len(events)

    def recent(self, limit: int = 100, grammar: str | None = None) -> list[Event]:
        out = []
        for ev in reversed(self.buffer):
            if grammar and ev.provenance.grammar_id != grammar:
                continue
            out.append(ev)
            if len(out) >= limit:
                break
        return out
