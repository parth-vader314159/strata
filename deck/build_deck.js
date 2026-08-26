// STRATA — SIH pitch deck generator
// Design language matches the console: paper/ink with a single orange signal.
// Motif: a small orange square marker preceding every section title.

const pptxgen = require("pptxgenjs");

const P = {
  paper: "FAFAF9",
  surface: "F2F1EE",
  sunk: "EAE9E5",
  rule: "E2E1DC",
  rule2: "CFCEC8",
  ink: "14151A",
  ink2: "494D56",
  faint: "8B909A",
  signal: "D9500C",
  signalInk: "B23F06",
  signalSoft: "FCEDE3",
  good: "1C6E46",
  goodSoft: "E4F0E9",
  warn: "96620A",
  warnSoft: "FAF0DC",
  bad: "B23A2C",
  badSoft: "FAE7E3",
  darkInk: "0F1012",
  darkRule: "2A2C31",
  darkText: "ECECE9",
  darkMuted: "9AA0A9",
};

const SANS = "Calibri";
const HEAD = "Arial";
const MONO = "Courier New";

const W = 13.333;
const H = 7.5;
const M = 0.72;          // page margin
const CW = W - 2 * M;    // content width

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Team STRATA";
pres.company = "Smart India Hackathon";
pres.title = "STRATA — Universal Log Pre-processing Framework";

// ---------------------------------------------------------------- helpers

function page(dark) {
  const s = pres.addSlide();
  s.background = { color: dark ? P.darkInk : P.paper };
  return s;
}

// The motif: orange square + kicker + title.
function head(s, kicker, title, opts = {}) {
  const dark = !!opts.dark;
  const y = opts.y === undefined ? 0.52 : opts.y;
  s.addShape(pres.ShapeType.rect, {
    x: M, y: y + 0.06, w: 0.15, h: 0.15, fill: { color: P.signal },
  });
  s.addText(kicker.toUpperCase(), {
    x: M + 0.28, y: y - 0.02, w: CW - 0.28, h: 0.3,
    fontFace: HEAD, fontSize: 11, bold: true, charSpacing: 2,
    color: dark ? P.signal : P.signalInk, isTextBox: true, margin: 0,
    valign: "middle",
  });
  s.addText(title, {
    x: M, y: y + 0.36, w: opts.tw || CW, h: opts.th || 0.72,
    fontFace: HEAD, fontSize: opts.size || 34, bold: true,
    color: dark ? P.darkText : P.ink, isTextBox: true, margin: 0,
    valign: "top", lineSpacing: opts.size ? opts.size * 1.12 : 38,
  });
}

function foot(s, n, label) {
  s.addText(label, {
    x: M, y: H - 0.52, w: CW - 1.2, h: 0.28,
    fontFace: SANS, fontSize: 9.5, color: P.faint, isTextBox: true, margin: 0,
  });
  s.addText(String(n), {
    x: W - M - 0.7, y: H - 0.52, w: 0.7, h: 0.28, align: "right",
    fontFace: HEAD, fontSize: 9.5, bold: true, color: P.rule2,
    isTextBox: true, margin: 0,
  });
}

function card(s, x, y, w, h, fill, line) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.06,
    fill: { color: fill || P.surface },
    line: { color: line || P.rule, width: 1 },
  });
}

function code(s, x, y, w, h, lines, opts = {}) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.05,
    fill: { color: opts.dark ? "17181B" : P.sunk },
    line: { color: opts.dark ? P.darkRule : P.rule, width: 1 },
  });
  s.addText(lines, {
    x: x + 0.18, y: y + 0.12, w: w - 0.36, h: h - 0.24,
    fontFace: MONO, fontSize: opts.size || 9.5,
    color: opts.dark ? P.darkText : P.ink2,
    isTextBox: true, margin: 0, valign: "top", lineSpacing: (opts.size || 9.5) * 1.5,
  });
}

// Big number + label block.
function stat(s, x, y, w, value, label, color, sub) {
  s.addText(value, {
    x, y, w, h: 0.62, fontFace: HEAD, fontSize: 33, bold: true,
    color: color || P.ink, isTextBox: true, margin: 0, valign: "middle",
  });
  s.addText(label, {
    x, y: y + 0.6, w, h: 0.28, fontFace: HEAD, fontSize: 10, bold: true,
    charSpacing: 1, color: P.ink2, isTextBox: true, margin: 0,
  });
  if (sub) {
    s.addText(sub, {
      x, y: y + 0.86, w, h: 0.5, fontFace: SANS, fontSize: 10.5,
      color: P.faint, isTextBox: true, margin: 0, valign: "top",
    });
  }
}

function body(s, x, y, w, h, text, opts = {}) {
  s.addText(text, {
    x, y, w, h, fontFace: SANS, fontSize: opts.size || 14,
    color: opts.color || P.ink2, isTextBox: true, margin: 0,
    valign: opts.valign || "top", lineSpacing: (opts.size || 14) * 1.42,
    align: opts.align,
  });
}

// ============================================================ 1 · TITLE

{
  const s = page(true);
  s.addShape(pres.ShapeType.rect, {
    x: M, y: 1.9, w: 0.34, h: 0.34, fill: { color: P.signal },
  });
  s.addText("STRATA", {
    x: M, y: 2.42, w: 9, h: 1.35,
    fontFace: HEAD, fontSize: 88, bold: true, charSpacing: 6,
    color: P.darkText, isTextBox: true, margin: 0, valign: "middle",
  });
  s.addText("Universal log pre-processing. Layered, legible, nothing rewritten.", {
    x: M, y: 3.82, w: 9.6, h: 0.42,
    fontFace: SANS, fontSize: 19, color: P.signal, isTextBox: true, margin: 0,
  });
  s.addText(
    "One vocabulary for every security device on the perimeter —\nand every original byte kept, provably, forever.",
    {
      x: M, y: 4.4, w: 9.2, h: 0.9,
      fontFace: SANS, fontSize: 14.5, color: P.darkMuted, isTextBox: true,
      margin: 0, lineSpacing: 22,
    });

  s.addShape(pres.ShapeType.line, {
    x: M, y: 5.72, w: CW, h: 0, line: { color: P.darkRule, width: 1 },
  });
  s.addText("SMART INDIA HACKATHON  ·  UNIVERSAL LOG PRE-PROCESSING FRAMEWORK", {
    x: M, y: 5.9, w: 8.6, h: 0.3,
    fontFace: HEAD, fontSize: 10.5, bold: true, charSpacing: 1.6,
    color: P.darkMuted, isTextBox: true, margin: 0,
  });
  s.addText("Runs air-gapped  ·  Pure Python  ·  91 tests", {
    x: W - M - 4.6, y: 5.9, w: 4.6, h: 0.3, align: "right",
    fontFace: SANS, fontSize: 10.5, color: P.faint, isTextBox: true, margin: 0,
  });
  s.addNotes(
    "Open cold, no slide: 'Every security device in this room writes down what it saw.' " +
    "Then pull the network cable and say everything from here runs offline. " +
    "STRATA — layers of rock. Each layer keeps what was laid down; nothing above rewrites what is below.");
}

