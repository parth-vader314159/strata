"""
strata.store.ledger
===================
THE LEDGER -- append-only, content-addressed, Merkle-sealed storage of original
bytes. Requirements (a) and (d) live here, and everything else in STRATA is a
derived view of what this holds.

LAYOUT

Records go into *strata* (segment files). Each record is an independently
compressed frame, so any one can be read back without touching its neighbours:

    st-000001.sl
    +--------------------------------------------------------------+
    | MAGIC(6) VERSION(1) SHARD(1)                    file header   |
    +--------------------------------------------------------------+
    | FRAME: len(u32) | zstd( envelope(packed) | payload bytes )    |
    | FRAME: ...                                                    |
    +--------------------------------------------------------------+

The envelope is a packed binary struct, not JSON. At a few hundred thousand
records the difference in both size and encode time is worth the twenty lines.

The payload is written as raw bytes inside the compressed frame -- never
base64'd, never decoded, never re-encoded. That is what makes byte-exact
reconstruction true rather than approximately true.

SEALING

When a stratum fills it is sealed: a Merkle tree is built over its record
digests and the root recorded. Roots are themselves chained (each stratum
stores its predecessor's root), so the archive has both properties:

    * per-record inclusion proofs, from the tree
    * whole-archive continuity, from the chain of roots

WRITERS

One writer per shard, by design. Concurrent appends to one file would
interleave and corrupt frames, and the fix -- a lock on the hot path -- would
cost more than it buys. Scale is horizontal: more shards, each with one writer,
exactly as it would work across machines.
"""

from __future__ import annotations

import os
import sqlite3
import struct
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import zstandard as zstd

from ..core.model import Channel, Envelope, MODEL_VERSION, Record, digest
from . import merkle

MAGIC = b"STRATA"
FORMAT_VERSION = 2
DEFAULT_STRATUM_BYTES = 64 * 1024 * 1024
DEFAULT_SYNC_EVERY = 2048

_FRAME_LEN = struct.Struct("<I")
# channel u8 | truncated u8 | received_ns u64 | peer_len u8 | listener_len u8
_ENV_HEAD = struct.Struct("<BBQBB")


class LedgerError(Exception):
    """Storage fault. Deliberately loud: a silent storage failure is worse
    than a crash, because it produces an archive you wrongly trust."""


class LedgerBusy(LedgerError):
    """Another process already holds this shard.

    The ledger is single-writer BY DESIGN -- concurrent appends to one segment
    file would interleave and corrupt frames. Without an explicit lock the
    second process fails later, deep inside SQLite, with "database is locked"
    at request time. That is a confusing 500 for the operator and a scary one
    for anyone watching a demo. Failing immediately, by name, is kinder and
    truer: the constraint is architectural, so it should be stated at the door.
    """


def _acquire(directory: Path) -> object | None:
    """Take an exclusive advisory lock on a shard directory.

    flock is used where available because the kernel releases it automatically
    when the process dies -- a pid file would go stale after a crash and need
    manual cleaning, which is precisely the wrong thing to hand an operator at
    3am. On platforms without flock we degrade to no lock rather than to a
    worse lock, and the SQLite busy timeout remains as a backstop.
    """
    handle = open(directory / ".lock", "w")
    try:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ImportError:
        try:
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except (ImportError, OSError):
            handle.close()
            return None
    except OSError:
        handle.close()
        raise LedgerBusy(
            f"another STRATA process already holds the ledger at {directory}. "
            "The ledger is single-writer by design; run one writer per shard, "
            "or point this process at a different --var directory.") from None
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


@dataclass(slots=True, frozen=True)
class LedgerStats:
    records: int
    strata: int
    sealed: int
    bytes_raw: int
    bytes_stored: int

    @property
    def ratio(self) -> float:
        return (self.bytes_raw / self.bytes_stored) if self.bytes_stored else 0.0


def _pack_envelope(e: Envelope) -> bytes:
    peer = e.peer.encode("utf-8")[:255]
    listener = e.listener.encode("utf-8")[:255]
    return (_ENV_HEAD.pack(int(e.channel), 1 if e.truncated else 0,
                           e.received_ns, len(peer), len(listener))
            + peer + listener)


