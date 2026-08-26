#!/usr/bin/env python3
"""
Generate docs/GRAMMAR-REFERENCE.md from the grammars themselves.

A hand-written mapping document drifts from the code within a week. This one
cannot: it is derived from the files the engine actually loads, and CI fails
the build if the committed copy is stale.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from strata.parse.grammar import Library
from strata.parse.compiler import compile_all

FAMILY_NOTES = {
    "csv": "positional columns, no names on the wire; one shifted column is a silent failure",
    "kv": "self-describing `key=value`; the pair separator varies by vendor",
    "json": "already structured — all the work is in the mapping",
    "freeform": "values embedded in an English sentence written for a human",
    "delimited": "whitespace-positional, no quoting, last column absorbs the rest",
    "cef": "pipe header + key=value extension; covers any CEF-speaking vendor",
    "leef": "pipe header + tab-separated pairs; covers any LEEF-speaking vendor",
}

lib = Library(ROOT / "grammars")
compiled, bad = compile_all(lib.all())
by_id = {g.id: g for g in compiled}
grammars = sorted(lib.all(), key=lambda g: g.id)

out = [
    "# Grammar reference",
    "",
    "**Generated from `grammars/*.yaml` by `tools/gen_reference.py` — do not edit.**",
    "A hand-written mapping document drifts from the code within a week. This one",
    "cannot, because it is derived from the files the engine loads. CI fails if the",
    "committed copy is stale.",
    "",
    f"Target schema **OCSF 1.8.0** · {len(grammars)} grammars · "
    f"{len({g.family for g in grammars})} structural families",
    "",
    "## Coverage by structural family",
    "",
    "Coverage is argued by structural family, not product count. A new source in a",
    "family already handled is a configuration change, not a development task.",
    "",
    "| Family | Grammars | What makes it distinct |",
    "|---|---|---|",
]
fams: dict[str, list[str]] = {}
for g in grammars:
    fams.setdefault(g.family, []).append(g.id)
for fam, ids in sorted(fams.items()):
    out.append(f"| `{fam}` | {', '.join(f'`{i}`' for i in sorted(ids))} | "
               f"{FAMILY_NOTES.get(fam, '—')} |")
out.append("")

for g in grammars:
    c = by_id[g.id]
    out += [f"## `{g.id}` — {g.vendor} {g.product}", "",
            f"- **Version** `{g.version}` · **Family** `{g.family}` · "
            f"**OCSF class** `{g.emit.cls}` (category `{g.emit.category}`)",
            f"- **Compiled pipeline** {' → '.join(f'`{s}`' for s in c.step_names)}",
            f"- **Signature** " + (", ".join(
                [f"must contain `{m}`" for m in g.signature.must]
                + ([f"any of {g.signature.any}"] if g.signature.any else [])
                + ([f"matches `{g.signature.pattern}`"] if g.signature.pattern else [])
            ) or "—") + f" (weight {g.signature.weight})",
            ""]
    if g.clock:
        out += [f"**Timestamp** — `{g.clock.field}`, formats "
                f"{', '.join(f'`{f}`' for f in g.clock.formats)}, zone `{g.clock.zone}`.", ""]
    else:
        out += ["**Timestamp** — none available; falls back to receipt time and is "
                "flagged `time_source: receipt_fallback` rather than invented.", ""]

    out += ["| OCSF field | Vendor field | Type |", "|---|---|---|"]
    for path, src in sorted(g.emit.fields.items()):
        out.append(f"| `{path}` | `{src}` | {g.coerce.get(src, 'str')} |")
    for path, val in sorted(g.emit.const.items()):
        out.append(f"| `{path}` | *(constant)* | `{val}` |")
    out.append("")

    if g.emit.enums:
        out += ["**Enum collapse** — the vendor's own word is always retained.", ""]
        for path, e in g.emit.enums.items():
            table = ", ".join(f"`{k}`→{v}" for k, v in list(e.table.items())[:12])
            out.append(f"- `{path}` ← `{e.source}`: {table} (default `{e.default}`)"
                       + (f", original in `{e.keep}`" if e.keep else ""))
        out.append("")
    if g.emit.ignore:
        out += ["**Excluded from `unmapped`** (vendor padding; the bytes are still in "
                "the ledger): " + ", ".join(f"`{i}`" for i in g.emit.ignore), ""]
    out.append("---\n")

out += ["## Everything else", "",
        "Any field the pipeline extracted that no row above claims is placed in the",
        "event's `unmapped` object. The mapper computes that as a set difference, so a",
        "forgotten mapping is *visible in the output* rather than silently missing. And",
        "regardless of mapping, the original bytes are in the ledger, addressable by",
        "`record_id` and provable by Merkle inclusion.", ""]

(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "GRAMMAR-REFERENCE.md").write_text("\n".join(out), encoding="utf-8")
print(f"docs/GRAMMAR-REFERENCE.md — {len(grammars)} grammars, {len(fams)} families")
if bad:
    print("COMPILE FAILURES:", bad); sys.exit(1)