// ============================================================ 2 · PROBLEM

{
  const s = page();
  head(s, "the problem", "One fact. Four vendors. Four vocabularies.");

  body(s, M, 1.68, CW, 0.34,
    "A machine talked to another machine and was blocked. Here is that single fact, written down four ways:",
    { size: 14 });

  const rows = [
    ["Palo Alto", "1,2026/08/26 14:32:07,0142,TRAFFIC,end,2561,...,10.10.4.55,203.0.113.42,...,deny"],
    ["FortiGate", 'date=2026-08-26 srcip=10.10.4.55 srcport=49832 dstip=203.0.113.42 action="deny"'],
    ["Suricata", '{"timestamp":"2026-08-26T14:32:07","src_ip":"10.10.4.55","dest_ip":"203.0.113.42"}'],
    ["Cisco ASA", "%ASA-6-106023: Deny outbound TCP connection for outside:203.0.113.42/443 to ..."],
  ];
  let y = 2.16;
  rows.forEach(([who, line]) => {
    card(s, M, y, CW, 0.62, P.sunk, P.rule);
    s.addText(who, {
      x: M + 0.18, y: y + 0.06, w: 1.5, h: 0.5,
      fontFace: HEAD, fontSize: 11.5, bold: true, color: P.signalInk,
      isTextBox: true, margin: 0, valign: "middle",
    });
    s.addText(line, {
      x: M + 1.72, y: y + 0.06, w: CW - 1.9, h: 0.5,
      fontFace: MONO, fontSize: 9.5, color: P.ink2,
      isTextBox: true, margin: 0, valign: "middle",
    });
    y += 0.72;
  });

  card(s, M, 5.16, CW, 1.16, P.signalSoft, P.signal);
  s.addText("A SIEM can only correlate what shares a vocabulary.", {
    x: M + 0.28, y: 5.3, w: CW - 0.56, h: 0.34,
    fontFace: HEAD, fontSize: 16, bold: true, color: P.signalInk,
    isTextBox: true, margin: 0,
  });
  body(s, M + 0.28, 5.68, CW - 0.56, 0.5,
    "So somebody writes a parser per vendor. That parser keeps the dozen fields it was told to keep — and throws the original away.",
    { size: 13, color: P.ink2 });

  foot(s, 2, "Scope: perimeter network devices");
  s.addNotes("Show, don't tell. Read two of the four lines aloud and let the audience see they are the same event. " +
    "The punchline is the orange box: the industry's answer to this creates a second, worse problem.");
}

// ============================================================ 3 · THE LOSS

{
  const s = page();
  head(s, "why today's answer fails", "The parser is not the problem.\nThe discard is.");

  body(s, M, 2.28, 6.1, 1.5,
    "Six months after the parser was written, a new attack technique makes field 38 matter.\n\n" +
    "Field 38 was never in the twelve. The line it came from is gone. There is no query, no vendor " +
    "escalation and no budget that brings it back.",
    { size: 15 });

  card(s, M, 3.98, 6.1, 1.9, P.badSoft, P.bad);
  s.addText("What is permanently lost", {
    x: M + 0.26, y: 4.14, w: 5.6, h: 0.3,
    fontFace: HEAD, fontSize: 12, bold: true, color: P.bad, isTextBox: true, margin: 0,
  });
  s.addText([
    { text: "Forensic re-analysis after a new IOC", options: { bullet: true, breakLine: true } },
    { text: "Legal admissibility — the original is the evidence", options: { bullet: true, breakLine: true } },
    { text: "Retraining ML on fields nobody kept", options: { bullet: true, breakLine: true } },
    { text: "Any correction to a mapping bug, retroactively", options: { bullet: true } },
  ], {
    x: M + 0.26, y: 4.48, w: 5.6, h: 1.3,
    fontFace: SANS, fontSize: 12.5, color: P.ink, isTextBox: true, margin: 0,
    paraSpaceAfter: 5,
  });

  // right: the inversion
  card(s, M + 6.5, 2.28, CW - 6.5, 3.6, P.surface, P.rule);
  s.addText("STRATA inverts it", {
    x: M + 6.78, y: 2.5, w: CW - 7.06, h: 0.36,
    fontFace: HEAD, fontSize: 18, bold: true, color: P.ink, isTextBox: true, margin: 0,
  });

  const inv = [
    ["Conventional", "parsed event = product\nraw log = optional backup", P.faint],
    ["STRATA", "raw bytes = source of truth\nnormalized event = derived view", P.signalInk],
  ];
  let iy = 3.02;
  inv.forEach(([t, d, c]) => {
    s.addText(t.toUpperCase(), {
      x: M + 6.78, y: iy, w: CW - 7.06, h: 0.26,
      fontFace: HEAD, fontSize: 10, bold: true, charSpacing: 1.4, color: c,
      isTextBox: true, margin: 0,
    });
    s.addText(d, {
      x: M + 6.78, y: iy + 0.26, w: CW - 7.06, h: 0.66,
      fontFace: MONO, fontSize: 11, color: P.ink, isTextBox: true, margin: 0,
      lineSpacing: 17,
    });
    iy += 1.06;
  });

  s.addShape(pres.ShapeType.line, {
    x: M + 6.78, y: 5.16, w: CW - 7.06, h: 0, line: { color: P.rule2, width: 1 },
  });
  body(s, M + 6.78, 5.3, CW - 7.06, 0.5,
    "Everything else in this deck follows from that one decision.",
    { size: 12.5, color: P.ink });

  foot(s, 3, "The bet the whole architecture rests on");
  s.addNotes("The industry did not choose to lose data — it chose storage economics in 2005 and never revisited them. " +
    "Compressed raw is 1.1–1.3× the feed today. The trade is no longer worth making.");
}

// ============================================================ 4 · ARCHITECTURE