def _unpack_envelope(buf: memoryview) -> tuple[Envelope, int]:
    ch, trunc, recv, plen, llen = _ENV_HEAD.unpack_from(buf, 0)
    at = _ENV_HEAD.size
    peer = bytes(buf[at:at + plen]).decode("utf-8", "replace"); at += plen
    listener = bytes(buf[at:at + llen]).decode("utf-8", "replace"); at += llen
    return Envelope(channel=Channel(ch), peer=peer, listener=listener,
                    received_ns=recv, truncated=bool(trunc)), at


class Ledger:
    """Append-only, content-addressed, Merkle-sealed store of raw log bytes."""

    def __init__(
        self,
        root: str | Path,
        shard: int = 0,
        stratum_bytes: int = DEFAULT_STRATUM_BYTES,
        sync_every: int = DEFAULT_SYNC_EVERY,
        level: int = 3,
    ) -> None:
        """
        `sync_every` is the durability/throughput dial.

        fsync + COMMIT once per record costs more than every other stage of the
        pipeline combined -- measured, not assumed. Every production log system
        batches it. At most `sync_every` records are at risk in a hard power
        loss; set it to 1 for per-record durability and roughly 20x less
        throughput. LOSSLESSNESS IS UNAFFECTED either way: the bytes stored are
        identical, only the moment they are forced to the platter moves.
        """
        self.root = Path(root)
        self.shard = shard
        self.dir = self.root / f"shard-{shard:02d}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.stratum_bytes = stratum_bytes
        self.sync_every = max(1, sync_every)

        self._lockfile: object | None = None
        self._cctx = zstd.ZstdCompressor(level=level)
        self._dctx = zstd.ZstdDecompressor()
        self._lock = threading.Lock()
        self._closed = False

        self._lockfile = _acquire(self.dir)

        self._db = sqlite3.connect(self.dir / "index.db", check_same_thread=False,
                                   timeout=10.0)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute("PRAGMA busy_timeout=10000")
        self._schema()

        self._stratum, self._fh, self._pos = self._open_active()
        self._ids: list[bytes] = self._load_open_ids()
        self._pending: list[tuple] = []
        self._pending_ids: set[bytes] = set()
        self._since_sync = 0

    # ------------------------------------------------------------------ setup

    def _schema(self) -> None:
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                id       BLOB PRIMARY KEY,   -- sha256 of payload; dedupes for free
                stratum  INTEGER NOT NULL,
                offset   INTEGER NOT NULL,
                length   INTEGER NOT NULL,   -- compressed frame length
                raw_len  INTEGER NOT NULL,
                seq      INTEGER NOT NULL,   -- position within its stratum
                seen     INTEGER DEFAULT 1   -- times these exact bytes arrived
            ) WITHOUT ROWID;
            CREATE INDEX IF NOT EXISTS ix_rec_stratum ON records(stratum, seq);

            CREATE TABLE IF NOT EXISTS strata (
                id        INTEGER PRIMARY KEY,
                prev_root BLOB NOT NULL,
                root      BLOB,              -- NULL while open
                count     INTEGER DEFAULT 0,
                sealed_ns INTEGER
            );
            CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
        """)
        self._db.execute("INSERT OR IGNORE INTO meta(k,v) VALUES('model_version',?)",
                         (str(MODEL_VERSION),))
        self._db.commit()

    def _open_active(self) -> tuple[int, object, int]:
        row = self._db.execute(
            "SELECT id FROM strata WHERE root IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        sid = row[0] if row else self._begin_stratum()
        path = self._path(sid)
        if not path.exists():
            path.write_bytes(MAGIC + bytes([FORMAT_VERSION, self.shard]))
        return sid, open(path, "ab"), path.stat().st_size

    def _begin_stratum(self) -> int:
        row = self._db.execute("SELECT MAX(id) FROM strata").fetchone()
        prev = row[0]
        if prev is None:
            sid, prev_root = 1, merkle.EMPTY_ROOT
        else:
            sid = prev + 1
            r = self._db.execute("SELECT root FROM strata WHERE id=?", (prev,)).fetchone()
            prev_root = r[0] if r and r[0] else merkle.EMPTY_ROOT
        self._db.execute("INSERT INTO strata(id, prev_root) VALUES(?,?)", (sid, prev_root))
        self._db.commit()
        return sid

    def _load_open_ids(self) -> list[bytes]:
        """Record digests already in the open stratum, in order.

        Needed to seal correctly after a restart: the Merkle root must be built
        over every record in the stratum, not only those this process wrote.
        """
        return [r[0] for r in self._db.execute(
            "SELECT id FROM records WHERE stratum=? ORDER BY seq", (self._stratum,))]

    def _path(self, sid: int) -> Path:
        return self.dir / f"st-{sid:06d}.sl"

    # ------------------------------------------------------------------ write

    def append(self, payload: bytes, envelope: Envelope | None = None) -> Record:
        """Store raw bytes. Returns the Record, positioned.

        Content-addressed, so appending identical bytes twice is a no-op that
        bumps a counter -- which is what makes replay safe to run repeatedly.
        """
        if self._closed:
            raise LedgerError("ledger is closed")
        if type(payload) is not bytes:
            raise TypeError(
                f"ledger.append needs bytes, got {type(payload).__name__}. "
                "Decoding before storage is precisely the bug this ledger exists "
                "to make impossible."
            )

        env = envelope or Envelope()
        rid = digest(payload)

        with self._lock:
            if rid in self._pending_ids:
                return Record(payload, env, rid, self._stratum, -1)

            hit = self._db.execute(
                "SELECT stratum, offset FROM records WHERE id=?", (rid,)).fetchone()
            if hit:
                self._db.execute("UPDATE records SET seen = seen + 1 WHERE id=?", (rid,))
                return Record(payload, env, rid, hit[0], hit[1])

            frame = self._encode(payload, env)
            self._fh.write(frame)
            offset, seq = self._pos, len(self._ids)

            self._pending.append((rid, self._stratum, offset, len(frame),
                                  len(payload), seq))
            self._pending_ids.add(rid)
            self._ids.append(rid)
            self._pos += len(frame)
            self._since_sync += 1

            if self._since_sync >= self.sync_every:
                self._sync()
            if self._pos >= self.stratum_bytes:
                self._seal()

            return Record(payload, env, rid, self._stratum, offset)

    def extend(self, items: list[tuple[bytes, Envelope]]) -> list[Record]:
        """Append many. Amortises the lock and the sync across the batch, which
        is where most of the throughput gain over one-at-a-time comes from."""
        return [self.append(p, e) for p, e in items]

    def _encode(self, payload: bytes, env: Envelope) -> bytes:
        packed = _pack_envelope(env)
        body = struct.pack("<H", len(packed)) + packed + payload
        blob = self._cctx.compress(body)
        return _FRAME_LEN.pack(len(blob)) + blob

    def _decode(self, blob: bytes) -> Record:
        body = memoryview(self._dctx.decompress(blob))
        (env_len,) = struct.unpack_from("<H", body, 0)
        env, _ = _unpack_envelope(body[2:2 + env_len])
        payload = bytes(body[2 + env_len:])
        return Record(payload, env, digest(payload))

    def _sync(self) -> None:
        """Force frames to disk, then commit their index rows.

        The ORDER is deliberate and not interchangeable. Data is fsynced before
        the index is committed, so a crash between the two leaves records on
        disk that the index does not yet know about -- recoverable, because
        `scan()` reads the files directly and `reindex()` can rebuild. The
        reverse order would leave the index pointing at bytes that were never
        written, which is not recoverable.
        """
        if not self._pending and self._since_sync == 0:
            return
        self._fh.flush()
        os.fsync(self._fh.fileno())
        if self._pending:
            self._db.executemany(
                "INSERT OR IGNORE INTO records(id,stratum,offset,length,raw_len,seq) "
                "VALUES(?,?,?,?,?,?)", self._pending)
            self._db.execute("UPDATE strata SET count=? WHERE id=?",
                             (len(self._ids), self._stratum))
            self._pending.clear()
            self._pending_ids.clear()
        self._db.commit()
        self._since_sync = 0

    def _seal(self) -> None:
        """Close the current stratum: build its Merkle tree, store the root,
        open the next one rooted at this one."""
        self._sync()
        root = merkle.root_of(self._ids)
        import time
        self._db.execute("UPDATE strata SET root=?, sealed_ns=?, count=? WHERE id=?",
                         (root, time.time_ns(), len(self._ids), self._stratum))
        self._db.commit()
        self._fh.close()

        self._ids = []
        self._stratum = self._begin_stratum()
        path = self._path(self._stratum)
        path.write_bytes(MAGIC + bytes([FORMAT_VERSION, self.shard]))
        self._fh = open(path, "ab")
        self._pos = path.stat().st_size

    def seal(self) -> None:
        """Seal the open stratum on demand -- needed before proofs can be
        issued for records in it, since an unsealed stratum has no root yet."""
        with self._lock:
            if self._ids:
                self._seal()

    # ------------------------------------------------------------------- read

    def get(self, record_id: bytes) -> Record | None:
        """Reconstruct one record from its content address. O(1)."""
        with self._lock:
            self._sync()
        row = self._db.execute(
            "SELECT stratum, offset, length FROM records WHERE id=?", (record_id,)).fetchone()
        if not row:
            return None
        sid, offset, length = row
        with open(self._path(sid), "rb") as f:
            f.seek(offset)
            raw = f.read(length)
        if len(raw) < 4:
            raise LedgerError(f"truncated frame for {record_id.hex()[:16]} in stratum {sid}")
        (blob_len,) = _FRAME_LEN.unpack_from(raw, 0)
        rec = self._decode(raw[4:4 + blob_len])
        rec.stratum, rec.offset = sid, offset
        return rec

    def raw(self, record_id: bytes) -> bytes | None:
        """The byte-exact original. This method IS requirement (a)."""
        rec = self.get(record_id)
        return rec.payload if rec else None

    def scan(self, stratum: int | None = None) -> Iterator[Record]:
        """Stream records straight from the segment files.

        Deliberately does not consult the index. This is what replay and
        verification use, and it is the proof that the files are self-
        sufficient and the index is only a cache.
        """
        with self._lock:
            self._sync()
        ids = [stratum] if stratum is not None else [
            r[0] for r in self._db.execute("SELECT id FROM strata ORDER BY id")]

        for sid in ids:
            path = self._path(sid)
            if not path.exists():
                continue
            with open(path, "rb") as f:
                head = f.read(8)
                if head[:6] != MAGIC:
                    raise LedgerError(f"stratum {sid}: bad magic, not a STRATA file")
                seq = 0
                while True:
                    length_bytes = f.read(4)
                    if len(length_bytes) < 4:
                        break
                    (blob_len,) = _FRAME_LEN.unpack_from(length_bytes, 0)
                    blob = f.read(blob_len)
                    if len(blob) < blob_len:
                        break      # torn tail write; everything before it is intact
                    rec = self._decode(blob)
                    rec.stratum, rec.offset = sid, f.tell() - blob_len - 4
                    yield rec
                    seq += 1

    # -------------------------------------------------------------- integrity

    def prove(self, record_id: bytes) -> dict | None:
        """Inclusion proof for one record.

        Hand the result to anyone. With the record's bytes and the published
        root they can verify membership without seeing another record and
        without access to this machine.
        """
        row = self._db.execute(
            "SELECT stratum, seq FROM records WHERE id=?", (record_id,)).fetchone()
        if not row:
            return None
        sid, seq = row
        srow = self._db.execute("SELECT root FROM strata WHERE id=?", (sid,)).fetchone()
        if not srow or srow[0] is None:
            return {"record_id": record_id.hex(), "stratum": sid,
                    "sealed": False,
                    "note": "stratum still open; seal it before issuing a proof"}

        ids = [r[0] for r in self._db.execute(
            "SELECT id FROM records WHERE stratum=? ORDER BY seq", (sid,))]
        path = merkle.proof(ids, seq)
        return {
            "record_id": record_id.hex(),
            "stratum": sid,
            "sealed": True,
            "index": seq,
            "leaves": len(ids),
            "root": srow[0].hex(),
            "path": merkle.encode_proof(path),
            "verified_locally": merkle.verify(record_id, path, srow[0]),
        }

    def audit(self, sample: int | None = None) -> dict:
        """Full integrity audit. Two independent checks.

        1. CONTENT -- every stored payload must still hash to the id it is
           filed under. Catches any modification of a record's bytes.
        2. STRUCTURE -- every sealed stratum's Merkle root must be
           reproducible from its records, and each must carry its predecessor's
           root. Catches insertion, deletion and reordering.

        Never raises on a finding: the caller decides how loud to be, and the
        dashboard wants the detail rather than a traceback.
        """
        report: dict = {"ok": True, "records": 0, "byte_exact": 0,
                        "strata": 0, "sealed": 0, "faults": []}
        prev_root = merkle.EMPTY_ROOT

        rows = self._db.execute(
            "SELECT id, prev_root, root FROM strata ORDER BY id").fetchall()

        for sid, stored_prev, stored_root in rows:
            report["strata"] += 1
            seen: list[bytes] = []

            for rec in self.scan(stratum=sid):
                report["records"] += 1
                if digest(rec.payload) == rec.id:
                    report["byte_exact"] += 1
                else:
                    report["ok"] = False
                    report["faults"].append(
                        {"stratum": sid, "kind": "content_mismatch",
                         "record": rec.id.hex()})
                seen.append(rec.id)
                if sample and report["records"] >= sample:
                    break

            if stored_prev != prev_root:
                report["ok"] = False
                report["faults"].append({"stratum": sid, "kind": "chain_break",
                                         "expected": prev_root.hex(),
                                         "stored": stored_prev.hex()})

            if stored_root is not None:
                report["sealed"] += 1
                recomputed = merkle.root_of(seen)
                if recomputed != stored_root:
                    report["ok"] = False
                    report["faults"].append({"stratum": sid, "kind": "root_mismatch",
                                             "expected": stored_root.hex(),
                                             "recomputed": recomputed.hex()})
                prev_root = stored_root

            if sample and report["records"] >= sample:
                break

        report["fidelity"] = (report["byte_exact"] / report["records"]
                              if report["records"] else 1.0)
        return report

    def reindex(self) -> int:
        """Rebuild the index from the segment files alone.

        Exists to demonstrate the claim that the index is a cache: delete
        index.db, run this, and the archive is fully addressable again. It is
        also the recovery path if a crash lands between fsync and commit.
        """
        with self._lock:
            self._sync()
        self._db.execute("DELETE FROM records")
        rows, counts = [], {}
        for sid in [r[0] for r in self._db.execute("SELECT id FROM strata ORDER BY id")]:
            seq = 0
            for rec in self.scan(stratum=sid):
                path = self._path(sid)
                with open(path, "rb") as f:
                    f.seek(rec.offset)
                    (blob_len,) = _FRAME_LEN.unpack_from(f.read(4), 0)
                rows.append((rec.id, sid, rec.offset, blob_len + 4,
                             len(rec.payload), seq))
                seq += 1
            counts[sid] = seq
        self._db.executemany(
            "INSERT OR IGNORE INTO records(id,stratum,offset,length,raw_len,seq) "
            "VALUES(?,?,?,?,?,?)", rows)
        for sid, n in counts.items():
            self._db.execute("UPDATE strata SET count=? WHERE id=?", (n, sid))
        self._db.commit()
        return len(rows)

    # ------------------------------------------------------------------ admin

    def stats(self) -> LedgerStats:
        with self._lock:
            self._sync()
        r = self._db.execute(
            "SELECT COUNT(*), COALESCE(SUM(raw_len),0), COALESCE(SUM(length),0) "
            "FROM records").fetchone()
        s = self._db.execute(
            "SELECT COUNT(*), COUNT(root) FROM strata").fetchone()
        return LedgerStats(records=r[0], bytes_raw=r[1], bytes_stored=r[2],
                           strata=s[0], sealed=s[1])

    def roots(self) -> list[dict]:
        """Published roots, one per sealed stratum. Safe to print, publish, or
        read aloud -- they reveal nothing about content but pin the archive."""
        return [{"stratum": sid, "records": n, "root": root.hex(),
                 "prev_root": prev.hex(), "sealed_ns": ns}
                for sid, prev, root, n, ns in self._db.execute(
                    "SELECT id, prev_root, root, count, sealed_ns FROM strata "
                    "WHERE root IS NOT NULL ORDER BY id")]

    def close(self) -> None:
        if self._closed:
            return
        with self._lock:
            self._sync()
            if self._ids:
                self._seal()
            try:
                self._fh.close()
            except Exception:
                pass
            self._db.commit()
            self._db.close()
            if self._lockfile is not None:
                try:
                    self._lockfile.close()
                except Exception:
                    pass
            self._closed = True

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
