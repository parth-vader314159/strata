"""
strata.app.cli
==============
Command line. Every claim STRATA makes has a command that demonstrates it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from ..core.model import Channel, Envelope, Event, digest
from ..dev.synth import Corpus
from ..flow.pipeline import Auditor, Pipeline, Rewind
from ..io.intake import Gate, read_lines
from ..io.outlets import CEF, NDJSON, Memory, Parquet
from ..learn.forge import Forge
from ..parse.grammar import Library
from ..store.ledger import Ledger

ROOT = Path(__file__).resolve().parents[2]
GRAMMARS = ROOT / "grammars"
VAR = ROOT / "var"

# ---------------------------------------------------------------------------
# terminal helpers
# ---------------------------------------------------------------------------

_TTY = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(text: str, code: str = "36") -> str:
    return f"\033[{code}m{text}\033[0m" if _TTY else text


def head(text: str) -> None:
    print(c(f"\n{text}", "1;36"))


def kv(label: str, value: object, width: int = 22) -> None:
    print(f"  {label:<{width}} {value}")


def rule(width: int = 66) -> None:
    print(c("  " + "─" * width, "2;37") if _TTY else "  " + "-" * width)


def build(outlets: bool = True, var: Path | None = None) -> tuple[Pipeline, Ledger]:
    base = var or VAR
    ledger = Ledger(base / "ledger")
    library = Library(GRAMMARS)
    sinks = []
    if outlets:
        sinks = [Parquet(base / "lake"),
                 NDJSON(base / "out" / "events.ndjson"),
                 CEF(path=base / "out" / "siem.cef"),
                 Memory(capacity=4000)]
    return Pipeline(ledger, library, sinks), ledger


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def cmd_check(args) -> int:
    """Environment and grammar health."""
    library = Library(GRAMMARS)
    from ..parse.compiler import compile_all
    compiled, bad = compile_all(library.all())

    head("STRATA — environment check")
    kv("python", sys.version.split()[0])
    for module, optional in (("zstandard", False), ("pyarrow", False),
                             ("pydantic", False), ("yaml", False),
                             ("fastapi", True), ("uvicorn", True), ("duckdb", True)):
        try:
            __import__(module)
            kv(module, c("ok", "32"))
        except ImportError:
            kv(module, c("missing" + (" (optional)" if optional else ""),
                         "33" if optional else "31"))

    head("grammars")
    kv("loaded", f"{len(library)} files, {len(compiled)} compiled")
    for family, ids in library.by_family().items():
        kv(f"  {family}", ", ".join(ids), 20)

    problems = {**library.errors, **bad}
    if problems:
        print(c(f"\n  {len(problems)} PROBLEM(S):", "1;31"))
        for name, err in problems.items():
            print(f"    {c(name, '31')}: {err[:180]}")
        return 1
    print(c("\n  all grammars valid and compiled", "1;32"))
    return 0


def cmd_generate(args) -> int:
    info = Corpus(seed=args.seed).write(args.out, args.count, messy=not args.clean)
    print(json.dumps(info, indent=2))
    return 0


def cmd_ingest(args) -> int:
    pipe, ledger = build()
    env = Envelope(channel=Channel.FILE, peer="localhost", listener="file")
    t0 = time.perf_counter()
    metrics = pipe.drain(read_lines(args.path), env, limit=args.limit)
    elapsed = time.perf_counter() - t0

    snap = metrics.snapshot()
    head("ingest")
    kv("lines", f"{snap['received']:,}")
    kv("normalized", f"{snap['mapped']:,}  ({snap['map_rate']:.2%})")
    kv("quarantined", f"{snap['rejected']:,}  {snap['by_verdict']}")
    kv("throughput", c(f"{snap['received']/elapsed:,.0f} events/sec", "1;32"))
    rule()
    for gid, n in list(snap["by_grammar"].items())[:12]:
        bar = "█" * max(1, round(28 * n / max(snap["by_grammar"].values())))
        print(f"  {gid:<26} {c(bar, '36')} {n:>7,}")
    pipe.close()
    ledger.close()
    return 0


def cmd_audit(args) -> int:
    _, ledger = build(outlets=False)
    report = Auditor(ledger).run(sample=args.sample or None)
    head("integrity audit")
    kv("records checked", f"{report['records']:,}")
    kv("byte-exact", f"{report['byte_exact']:,}")
    kv("strata", f"{report['strata']} ({report['sealed']} sealed)")
    ok = report["ok"] and report["fidelity"] == 1.0
    rule()
    kv("FIDELITY", c(f"{report['fidelity']:.6%}", "1;32" if ok else "1;31"))
    kv("MERKLE + CHAIN", c(report["verdict"], "1;32" if report["ok"] else "1;31"))
    if report["faults"]:
        print(c(f"\n  {len(report['faults'])} FAULT(S):", "1;31"))
        for fault in report["faults"][:10]:
            print(f"    {fault}")
    ledger.close()
    return 0 if ok else 1


def cmd_prove(args) -> int:
    """Merkle inclusion proof for one record."""
    _, ledger = build(outlets=False)
    try:
        rid = bytes.fromhex(args.record_id)
    except ValueError:
        print(c("record id must be 64 hex characters", "31"))
        return 2
    proof = ledger.prove(rid)
    if proof is None:
        print(c("no such record", "31"))
        ledger.close()
        return 1
    head("merkle inclusion proof")
    kv("record", proof["record_id"][:32] + "…")
    kv("stratum", proof["stratum"])
    if not proof.get("sealed"):
        kv("status", c(proof.get("note", "unsealed"), "33"))
        ledger.close()
        return 1
    kv("leaves in stratum", f"{proof['leaves']:,}")
    kv("proof size", f"{len(proof['path'])} sibling hashes")
    kv("root", proof["root"][:32] + "…")
    kv("verified", c("YES", "1;32") if proof["verified_locally"] else c("NO", "1;31"))
    print(c("\n  This proof plus the record and the published root is enough for", "2;37"))
    print(c("  anyone to verify membership — with no access to this machine and", "2;37"))
    print(c("  without learning anything about any other record.", "2;37"))
    if args.json:
        print("\n" + json.dumps(proof, indent=2))
    ledger.close()
    return 0


def cmd_rewind(args) -> int:
    pipe, ledger = build(outlets=not args.commit is False)
    result = Rewind(pipe).run(generation=args.generation, limit=args.limit or None,
                              dry_run=not args.commit)
    head("rewind" + ("" if args.commit else " (dry run)"))
    kv("records replayed", f"{result['records']:,}")
    kv("re-derived", f"{result['remapped']:,}")
    kv("still quarantined", f"{result['still_rejected']:,}")
    kv("generation", result["generation"])
    pipe.close()
    ledger.close()
    return 0


def cmd_forge(args) -> int:
    text = Path(args.path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    proposal = Forge().propose(lines, args.id, args.vendor, args.product)
    r = proposal.report()

    head("forge — grammar proposal")
    kv("sample lines", r["induction"]["lines"])
    kv("structure", r["induction"]["shape"])
    kv("fields found", r["fields_discovered"])
    kv("auto-mapped", f"{r['fields_mapped']}  ({r['coverage']:.0%})")
    kv("valid grammar", c("yes", "1;32") if r["valid"] else c(f"no — {r['error']}", "1;31"))
    if r["unmapped"]:
        kv("needs a human", ", ".join(r["unmapped"][:10]))
    for note in r["notes"]:
        print(c(f"  note: {note}", "33"))

    rule()
    print(proposal.yaml)

    if args.write:
        if not proposal.valid:
            print(c("refusing to write an invalid grammar", "31"))
            return 1
        target = GRAMMARS / f"{args.id}.yaml"
        target.write_text(proposal.yaml, encoding="utf-8")
        print(c(f"written to grammars/{args.id}.yaml — reload to activate", "1;32"))
    return 0


def _bench_shard(payloads: list[bytes], directory: str) -> tuple[int, float]:
    """One worker: its own ledger shard, its own pipeline.

    Sharding rather than sharing is the design, not a benchmark trick. The
    ledger is single-writer because concurrent appends to one segment would
    interleave and corrupt frames, so horizontal scale comes from more shards
    -- exactly as it would across machines.
    """
    from ..flow.pipeline import Pipeline as P
    from ..parse.grammar import Library as L
    from ..store.ledger import Ledger as Led
    led = Led(directory)
    pipe = P(led, L(GRAMMARS), [])
    env = Envelope(channel=Channel.FILE, peer="bench")
    t0 = time.perf_counter()
    for i in range(0, len(payloads), 512):
        pipe.submit_batch([(p, env) for p in payloads[i:i + 512]])
    elapsed = time.perf_counter() - t0
    led.close()
    return len(payloads), elapsed


def cmd_bench(args) -> int:
    import multiprocessing as mp
    import tempfile

    corpus = [s.payload for s in Corpus(seed=99).stream(args.count)]

    with tempfile.TemporaryDirectory() as tmp:
        if args.workers > 1:
            chunks = [corpus[i::args.workers] for i in range(args.workers)]
            t0 = time.perf_counter()
            with mp.Pool(args.workers) as pool:
                results = pool.starmap(
                    _bench_shard,
                    [(chunk, f"{tmp}/shard-{i}") for i, chunk in enumerate(chunks)])
            wall = time.perf_counter() - t0
            per = [round(n / e) for n, e in results]
            eps = args.count / wall
            scaling = eps / sum(per) if sum(per) else 0.0
        else:
            n, wall = _bench_shard(corpus, f"{tmp}/shard-0")
            eps = n / wall
            per, scaling = [round(eps)], 1.0

    head(f"throughput — {args.workers} worker(s)")
    kv("events", f"{args.count:,}")
    kv("wall clock", f"{wall:.2f}s")
    kv("throughput", c(f"{eps:,.0f} events/sec", "1;32"))
    if args.workers > 1:
        kv("per worker", ", ".join(f"{p:,}" for p in per))
        kv("scaling efficiency", f"{scaling:.1%}")
    rule()
    kv("1 billion/day needs", f"11,574 eps sustained")
    kv("this configuration", f"{eps * 86400 / 1e9:.2f} billion/day")
    kv("nodes for 1B/day", f"{max(1, 11574 / eps):.2f}")
    if args.json:
        print(json.dumps({"events": args.count, "seconds": round(wall, 3),
                          "eps": round(eps), "workers": args.workers,
                          "per_worker": per, "scaling": round(scaling, 3)}, indent=2))
    return 0


def cmd_query(args) -> int:
    try:
        import duckdb
    except ImportError:
        print("duckdb is not installed:  pip install duckdb")
        return 1
    lake = VAR / "lake"
    if not any(lake.rglob("*.parquet")):
        print("no lake yet — run:  strata demo")
        return 1
    con = duckdb.connect()
    con.execute(f"CREATE VIEW events AS SELECT * FROM read_parquet('{lake}/**/*.parquet')")
    print(con.execute(args.sql).df().to_string(index=False))
    return 0


def cmd_serve(args) -> int:
    import asyncio
    from ..io.intake import listen_tcp, listen_udp

    pipe, ledger = build()
    gate = Gate(rate=args.rate)
    pending: list[tuple[bytes, Envelope]] = []

    def handle(payload: bytes, env: Envelope) -> None:
        pending.append((payload, env))
        if len(pending) >= pipe.batch_size:
            pipe.submit_batch(pending[:])
            pending.clear()

    async def main() -> None:
        await listen_udp("0.0.0.0", args.udp, gate, handle)
        await listen_tcp("0.0.0.0", args.tcp, gate, handle)
        head("listening")
        kv("syslog udp", args.udp)
        kv("syslog tcp", args.tcp)
        kv("admission", "OPEN — all sources accepted" if gate.open_to_all
           else f"{len(gate.allow)} allowed sources")
        print(c("\n  ctrl-c to stop\n", "2;37"))
        while True:
            await asyncio.sleep(3)
            if pending:
                pipe.submit_batch(pending[:])
                pending.clear()
            pipe.flush()
            s = pipe.metrics.snapshot()
            print(f"  {s['received']:>9,} in │ {s['mapped']:>9,} mapped │ "
                  f"{s['rejected']:>6,} quarantined │ {s['eps']:>8,.0f} eps")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        if pending:
            pipe.submit_batch(pending)
        pipe.close()
        ledger.close()
    return 0


def cmd_api(args) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is not installed:  pip install fastapi uvicorn")
        return 1

    # Pre-flight the ledger before binding a port. The server builds its
    # pipeline lazily on first request, so without this a second instance
    # starts happily and then serves 500s -- the operator sees a broken server
    # rather than the real problem, which is that another one is running.
    from ..store.ledger import Ledger as _Ledger, LedgerBusy as _Busy
    try:
        _Ledger(VAR / "ledger").close()
    except _Busy as exc:
        print(c(f"\n  cannot start: {exc}\n", "1;31"))
        return 1
    print(c(f"\n  STRATA console → http://localhost:{args.port}\n", "1;36"))
    uvicorn.run("strata.app.api:app", host=args.host, port=args.port,
                log_level="warning")
    return 0


def cmd_demo(args) -> int:
    """The scripted demonstration. Every requirement, in order, offline."""
    import shutil
    if VAR.exists():
        shutil.rmtree(VAR)
    (GRAMMARS / "meridian.gateway.yaml").unlink(missing_ok=True)

    n = args.count
    head("1 · a multi-vendor corpus, generated offline")
    info = Corpus(seed=20260826).write(VAR / "samples" / "demo.log", n)
    kv("lines", f"{info['lines']:,}")
    for src, count in list(info["by_source"].items()):
        kv(f"  {src}", f"{count:,}", 24)

    head("2 · preserve → triage → read → map → emit")
    pipe, ledger = build()
    env = Envelope(channel=Channel.SYSLOG_UDP, peer="10.0.0.1", listener="udp/514")
    t0 = time.perf_counter()
    metrics = pipe.drain(read_lines(VAR / "samples" / "demo.log"), env)
    elapsed = time.perf_counter() - t0
    snap = metrics.snapshot()
    kv("normalized", f"{snap['mapped']:,} of {snap['received']:,}  ({snap['map_rate']:.2%})")
    kv("quarantined", f"{snap['rejected']:,}  {snap['by_verdict']}")
    kv("throughput", c(f"{snap['received']/elapsed:,.0f} eps", "1;32"))
    sel = pipe.triage.selectivity()
    kv("triage cost", f"{sel['grammars_per_line']} of {sel['grammars_total']} grammars "
                      f"per line ({sel['work_avoided']:.0%} avoided)")

    head("3 · requirement (a) — losslessness, proven byte for byte")
    report = Auditor(ledger).run()
    kv("records", f"{report['records']:,}")
    kv("fidelity", c(f"{report['fidelity']:.6%}", "1;32"))
    kv("merkle + chain", c(report["verdict"], "1;32" if report["ok"] else "1;31"))

    head("4 · requirement (d) — traceability, both directions")
    ndjson = (VAR / "out" / "events.ndjson").read_text().splitlines()
    doc = json.loads(ndjson[0])
    rid = bytes.fromhex(doc["strata"]["record_id"])
    original = ledger.raw(rid)
    kv("event", f"{doc.get('src_endpoint', {}).get('ip')} → "
                f"{doc.get('dst_endpoint', {}).get('ip')}")
    kv("read by", f"{doc['strata']['grammar']} v{doc['strata']['grammar_version']}")
    kv("record id", doc["strata"]["record_id"][:40] + "…")
    kv("original bytes", repr(original[:70])[:78] + "…")
    kv("byte-exact", c("yes", "1;32") if digest(original) == rid else c("no", "1;31"))
    kv("unmapped kept", f"{len(doc.get('unmapped', {}))} fields")

    head("5 · merkle proof — evidence without disclosure")
    ledger.seal()
    proof = ledger.prove(rid)
    if proof and proof.get("sealed"):
        kv("stratum", f"{proof['stratum']} ({proof['leaves']:,} leaves)")
        kv("proof size", f"{len(proof['path'])} sibling hashes")
        kv("verifies", c("yes", "1;32") if proof["verified_locally"] else c("no", "1;31"))
        print(c("  → proves this one line is in the archive, revealing no other line",
                "2;37"))

    head("6 · principle — unknown beats wrong")
    kv("quarantined", f"{snap['rejected']:,}")
    samples = pipe.rejected_samples(200)
    if samples:
        kv("example", samples[0][:74] + "…")

    head("7 · requirements (e)+(i) — onboard the unknown source, live")
    unknown = [s for s in samples if "MERIDIAN" in s]
    if unknown:
        t1 = time.perf_counter()
        proposal = Forge().propose(unknown, "meridian.gateway", "Meridian", "Gateway")
        forge_ms = (time.perf_counter() - t1) * 1000
        r = proposal.report()
        kv("structure detected", r["induction"]["shape"])
        kv("fields", f"{r['fields_discovered']} found, {r['fields_mapped']} mapped "
                     f"({r['coverage']:.0%})")
        kv("valid", c("yes", "1;32") if r["valid"] else c("no", "1;31"))
        kv("proposed in", f"{forge_ms:.0f} ms")
        if proposal.valid:
            (GRAMMARS / "meridian.gateway.yaml").write_text(proposal.yaml)
            pipe.library.reload()
            pipe.refresh()
            kv("published", c(f"{len(pipe.library)} grammars active, no restart", "1;32"))

            head("8 · rewind — fix the grammar, fix the past")
            result = Rewind(pipe).run(generation=1, dry_run=True)
            kv("records replayed", f"{result['records']:,}")
            kv("re-derived", f"{result['remapped']:,}")
            kv("still quarantined", c(f"{result['still_rejected']:,}", "1;32"
                                      if result["still_rejected"] == 0 else "33"))
            print(c("  → history corrected from the ledger; nothing was re-ingested",
                    "2;37"))

    pipe.close()
    ledger.close()
    print(c("\n  demo complete — no network was used at any point\n", "1;32"))
    return 0


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="strata",
        description="STRATA — universal log pre-processing. "
                    "Layered, legible, nothing rewritten.")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="environment and grammar health").set_defaults(fn=cmd_check)

    g = sub.add_parser("generate", help="write a synthetic corpus")
    g.set_defaults(fn=cmd_generate)
    g.add_argument("--count", type=int, default=20000)
    g.add_argument("--seed", type=int, default=20260826)
    g.add_argument("--clean", action="store_true", help="omit malformed lines")
    g.add_argument("--out", default=str(VAR / "samples" / "corpus.log"))

    i = sub.add_parser("ingest", help="process a log file")
    i.set_defaults(fn=cmd_ingest)
    i.add_argument("path")
    i.add_argument("--limit", type=int, default=0)

    a = sub.add_parser("audit", help="prove losslessness and integrity")
    a.set_defaults(fn=cmd_audit)
    a.add_argument("--sample", type=int, default=0)

    pr = sub.add_parser("prove", help="merkle inclusion proof for one record")
    pr.set_defaults(fn=cmd_prove)
    pr.add_argument("record_id")
    pr.add_argument("--json", action="store_true")

    rw = sub.add_parser("rewind", help="re-derive history from the ledger")
    rw.set_defaults(fn=cmd_rewind)
    rw.add_argument("--generation", type=int, default=1)
    rw.add_argument("--limit", type=int, default=0)
    rw.add_argument("--commit", action="store_true", help="emit, not just derive")

    fo = sub.add_parser("forge", help="propose a grammar from sample lines")
    fo.set_defaults(fn=cmd_forge)
    fo.add_argument("path")
    fo.add_argument("--id", default="proposed.source")
    fo.add_argument("--vendor", default="Unknown")
    fo.add_argument("--product", default="Unknown")
    fo.add_argument("--write", action="store_true")

    b = sub.add_parser("bench", help="measured throughput")
    b.set_defaults(fn=cmd_bench)
    b.add_argument("--count", type=int, default=50000)
    b.add_argument("--workers", type=int, default=1)
    b.add_argument("--json", action="store_true")

    q = sub.add_parser("query", help="SQL over the parquet lake")
    q.set_defaults(fn=cmd_query)
    q.add_argument("sql")

    s = sub.add_parser("serve", help="live syslog listeners")
    s.set_defaults(fn=cmd_serve)
    s.add_argument("--udp", type=int, default=5514)
    s.add_argument("--tcp", type=int, default=5601)
    s.add_argument("--rate", type=float, default=50000)

    ap = sub.add_parser("console", help="web console + REST API")
    ap.set_defaults(fn=cmd_api)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8400)

    d = sub.add_parser("demo", help="the full scripted demonstration")
    d.set_defaults(fn=cmd_demo)
    d.add_argument("--count", type=int, default=20000)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