{
  const s = page();
  head(s, "architecture", "Ten stages. One direction. Nothing edited.");

  const stages = [
    ["1", "INTAKE", "admission list · rate limit\nobserved peer · size cap"],
    ["2", "LEDGER", "SOURCE OF TRUTH\nzstd · sha256 · Merkle strata"],
    ["3", "TRIAGE", "shape in one pass\nsame-family grammars only"],
    ["4", "READ", "compiled grammar plan\nclosures, no dispatch"],
    ["5", "MAP", "OCSF 1.8 · enum collapse\nresidue by set difference"],
  ];
  const stages2 = [
    ["6", "OUTLETS", "Parquet lake · CEF→SIEM\nNDJSON · in-memory"],
    ["7", "FORGE", "profiles unknown formats\nproposes a grammar"],
    ["8", "REWIND", "re-derives all history\nfrom untouched originals"],
    ["9", "AUDITOR", "independent rebuild\nand re-hash"],
    ["10", "CONSOLE", "REST · provenance inspector\nRBAC · audit log"],
  ];

  const bw = 2.28, gap = 0.19;
  function rowOf(arr, y, hl) {
    arr.forEach(([n, name, desc], i) => {
      const x = M + i * (bw + gap);
      const isLedger = name === "LEDGER";
      card(s, x, y, bw, 1.36, isLedger ? P.signalSoft : P.surface,
        isLedger ? P.signal : P.rule);
      s.addText(n, {
        x: x + 0.16, y: y + 0.13, w: 0.4, h: 0.26,
        fontFace: HEAD, fontSize: 11, bold: true,
        color: isLedger ? P.signal : P.rule2, isTextBox: true, margin: 0,
      });
      s.addText(name, {
        x: x + 0.5, y: y + 0.13, w: bw - 0.66, h: 0.26,
        fontFace: HEAD, fontSize: 12.5, bold: true, charSpacing: 0.8,
        color: isLedger ? P.signalInk : P.ink, isTextBox: true, margin: 0,
      });
      s.addText(desc, {
        x: x + 0.16, y: y + 0.48, w: bw - 0.32, h: 0.74,
        fontFace: SANS, fontSize: 10.5, color: P.ink2, isTextBox: true,
        margin: 0, valign: "top", lineSpacing: 14,
      });
    });
  }
  rowOf(stages, 1.72);
  rowOf(stages2, 3.32);

  // flow markers in the gaps between cards
  [1.72, 3.32].forEach((ry) => {
    for (let i = 0; i < 4; i++) {
      const x = M + i * (bw + gap) + bw + 0.035;
      s.addShape(pres.ShapeType.triangle, {
        x, y: ry + 0.61, w: 0.12, h: 0.14,
        fill: { color: P.rule2 }, line: { color: P.rule2, width: 0 },
        rotate: 90,
      });
    }
  });

  card(s, M, 5.02, CW, 1.32, P.sunk, P.rule);
  const facts = [
    ["Append-only", "no stage edits or deletes;\ncorrections are new derivations"],
    ["Content-addressed", "sha256(payload) is the identity —\ndedup and idempotent replay, free"],
    ["Data, not code", "grammars are declarative YAML;\nno expressions, no imports, no shell"],
  ];
  facts.forEach(([t, d], i) => {
    const x = M + 0.28 + i * ((CW - 0.56) / 3);
    s.addText(t, {
      x, y: 5.18, w: (CW - 0.56) / 3 - 0.3, h: 0.28,
      fontFace: HEAD, fontSize: 12, bold: true, color: P.signalInk,
      isTextBox: true, margin: 0,
    });
    s.addText(d, {
      x, y: 5.46, w: (CW - 0.56) / 3 - 0.3, h: 0.7,
      fontFace: SANS, fontSize: 11, color: P.ink2, isTextBox: true,
      margin: 0, lineSpacing: 15,
    });
  });

  foot(s, 4, "Stages 7–10 exist only because stage 2 keeps everything");
  s.addNotes("Trace one line through with your finger. The point to land: stages 7, 8 and 9 are impossible " +
    "for a pipeline that discarded the raw. They are not extra features — they are consequences.");
}

// ============================================================ 5 · TRIAGE

{
  const s = page();
  head(s, "how it scales", "Onboarding the 50th source costs\nthe other 49 nothing.");

  body(s, M, 2.42, 6.2, 1.1,
    "Scoring every grammar's rules against every line is O(grammars) per event — so adding sources " +
    "makes the pipeline slower. Exactly backwards for a product whose promise is easy onboarding.",
    { size: 14 });

  card(s, M, 3.66, 6.2, 2.3, P.surface, P.rule);
  s.addText("Structure is far cheaper to decide than identity", {
    x: M + 0.26, y: 3.84, w: 5.7, h: 0.3,
    fontFace: HEAD, fontSize: 13, bold: true, color: P.ink, isTextBox: true, margin: 0,
  });
  body(s, M + 0.26, 4.18, 5.7, 1.6,
    "One character-counting pass tells you a line is JSON, or has 34 commas, or holds 12 key=value pairs. " +
    "That assigns a structural family — and only same-family grammars are then evaluated.\n\n" +
    "The fingerprint is computed once and reused by triage, the compiler and the Forge.",
    { size: 12.5 });

  // right: the funnel
  const rx = M + 6.62, rw = CW - 6.62;
  card(s, rx, 2.42, rw, 3.54, P.sunk, P.rule);
  const steps = [
    ["grammars registered", "10", P.ink2],
    ["one counting pass assigns a family", "↓", P.signal],
    ["evaluated per line", "2.7", P.signalInk],
  ];
  let sy = 2.72;
  steps.forEach(([label, val, c]) => {
    s.addText(val, {
      x: rx + 0.3, y: sy, w: 1.1, h: 0.62,
      fontFace: HEAD, fontSize: 30, bold: true, color: c,
      isTextBox: true, margin: 0, valign: "middle",
    });
    s.addText(label, {
      x: rx + 1.5, y: sy, w: rw - 1.8, h: 0.62,
      fontFace: SANS, fontSize: 12.5, color: P.ink2, isTextBox: true,
      margin: 0, valign: "middle",
    });
    sy += 0.82;
  });
  s.addShape(pres.ShapeType.line, {
    x: rx + 0.3, y: 5.18, w: rw - 0.6, h: 0, line: { color: P.rule2, width: 1 },
  });
  s.addText("73%", {
    x: rx + 0.3, y: 5.3, w: rw - 0.6, h: 0.44,
    fontFace: HEAD, fontSize: 26, bold: true, color: P.good,
    isTextBox: true, margin: 0,
  });
  s.addText("of classification work avoided", {
    x: rx + 0.3, y: 5.7, w: rw - 0.6, h: 0.26,
    fontFace: SANS, fontSize: 11.5, color: P.ink2, isTextBox: true, margin: 0,
  });

  foot(s, 5, "Measured over a 20,000-event multi-vendor corpus");
  s.addNotes("This is the only optimisation in the system that gets BETTER as sources are added. " +
    "Everything else is a constant factor; this one changes the complexity class of onboarding.");
}

// ============================================================ 6 · THROUGHPUT

{
  const s = page();
  head(s, "throughput", "Billions per day is a five-figure\nevents-per-second problem.");

  code(s, M, 2.42, 5.9, 0.92, [
    { text: "1,000,000,000 events/day ÷ 86,400 s  =  11,574 eps sustained\n", options: { color: P.ink } },
    { text: "                        × 3 peak factor  ≈  35,000 eps peak", options: { color: P.faint } },
  ], { size: 10.5 });

  body(s, M, 3.56, 5.9, 1.5,
    "That distinction decides the architecture — in particular whether a rewrite in a compiled " +
    "language is necessary. It is not. Three changes got pure Python past the target:",
    { size: 13.5 });

  const wins = [
    ["Compiled grammars", "closures with args bound; no per-event dispatch"],
    ["Shape-first triage", "73% of classification work never runs"],
    ["Hand-written time parsers", "~10× faster than strptime, and explicit"],
  ];
  let wy = 4.86;
  wins.forEach(([t, d]) => {
    s.addShape(pres.ShapeType.rect, {
      x: M, y: wy + 0.08, w: 0.09, h: 0.09, fill: { color: P.signal },
    });
    s.addText(t, {
      x: M + 0.24, y: wy - 0.02, w: 2.4, h: 0.28,
      fontFace: HEAD, fontSize: 11.5, bold: true, color: P.ink,
      isTextBox: true, margin: 0,
    });
    s.addText(d, {
      x: M + 2.66, y: wy - 0.02, w: 3.3, h: 0.28,
      fontFace: SANS, fontSize: 11.5, color: P.ink2, isTextBox: true, margin: 0,
    });
    wy += 0.42;
  });

  s.addChart(pres.ChartType.bar, [{
    name: "events/sec",
    labels: ["1 process", "2 processes", "8 cores (projected)"],
    values: [11440, 20819, 82900],
  }], {
    x: M + 6.3, y: 2.36, w: CW - 6.3, h: 3.1,
    barDir: "bar",
    chartColors: [P.signal],
    showTitle: true,
    title: "Measured throughput — events/sec",
    titleFontFace: HEAD, titleFontSize: 12, titleColor: P.ink,
    showValue: true, dataLabelPosition: "outEnd",
    dataLabelFontFace: HEAD, dataLabelFontSize: 10, dataLabelColor: P.ink2,
    dataLabelFormatCode: "#,##0",
    catAxisLabelColor: P.ink2, catAxisLabelFontFace: SANS, catAxisLabelFontSize: 10.5,
    valAxisLabelColor: P.faint, valAxisLabelFontSize: 9,
    valAxisMinVal: 0, valAxisMaxVal: 95000, valAxisMajorUnit: 20000,
    valGridLine: { color: P.rule, size: 1 },
    catGridLine: { style: "none" },
    showLegend: false,
    barGapWidthPct: 55,
    plotArea: { fill: { color: P.paper } },
    chartArea: { fill: { color: P.paper } },
  });

  card(s, M + 6.3, 5.6, CW - 6.3, 0.72, P.goodSoft, P.good);
  s.addText("90.6% scaling efficiency → ≈7.2 billion events/day on one 8-core node", {
    x: M + 6.52, y: 5.7, w: CW - 6.74, h: 0.52,
    fontFace: SANS, fontSize: 11.5, color: P.good, isTextBox: true,
    margin: 0, valign: "middle",
  });

  foot(s, 6, "2-core container · CPython 3.11 · engine only, outlets disabled");
  s.addNotes("Be honest about the projection: 8-core is a labelled extrapolation from measured 2-core scaling, " +
    "not a measurement. Judges respect the distinction and will ask if you blur it. " +
    "The 1-process number alone already clears 11,574 eps.");
}

// ============================================================ 7 · REWIND

{
  const s = page();
  head(s, "the capability nobody else has", "Fix the grammar. Fix the past.");

  body(s, M, 2.06, 6.2, 1.0,
    "Six months in, you find a mapping bug. Every event derived from that grammar has been wrong " +
    "since the day it shipped. What happens next?",
    { size: 15 });

  card(s, M, 3.3, 3.0, 2.3, P.badSoft, P.bad);
  s.addText("Conventional pipeline", {
    x: M + 0.22, y: 3.46, w: 2.56, h: 0.3,
    fontFace: HEAD, fontSize: 12, bold: true, color: P.bad, isTextBox: true, margin: 0,
  });
  body(s, M + 0.22, 3.8, 2.56, 1.6,
    "Fix it going forward. Six months of history stays wrong — the inputs that would let you " +
    "re-derive them were discarded on ingest.",
    { size: 12, color: P.ink });

  card(s, M + 3.2, 3.3, 3.0, 2.3, P.goodSoft, P.good);
  s.addText("STRATA", {
    x: M + 3.42, y: 3.46, w: 2.56, h: 0.3,
    fontFace: HEAD, fontSize: 12, bold: true, color: P.good, isTextBox: true, margin: 0,
  });
  body(s, M + 3.42, 3.8, 2.56, 1.6,
    "Correct the YAML. Replay the ledger. Every historical event is re-derived from originals " +
    "that were never touched.",
    { size: 12, color: P.ink });

  code(s, M + 6.62, 2.06, CW - 6.62, 1.32, [
    { text: "$ strata rewind --dry-run\n", options: { color: P.signalInk, bold: true } },
    { text: "  records replayed   20,000\n", options: {} },
    { text: "  re-derived         20,000\n", options: {} },
    { text: "  still quarantined       0\n", options: {} },
    { text: "  ledger bytes written    0", options: { color: P.good } },
  ], { size: 11 });

  card(s, M + 6.62, 3.66, CW - 6.62, 1.94, P.signalSoft, P.signal);
  s.addText("≈60 lines of code.", {
    x: M + 6.86, y: 3.9, w: CW - 7.1, h: 0.32,
    fontFace: HEAD, fontSize: 15, bold: true, color: P.signalInk,
    isTextBox: true, margin: 0,
  });
  body(s, M + 6.86, 4.26, CW - 7.1, 1.2,
    "Not because it is easy — because the architecture was built for it. No pipeline that discards " +
    "the raw can do this at any price.",
    { size: 12, color: P.ink });

  foot(s, 7, "Requirement (a) is not a feature here. It is the substrate.");
  s.addNotes("This is the strongest single differentiator in the deck. If a judge remembers one slide, " +
    "make it this one. Offer to run it live — it takes seconds and writes nothing.");
}

// ============================================================ 8 · MERKLE

{
  const s = page();
  head(s, "integrity", "Evidence, not just integrity.");

  body(s, M, 2.06, 6.0, 1.0,
    "A hash chain proves the whole archive is unaltered — and nothing less. To convince a third party " +
    "that ONE line is present, a chain makes you hand over every other line.",
    { size: 14.5 });

  card(s, M, 3.16, 6.0, 1.28, P.badSoft, P.bad);
  s.addText("In a real case, the other lines belong to other people.", {
    x: M + 0.26, y: 3.32, w: 5.5, h: 0.3,
    fontFace: HEAD, fontSize: 13, bold: true, color: P.bad, isTextBox: true, margin: 0,
  });
  body(s, M + 0.26, 3.66, 5.5, 0.68,
    "Other investigations, other customers, other jurisdictions. Disclosure is often precisely what you cannot do.",
    { size: 12, color: P.ink });

  s.addText("So each stratum is sealed with a Merkle tree.", {
    x: M, y: 4.72, w: 6.0, h: 0.32,
    fontFace: HEAD, fontSize: 15, bold: true, color: P.ink, isTextBox: true, margin: 0,
  });
  body(s, M, 5.08, 6.0, 0.9,
    "One record is proven with ~log₂(n) sibling hashes. The verifier learns that this line is in the " +
    "archive and nothing whatsoever about any other.",
    { size: 12.5 });

  code(s, M + 6.42, 2.06, CW - 6.42, 1.32, [
    { text: "$ strata prove 9f2c1a...\n", options: { color: P.signalInk, bold: true } },
    { text: "  stratum            1\n", options: {} },
    { text: "  leaves        20,000\n", options: {} },
    { text: "  proof size  15 hashes\n", options: {} },
    { text: "  verified         YES", options: { color: P.good, bold: true } },
  ], { size: 11 });

  const details = [
    ["RFC 6962 domain separation", "leaves and nodes hashed with distinct prefixes — otherwise a node can be presented as a leaf and a proof forged for data never stored"],
    ["Odd nodes promoted, not duplicated", "duplicating makes two distinct trees share a root, which is its own forgery vector"],
    ["Roots chained across strata", "tamper with a sealed stratum and the chain breaks at the next one"],
  ];
  let dy = 3.62;
  details.forEach(([t, d]) => {
    s.addShape(pres.ShapeType.rect, {
      x: M + 6.42, y: dy + 0.08, w: 0.09, h: 0.09, fill: { color: P.signal },
    });
    s.addText(t, {
      x: M + 6.66, y: dy - 0.03, w: CW - 6.66, h: 0.26,
      fontFace: HEAD, fontSize: 11, bold: true, color: P.ink, isTextBox: true, margin: 0,
    });
    s.addText(d, {
      x: M + 6.66, y: dy + 0.24, w: CW - 6.66, h: 0.58,
      fontFace: SANS, fontSize: 10.5, color: P.ink2, isTextBox: true, margin: 0,
      valign: "top", lineSpacing: 14,
    });
    dy += 0.86;
  });

  foot(s, 8, "Forged proofs are rejected — there is a test for each of the three faults above");
  s.addNotes("Offer to break it live: flip one byte in a segment file and run audit. It names the record. " +
    "Then show a hand-forged proof being rejected. Two commands, thirty seconds, ends the integrity conversation.");
}

// ============================================================ 9 · PROVENANCE

{
  const s = page();
  head(s, "traceability", "Requirement (d), as something\nyou can point at.");

  body(s, M, 2.42, 6.3, 0.86,
    "Most tools answer traceability with an identifier you could, in principle, look up somewhere. " +
    "The console shows the original bytes with every extracted value highlighted — each linked to the OCSF field it became.",
    { size: 13.5 });

  // mock inspector
  const ix = M, iw = 6.3;
  card(s, ix, 3.42, iw, 2.5, P.sunk, P.rule);
  s.addText("ORIGINAL BYTES  ·  record 9f2c1a4e…  ·  312 B", {
    x: ix + 0.22, y: 3.56, w: iw - 0.44, h: 0.24,
    fontFace: HEAD, fontSize: 9, bold: true, charSpacing: 1, color: P.faint,
    isTextBox: true, margin: 0,
  });
  const HL_MAP = P.signalSoft;   // consumed by the grammar
  const HL_RES = P.warnSoft;     // preserved as unmapped residue
  s.addText([
    { text: "date=", options: { color: P.faint } },
    { text: "2026-08-26 14:32:07", options: { color: P.ink, highlight: HL_MAP } },
    { text: " devname=", options: { color: P.faint } },
    { text: "FGT-EDGE-01", options: { color: P.ink, highlight: HL_MAP } },
    { text: " srcip=", options: { color: P.faint } },
    { text: "10.10.4.55", options: { color: P.ink, highlight: HL_MAP } },
    { text: " srcport=", options: { color: P.faint } },
    { text: "49832", options: { color: P.ink, highlight: HL_MAP } },
    { text: " dstip=", options: { color: P.faint } },
    { text: "203.0.113.42", options: { color: P.ink, highlight: HL_MAP } },
    { text: " action=", options: { color: P.faint } },
    { text: '"deny"', options: { color: P.ink, highlight: HL_MAP } },
    { text: " policyid=", options: { color: P.faint } },
    { text: "1047", options: { color: P.ink, highlight: HL_RES } },
    { text: " sessionid=", options: { color: P.faint } },
    { text: "88213", options: { color: P.ink, highlight: HL_RES } },
  ], {
    x: ix + 0.22, y: 3.86, w: iw - 0.44, h: 1.0,
    fontFace: MONO, fontSize: 9.5, isTextBox: true, margin: 0, valign: "top",
    lineSpacing: 17,
  });
  s.addShape(pres.ShapeType.line, {
    x: ix + 0.22, y: 4.98, w: iw - 0.44, h: 0, line: { color: P.rule2, width: 1 },
  });
  s.addText([
    { text: "bytes 42–52", options: { color: P.signalInk, bold: true } },
    { text: "   →   ", options: { color: P.faint } },
    { text: "src_endpoint.ip", options: { color: P.ink, bold: true } },
    { text: "   via grammar ", options: { color: P.faint } },
    { text: "fortigate.traffic", options: { color: P.ink2 } },
  ], {
    x: ix + 0.22, y: 5.12, w: iw - 0.44, h: 0.3,
    fontFace: MONO, fontSize: 10, isTextBox: true, margin: 0, valign: "middle",
  });
  s.addText([
    { text: "6 fields consumed", options: { color: P.good, bold: true } },
    { text: "  ·  ", options: { color: P.faint } },
    { text: "2 fields preserved as unmapped residue", options: { color: P.warn } },
  ], {
    x: ix + 0.22, y: 5.46, w: iw - 0.44, h: 0.3,
    fontFace: SANS, fontSize: 10.5, isTextBox: true, margin: 0, valign: "middle",
  });

  const rx = M + 6.72, rw = CW - 6.72;
  const pts = [
    ["Byte ranges, both ways", "Hover a highlighted span to see its OCSF field; hover a field to see the bytes it came from."],
    ["Residue is visible, not silent", "Fields no grammar claimed are kept in OCSF's own unmapped object — computed by set difference, so nothing can be quietly dropped."],
    ["Every event names its grammar", "…and its version. A mapping change is attributable to a specific grammar revision."],
  ];
  let py = 2.42;
  pts.forEach(([t, d]) => {
    card(s, rx, py, rw, 1.1, P.surface, P.rule);
    s.addText(t, {
      x: rx + 0.22, y: py + 0.14, w: rw - 0.44, h: 0.26,
      fontFace: HEAD, fontSize: 12, bold: true, color: P.signalInk,
      isTextBox: true, margin: 0,
    });
    s.addText(d, {
      x: rx + 0.22, y: py + 0.4, w: rw - 0.44, h: 0.6,
      fontFace: SANS, fontSize: 10.5, color: P.ink2, isTextBox: true, margin: 0,
      lineSpacing: 14,
    });
    py += 1.2;
  });

  foot(s, 9, "OCSF 1.8 · Linux Foundation · the base event class defines unmapped and raw_data");
  s.addNotes("Click a row in the live console rather than describing it. The two-way hover is the moment " +
    "traceability stops being a claim.");
}

// ============================================================ 10 · FORGE

{
  const s = page();
  head(s, "onboarding", "An unknown vendor, live on stage,\nin under ten milliseconds.");

  body(s, M, 2.5, CW, 0.4,
    "Requirements (e) and (i): plug-and-play onboarding, and less parser-writing effort. The Forge reads quarantined lines and proposes a grammar.",
    { size: 13.5 });

  const flow = [
    ["1", "PROFILE", "Cluster quarantined lines by structure; mine a template across the cluster."],
    ["2", "INFER", "Name hints where fields are named — values and adjacency where they are not."],
    ["3", "PROPOSE", "Emit a complete YAML grammar with confidence per field."],
    ["4", "PUBLISH", "A human approves. Hot reload. No restart."],
  ];
  const fw = (CW - 3 * 0.22) / 4;
  flow.forEach(([n, t, d], i) => {
    const x = M + i * (fw + 0.22);
    card(s, x, 3.06, fw, 1.72, i === 3 ? P.signalSoft : P.surface, i === 3 ? P.signal : P.rule);
    s.addShape(pres.ShapeType.ellipse, {
      x: x + 0.2, y: 3.24, w: 0.34, h: 0.34,
      fill: { color: i === 3 ? P.signal : P.ink },
    });
    s.addText(n, {
      x: x + 0.2, y: 3.24, w: 0.34, h: 0.34, align: "center",
      fontFace: HEAD, fontSize: 12, bold: true, color: P.paper,
      isTextBox: true, margin: 0, valign: "middle",
    });
    s.addText(t, {
      x: x + 0.64, y: 3.24, w: fw - 0.84, h: 0.34,
      fontFace: HEAD, fontSize: 12.5, bold: true, charSpacing: 0.8,
      color: i === 3 ? P.signalInk : P.ink, isTextBox: true, margin: 0, valign: "middle",
    });
    s.addText(d, {
      x: x + 0.2, y: 3.68, w: fw - 0.4, h: 0.96,
      fontFace: SANS, fontSize: 11, color: P.ink2, isTextBox: true,
      margin: 0, valign: "top", lineSpacing: 15,
    });
  });

  card(s, M, 5.0, 6.2, 1.34, P.sunk, P.rule);
  s.addText("Why values, not just names", {
    x: M + 0.24, y: 5.14, w: 5.7, h: 0.28,
    fontFace: HEAD, fontSize: 12, bold: true, color: P.ink, isTextBox: true, margin: 0,
  });
  body(s, M + 0.24, 5.44, 5.7, 0.82,
    "Positional CSV has no names at all — and positional CSV is most of the perimeter. Knowing every value " +
    "in a column is an IPv4 address, and the column two later is always an integer under 65536, tells you it " +
    "is a source endpoint and its port.",
    { size: 11, color: P.ink2 });

  const nums = [
    ["8", "fields found"],
    ["7", "auto-mapped"],
    ["<10 ms", "to onboard"],
  ];
  nums.forEach(([v, l], i) => {
    const x = M + 6.52 + i * ((CW - 6.52) / 3);
    s.addText(v, {
      x, y: 5.0, w: (CW - 6.52) / 3 - 0.2, h: 0.62,
      fontFace: HEAD, fontSize: 30, bold: true, color: P.signal,
      isTextBox: true, margin: 0, valign: "middle",
    });
    s.addText(l, {
      x, y: 5.62, w: (CW - 6.52) / 3 - 0.2, h: 0.3,
      fontFace: SANS, fontSize: 11, color: P.ink2, isTextBox: true, margin: 0,
    });
  });
  s.addText("An unseen “MERIDIAN-GW” format, quarantined → published, during the demo.", {
    x: M + 6.52, y: 5.98, w: CW - 6.52, h: 0.34,
    fontFace: SANS, fontSize: 10.5, color: P.faint, isTextBox: true, margin: 0,
  });

  foot(s, 10, "The Forge proposes. A human publishes. That boundary is deliberate.");
  s.addNotes("Do this live — it is the crowd-pleaser. Quarantine tab → Onboard these → Analyse & propose → " +
    "read the YAML aloud → Publish. Then refresh and the same lines normalize.");
}

// ============================================================ 11 · UNKNOWN

{
  const s = page();
  head(s, "the safety property", "Unknown beats wrong.");

  body(s, M, 2.02, 7.2, 1.0,
    "A misidentified log confidently parsed into the wrong fields is more dangerous than an unparsed one — " +
    "because it looks correct, and nothing alerts. It will sit in the SIEM being quietly wrong for years.",
    { size: 15 });

  const rules = [
    ["Every decision carries a confidence score", "Not a boolean match. Signature weight, family agreement and field yield all contribute."],
    ["Ambiguity lowers confidence rather than hiding", "When two grammars score within 12% of each other, both are penalised. A coin-flip must never present as certainty."],
    ["Below the floor → quarantine, visibly", "Not silently dropped, not force-fit. Quarantined records are in the ledger, on the console, and one click from the Forge."],
    ["The ASA bug is the case in point", "Cisco writes “for outside:X … to inside:Y”, so on an outbound connection the FIRST address is the destination. Positional naming parsed cleanly, validated as OCSF, and swapped source and destination on 135 events. Caught by ground-truth comparison, not by tests passing."],
  ];
  let ry = 3.18;
  rules.forEach(([t, d], i) => {
    const last = i === rules.length - 1;
    card(s, M, ry, CW, last ? 1.02 : 0.62, last ? P.warnSoft : P.surface, last ? P.warn : P.rule);
    s.addText(t, {
      x: M + 0.26, y: ry + (last ? 0.12 : 0.06), w: 4.9, h: last ? 0.5 : 0.5,
      fontFace: HEAD, fontSize: 12, bold: true, color: last ? P.warn : P.ink,
      isTextBox: true, margin: 0, valign: last ? "top" : "middle", lineSpacing: 15,
    });
    s.addText(d, {
      x: M + 5.3, y: ry + (last ? 0.12 : 0.06), w: CW - 5.56, h: last ? 0.8 : 0.5,
      fontFace: SANS, fontSize: 11, color: P.ink2, isTextBox: true,
      margin: 0, valign: last ? "top" : "middle", lineSpacing: 14.5,
    });
    ry += last ? 1.12 : 0.72;
  });

  foot(s, 11, "Every bug found during the build has a regression test marked REGRESSION");
  s.addNotes("Tell the ASA story honestly — it is the most credible thing in the deck. A parse that succeeds, " +
    "validates, and is wrong is exactly the failure mode this whole design exists to make visible.");
}

// ============================================================ 12 · REQUIREMENTS

{
  const s = page();
  head(s, "requirement traceability", "All eleven, and how to check each one.");

  const rows = [
    ["a", "Lossless raw preservation", "store/ledger.py", "strata audit → 100.000000%"],
    ["b", "Parse source attributes", "parse/ + 10 grammars", "strata ingest → map rate"],
    ["c", "Common taxonomy", "mapping/ocsf.py → OCSF 1.8", "every event validated"],
    ["d", "Traceability", "provenance envelope + inspector", "console → Inspector"],
    ["e", "Plug-and-play onboarding", "learn/forge.py", "Forge tab, no restart"],
    ["f", "Unified visibility", "app/ console", "strata console"],
    ["g", "SIEM + lake integration", "io/outlets.py", "strata query \"SELECT …\""],
    ["h", "AI/ML-ready output", "typed Parquet, stable names", "strata query"],
    ["i", "Reduced parser effort", "learn/forge.py", "days → seconds, on stage"],
    ["j", "Air-gapped operation", "install-offline.sh, CI-enforced", "unplug the cable"],
    ["k", "Containerised", "Dockerfile, compose", "docker compose up"],
  ];

  const hy = 1.86, rh = 0.39;
  const cols = [0.42, 3.5, 4.0, 4.31];
  const cx = [M, M + cols[0], M + cols[0] + cols[1], M + cols[0] + cols[1] + cols[2]];
  const heads = ["", "REQUIREMENT", "WHERE IT LIVES", "VERIFY WITH"];
  heads.forEach((h, i) => {
    if (!h) return;
    s.addText(h, {
      x: cx[i], y: hy, w: cols[i] - 0.2, h: 0.28,
      fontFace: HEAD, fontSize: 9.5, bold: true, charSpacing: 1.2, color: P.faint,
      isTextBox: true, margin: 0, valign: "middle",
    });
  });
  s.addShape(pres.ShapeType.line, {
    x: M, y: hy + 0.3, w: CW, h: 0, line: { color: P.rule2, width: 1 },
  });

  rows.forEach((r, i) => {
    const y = hy + 0.38 + i * rh;
    if (i % 2 === 1) {
      s.addShape(pres.ShapeType.rect, {
        x: M - 0.12, y, w: CW + 0.24, h: rh, fill: { color: P.surface }, line: { color: P.surface, width: 0 },
      });
    }
    s.addText(r[0], {
      x: cx[0], y, w: cols[0] - 0.2, h: rh,
      fontFace: HEAD, fontSize: 12.5, bold: true, color: P.signal,
      isTextBox: true, margin: 0, valign: "middle",
    });
    s.addText(r[1], {
      x: cx[1], y, w: cols[1] - 0.2, h: rh,
      fontFace: SANS, fontSize: 12, bold: true, color: P.ink,
      isTextBox: true, margin: 0, valign: "middle",
    });
    s.addText(r[2], {
      x: cx[2], y, w: cols[2] - 0.2, h: rh,
      fontFace: MONO, fontSize: 9.5, color: P.ink2,
      isTextBox: true, margin: 0, valign: "middle",
    });
    s.addText(r[3], {
      x: cx[3], y, w: cols[3], h: rh,
      fontFace: MONO, fontSize: 9.5, color: P.signalInk,
      isTextBox: true, margin: 0, valign: "middle",
    });
  });

  foot(s, 12, "Tests are organised by requirement, not by module — the suite doubles as evidence");
  s.addNotes("Do not read this table aloud. Leave it up for ten seconds and say: every row has a command " +
    "next to it, and you can run all eleven yourself in under five minutes with the cable unplugged.");
}

// ============================================================ 13 · MEASURED

{
  const s = page();
  head(s, "measured, not claimed", "20,000 events. Ten vendors.\nOne command to reproduce.");

  const top = [
    ["100.000000%", "BYTE-EXACT FIDELITY", P.good, "independently reconstructed\nand re-hashed"],
    ["98.97%", "NORMALIZED TO OCSF 1.8", P.ink, "the remainder is a format\nno grammar knows — by design"],
    ["100%", "FIELD ACCURACY", P.good, "src, dst, sport, dport against\ngenerator ground truth"],
    ["11,440", "EVENTS/SEC, 1 PROCESS", P.signal, "20,819 on two workers\n90.6% scaling efficiency"],
  ];
  const sw = (CW - 3 * 0.22) / 4;
  top.forEach(([v, l, c, sub], i) => {
    const x = M + i * (sw + 0.22);
    card(s, x, 2.42, sw, 1.72, P.surface, P.rule);
    s.addText(v, {
      x: x + 0.22, y: 2.56, w: sw - 0.44, h: 0.56,
      fontFace: HEAD, fontSize: v.length > 9 ? 22 : 28, bold: true, color: c,
      isTextBox: true, margin: 0, valign: "middle",
    });
    s.addText(l, {
      x: x + 0.22, y: 3.12, w: sw - 0.44, h: 0.26,
      fontFace: HEAD, fontSize: 9, bold: true, charSpacing: 0.8, color: P.ink2,
      isTextBox: true, margin: 0,
    });
    s.addText(sub, {
      x: x + 0.22, y: 3.4, w: sw - 0.44, h: 0.6,
      fontFace: SANS, fontSize: 10, color: P.faint, isTextBox: true,
      margin: 0, lineSpacing: 13,
    });
  });

  code(s, M, 4.36, 6.2, 1.5, [
    { text: "$ strata demo\n", options: { color: P.signalInk, bold: true } },
    { text: "  merkle roots + chain      intact\n", options: {} },
    { text: "  unknown vendor format     8 fields, 7 auto-mapped, <10 ms\n", options: {} },
    { text: "  rewind                    20,000 / 20,000 re-derived, 0 quarantined\n", options: {} },
    { text: "  triage                    2.7 of 10 grammars evaluated per line\n", options: {} },
    { text: "  air-gap                   0 external refs, 0 network-client imports", options: { color: P.good } },
  ], { size: 9.5 });

  const facts = [
    ["10", "grammars"],
    ["7", "structural families"],
    ["91", "tests passing"],
    ["0", "external references"],
  ];
  facts.forEach(([v, l], i) => {
    const x = M + 6.52, y = 4.36 + i * 0.5;
    s.addText(v, {
      x, y, w: 0.9, h: 0.44,
      fontFace: HEAD, fontSize: 20, bold: true, color: P.ink,
      isTextBox: true, margin: 0, valign: "middle", align: "right",
    });
    s.addText(l, {
      x: x + 1.06, y, w: CW - 7.58, h: 0.44,
      fontFace: SANS, fontSize: 12.5, color: P.ink2,
      isTextBox: true, margin: 0, valign: "middle",
    });
  });

  foot(s, 13, "Sample logs are synthetic, generated from published vendor field references — stated up front");
  s.addNotes("Every number here comes out of a command the judges can run. Say that explicitly. " +
    "And volunteer the synthetic-data limitation before anyone asks — it costs nothing and buys all your credibility.");
}

// ============================================================ 14 · DEPLOY

{
  const s = page();
  head(s, "deployment reality", "Built for the network it will\nactually run on.");

  const blocks = [
    ["AIR-GAPPED", P.good, P.goodSoft,
      "build-bundle.sh on a connected machine, carry the folder across, then install-offline.sh. " +
      "pip runs with --no-index, so reaching the network is impossible rather than merely unnecessary.",
      "CI fails the build on any external reference or network-client import."],
    ["CONTAINERISED", P.signalInk, P.signalSoft,
      "docker compose up -d. Console on 8400, syslog on UDP 514 and TCP 601. Non-root user, " +
      "pinned base, secret from the environment.",
      "One .env file is the entire configuration surface."],
    ["OPERATIONALLY HONEST", P.warn, P.warnSoft,
      "Single-writer ledger enforced with a lock at the door — a second process refuses with a named " +
      "error instead of corrupting a segment.",
      "Scale by sharding, exactly as it would work across machines."],
  ];
  const bw2 = (CW - 2 * 0.24) / 3;
  blocks.forEach(([t, c, bg, d, note], i) => {
    const x = M + i * (bw2 + 0.24);
    card(s, x, 2.46, bw2, 2.36, bg, c);
    s.addText(t, {
      x: x + 0.24, y: 2.64, w: bw2 - 0.48, h: 0.28,
      fontFace: HEAD, fontSize: 11.5, bold: true, charSpacing: 1.2, color: c,
      isTextBox: true, margin: 0,
    });
    s.addText(d, {
      x: x + 0.24, y: 2.96, w: bw2 - 0.48, h: 1.1,
      fontFace: SANS, fontSize: 11.5, color: P.ink, isTextBox: true,
      margin: 0, valign: "top", lineSpacing: 16,
    });
    s.addText(note, {
      x: x + 0.24, y: 4.12, w: bw2 - 0.48, h: 0.58,
      fontFace: SANS, fontSize: 10.5, color: P.ink2, isTextBox: true,
      margin: 0, valign: "top", lineSpacing: 14, italic: true,
    });
  });

  s.addText("Known limitations — stated plainly", {
    x: M, y: 5.02, w: CW, h: 0.3,
    fontFace: HEAD, fontSize: 13, bold: true, color: P.ink, isTextBox: true, margin: 0,
  });
  const lims = [
    "Sample logs are synthetic, from published vendor field references — structurally faithful, not captured traffic.",
    "The 8-core throughput figure is a labelled projection from measured 2-core scaling, not a measurement.",
    "OCSF mappings cover the fields our sources emit, not the full 1.8 schema; validation checks structure.",
    "No encryption at rest — the frame format carries a version byte so it can be added without migration.",
  ];
  s.addText(lims.map((t, i) => ({
    text: t, options: { bullet: true, breakLine: i !== lims.length - 1 },
  })), {
    x: M, y: 5.36, w: CW, h: 1.0,
    fontFace: SANS, fontSize: 11, color: P.ink2, isTextBox: true, margin: 0,
    paraSpaceAfter: 3,
  });

  foot(s, 14, "Pretending otherwise is how a viva goes badly");
  s.addNotes("Naming your own limitations before the panel does converts the hardest part of Q&A into a " +
    "credibility win. Each limitation here has a stated path forward — say the path, not just the limit.");
}

// ============================================================ 15 · CLOSE

{
  const s = page(true);
  s.addShape(pres.ShapeType.rect, {
    x: M, y: 1.62, w: 0.24, h: 0.24, fill: { color: P.signal },
  });
  s.addText("The translator that never\nthrows anything away.", {
    x: M, y: 2.06, w: 8.4, h: 1.7,
    fontFace: HEAD, fontSize: 40, bold: true, color: P.darkText,
    isTextBox: true, margin: 0, valign: "top", lineSpacing: 48,
  });

  const closes = [
    ["One vocabulary", "OCSF 1.8 across every perimeter vendor — 98.97% normalized, residue preserved, never dropped."],
    ["Every original byte", "100.000000% byte-exact, Merkle-sealed, provable one record at a time without disclosing any other."],
    ["A past you can still fix", "Correct a grammar, re-derive six months of history. No tool that discards the raw can do this."],
  ];
  let cy = 4.0;
  closes.forEach(([t, d]) => {
    s.addShape(pres.ShapeType.rect, {
      x: M, y: cy + 0.09, w: 0.09, h: 0.09, fill: { color: P.signal },
    });
    s.addText(t, {
      x: M + 0.26, y: cy - 0.02, w: 2.7, h: 0.3,
      fontFace: HEAD, fontSize: 13, bold: true, color: P.darkText,
      isTextBox: true, margin: 0,
    });
    s.addText(d, {
      x: M + 3.06, y: cy - 0.05, w: 6.4, h: 0.56,
      fontFace: SANS, fontSize: 11.5, color: P.darkMuted, isTextBox: true,
      margin: 0, valign: "top",
    });
    cy += 0.68;
  });

  s.addShape(pres.ShapeType.line, {
    x: M, y: 6.34, w: CW, h: 0, line: { color: P.darkRule, width: 1 },
  });
  s.addText("STRATA", {
    x: M, y: 6.5, w: 3, h: 0.34,
    fontFace: HEAD, fontSize: 15, bold: true, charSpacing: 3,
    color: P.signal, isTextBox: true, margin: 0,
  });
  s.addText("python3 strata.py demo   ·   90 seconds   ·   no network required", {
    x: W - M - 7, y: 6.5, w: 7, h: 0.34, align: "right",
    fontFace: MONO, fontSize: 11.5, color: P.darkMuted, isTextBox: true, margin: 0,
  });
  s.addNotes("Close on the same sentence you opened with, then offer the live demo. " +
    "Do not add a thank-you slide — end on the command.");
}

pres.writeFile({ fileName: "/home/claude/strata/deck/STRATA-SIH-Deck.pptx" })
  .then((f) => console.log("wrote", f));
