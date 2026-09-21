// Capstone presentation deck — AI Statistician, sixteen slides.
//
//   node scripts/build_presentation.js
//
// Built for an academic audience: the problem statement leads, the method is
// shown in enough detail to be judged, the held-out figures are the evidence,
// and the limits are stated on their own slide rather than left to questions.
// Results are paired two to a slide so the whole argument fits sixteen slides
// without dropping any of it.  Every number matches the recorded held-out run.
const pptx = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "docs", "AI_Statistician_Presentation.pptx");
const SL = (p) => path.join(ROOT, "reports", "figures", "slides", p);

// Aspect ratios measured from the rendered files; pictures are fitted, never
// stretched, and the layout check confirms it.
const FIGS = {
  accuracy:   { path: SL("accuracy.png"),   ratio: 1.846 },
  paired:     { path: SL("paired.png"),     ratio: 1.954 },
  abstention: { path: SL("abstention.png"), ratio: 1.811 },
  validity:   { path: SL("validity.png"),   ratio: 2.115 },
  failures:   { path: SL("failures.png"),   ratio: 1.572 },
  coverage:   { path: SL("coverage.png"),   ratio: 1.623 },
};
for (const [k, v] of Object.entries(FIGS)) {
  if (!fs.existsSync(v.path)) throw new Error(`missing figure ${k}: ${v.path}`);
}

// ---- palette ---------------------------------------------------------------
const INK = "14202B", INK_SOFT = "22303D", PAPER = "F4F7FA", CARD = "FFFFFF";
const TEXT = "16222E", TEXT_2 = "4A5A69", MUTED = "8496A6", LINE = "E2E9F0";
const A_COL = "2F6FD0", B_COL = "DD6027", C_COL = "129B68";
const AMBER = "C8891B", ICE = "CFE0F2", MINT = "EAF6F0";
const H = "Cambria", B = "Calibri";

const p = new pptx();
p.layout = "LAYOUT_WIDE";                 // 13.3 x 7.5 in
p.author = "Vishal Dhinesh Kumar";
p.title = "AI Statistician";
const W = 13.3, M = 0.7, COL = 5.75, GAP = 0.4;
const X2 = M + COL + GAP;                 // left edge of the right column
let n = 0;

// ---- helpers ---------------------------------------------------------------
function folio(s, dark) {
  n += 1;
  s.addText(String(n), { x: W - M - 0.6, y: 6.92, w: 0.6, h: 0.3,
    isTextBox: true, margin: 0, fontFace: B, fontSize: 10,
    color: dark ? "55697C" : MUTED, align: "right" });
}
function dark() { const s = p.addSlide(); s.background = { color: INK }; return s; }
function light(title, kicker) {
  const s = p.addSlide(); s.background = { color: PAPER };
  if (kicker) s.addText(kicker.toUpperCase(), { x: M, y: 0.52, w: 9, h: 0.28,
    isTextBox: true, margin: 0, fontFace: B, fontSize: 11, bold: true,
    charSpacing: 2, color: MUTED });
  s.addText(title, { x: M, y: 0.84, w: W - 2 * M, h: 0.72, isTextBox: true,
    margin: 0, fontFace: H, fontSize: 30, bold: true, color: TEXT });
  return s;
}
function card(s, x, y, w, h, fill = CARD) {
  s.addShape(p.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.06,
    fill: { color: fill }, line: { color: LINE, width: 1 },
    shadow: { type: "outer", angle: 90, blur: 10, offset: 2,
              color: "9FB0C0", opacity: 0.22 } });
}
function badge(s, letter, color, x, y, d = 0.5) {
  s.addShape(p.ShapeType.ellipse, { x, y, w: d, h: d,
    fill: { color }, line: { color, width: 0 } });
  s.addText(letter, { x, y, w: d, h: d, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 15, bold: true, color: "FFFFFF",
    align: "center", valign: "middle" });
}
function T(s, text, o) {
  s.addText(text, Object.assign({ isTextBox: true, margin: 0, fontFace: B,
    fontSize: 15, color: TEXT_2 }, o));
}
function figure(s, key, x, y, maxW, maxH, pad = 0.2) {
  card(s, x, y, maxW, maxH);
  const r = FIGS[key].ratio, bw = maxW - 2 * pad, bh = maxH - 2 * pad;
  let w = bw, h = w / r;
  if (h > bh) { h = bh; w = h * r; }
  s.addImage({ path: FIGS[key].path,
    x: x + pad + (bw - w) / 2, y: y + pad + (bh - h) / 2, w, h });
}
// A result slide: two figures side by side, a verdict under each.
function pairOfResults(s, left, right) {
  [[left, M], [right, X2]].forEach(([r, x]) => {
    T(s, r.label, { x, y: 1.66, w: COL, h: 0.3, fontSize: 12, bold: true,
      charSpacing: 1.5, color: MUTED });
    figure(s, r.fig, x, 2.0, COL, 3.2);
    card(s, x, 5.36, COL, 1.2);
    T(s, r.head, { x: x + 0.32, y: 5.52, w: COL - 0.64, h: 0.36,
      fontSize: 15, bold: true, color: r.col });
    T(s, r.body, { x: x + 0.32, y: 5.9, w: COL - 0.64, h: 0.58,
      fontSize: 12.5, lineSpacing: 17 });
  });
}

// ================================================================= slides ===

// 1 — title
{
  const s = dark();
  T(s, "CAPSTONE PROJECT", { x: M, y: 1.5, w: 8, h: 0.3, fontSize: 11,
    bold: true, charSpacing: 2, color: MUTED });
  T(s, "AI Statistician", { x: M, y: 1.9, w: 11, h: 0.95, fontFace: H,
    fontSize: 50, bold: true, color: "FFFFFF" });
  T(s, "Design-aware method selection for LLM statistical analysis", {
    x: M, y: 2.9, w: 11.5, h: 0.6, fontFace: H, fontSize: 24, color: C_COL });
  T(s, "Does an explicit decision protocol make an LLM agent choose valid " +
    "statistical methods more reliably than tool access alone?",
    { x: M, y: 3.75, w: 10.2, h: 0.8, fontSize: 17, color: ICE, lineSpacing: 25 });
  ["A", "B", "C"].forEach((l, i) =>
    badge(s, l, [A_COL, B_COL, C_COL][i], M + i * 0.66, 4.85, 0.5));
  T(s, "Vishal Dhinesh Kumar", { x: M, y: 6.2, w: 8, h: 0.35, fontSize: 15,
    bold: true, color: "FFFFFF" });
  T(s, "SP Jain School of Global Management", { x: M, y: 6.55, w: 8,
    h: 0.3, fontSize: 12.5, color: MUTED });
  folio(s, true);
  s.addNotes("Introduce yourself and the one-line question. Keep it short.");
}

// 2 — problem statement
{
  const s = light("Problem statement", "Why this project exists");
  card(s, M, 1.72, W - 2 * M, 1.64, INK);
  T(s, "Large language models produce statistical analyses that are fluent, " +
    "arithmetically correct, and frequently invalid — because validity depends " +
    "on facts about how the data was collected, which the data itself does " +
    "not contain.",
    { x: M + 0.45, y: 1.92, w: W - 2 * M - 0.9, h: 1.28, fontFace: H,
      fontSize: 19, color: "FFFFFF", lineSpacing: 28 });
  [[A_COL, "Invalid method, correct arithmetic",
    "Independence, pairing, temporal order and clustering are properties of the " +
    "study design. A method that assumes them can be applied to data that " +
    "violates them, and every number will still add up."],
   [B_COL, "Fabricated numerical detail",
    "A model can write a plausible statistic that no calculation produced. The " +
    "prose reads as a result; checking it means redoing the analysis."],
   [AMBER, "No mechanism to decline",
    "Tool use gives the model the ability to compute. Nothing obliges it to " +
    "establish that computing is appropriate before it answers."],
  ].forEach(([col, h, d], i) => {
    const x = M + i * 4.0;
    card(s, x, 3.5, 3.8, 2.85);
    s.addShape(p.ShapeType.ellipse, { x: x + 0.35, y: 3.82, w: 0.22, h: 0.22,
      fill: { color: col }, line: { color: col, width: 0 } });
    T(s, h, { x: x + 0.72, y: 3.74, w: 2.85, h: 0.62, fontSize: 15,
      bold: true, color: TEXT, lineSpacing: 19 });
    T(s, d, { x: x + 0.35, y: 4.5, w: 3.15, h: 1.7, fontSize: 13,
      lineSpacing: 18.5 });
  });
  folio(s);
  s.addNotes("The most important slide. Fluent, correct arithmetic, often invalid.");
}

// 3 — motivating case
{
  const s = light("A motivating case from the benchmark", "The failure, concretely");
  card(s, M, 1.72, COL, 4.55);
  T(s, "Seoul Bike Sharing  ·  UCI 560", { x: M + 0.4, y: 2.0, w: 5, h: 0.4,
    fontFace: H, fontSize: 19, bold: true, color: TEXT });
  T(s, "8,760 rows — one per hour for a year", { x: M + 0.4, y: 2.42, w: 5,
    h: 0.3, fontSize: 13.5, color: MUTED });
  T(s, [
    { text: "Question: does temperature relate to rental demand?",
      options: { bullet: true, breakLine: true } },
    { text: "The table is a textbook fit for correlation or Poisson regression.",
      options: { bullet: true, breakLine: true } },
    { text: "Both assume observations are independent.",
      options: { bullet: true } },
  ], { x: M + 0.4, y: 2.95, w: 5.0, h: 1.65, fontSize: 14.5, paraSpaceAfter: 9 });
  T(s, "They are not.", { x: M + 0.4, y: 4.75, w: 5, h: 0.45, fontFace: H,
    fontSize: 20, bold: true, color: B_COL });
  T(s, "Adjacent hours share weather, commuter cycles and daylight — each row " +
    "carries information about its neighbours.",
    { x: M + 0.4, y: 5.2, w: 5.0, h: 0.85, fontSize: 13.5, lineSpacing: 19 });
  card(s, X2, 1.72, COL, 4.55);
  T(s, "Why a data-only system cannot see it", { x: X2 + 0.4, y: 2.0, w: 5,
    h: 0.4, fontFace: H, fontSize: 19, bold: true, color: TEXT });
  T(s, "Nothing in the matrix marks the rows as serially dependent. The " +
    "dependence is a fact about the collection process — known to whoever " +
    "gathered the data, invisible to anyone reading only the file.",
    { x: X2 + 0.4, y: 2.55, w: 4.95, h: 1.5, fontSize: 14.5, lineSpacing: 21 });
  T(s, "This project supplies that fact through a design card, and scores the " +
    "system on whether it acts on it.",
    { x: X2 + 0.4, y: 4.1, w: 4.95, h: 0.95, fontSize: 14.5, lineSpacing: 21 });
  T(s, "Correct answer: decline to model.", { x: X2 + 0.4, y: 5.35, w: 5,
    h: 0.45, fontFace: H, fontSize: 19, bold: true, color: C_COL });
  folio(s);
  s.addNotes("The table looks perfect; the correct answer is to decline.");
}

// 4 — research question and hypotheses
{
  const s = light("Research question and hypotheses", "What is being tested");
  card(s, M, 1.72, W - 2 * M, 1.15, INK);
  T(s, "Does an explicit statistical decision protocol improve an LLM agent's " +
    "selection of valid methods, compared with direct LLM advice and with tool " +
    "access that has no protocol governing its use?",
    { x: M + 0.45, y: 1.9, w: W - 2 * M - 0.9, h: 0.85, fontFace: H,
      fontSize: 17, color: "FFFFFF", lineSpacing: 24 });
  [["H1", "Selection", "The protocol arm selects an admissible method more " +
    "often than the tool-enabled baseline."],
   ["H2", "Abstention", "The protocol arm declines more reliably on designs " +
    "that no supported method fits — the safety-critical case."],
   ["H3", "Provenance", "Schema-level provenance prevents fabricated numbers " +
    "from reaching a finished report."],
  ].forEach(([k, name, d], i) => {
    const y = 3.15 + i * 1.08;
    card(s, M, y, W - 2 * M, 0.9);
    T(s, k, { x: M + 0.35, y: y + 0.2, w: 0.8, h: 0.5, fontFace: H,
      fontSize: 24, bold: true, color: C_COL });
    T(s, name, { x: M + 1.25, y: y + 0.27, w: 2.1, h: 0.4, fontSize: 16,
      bold: true, color: TEXT });
    T(s, d, { x: M + 3.4, y: y + 0.22, w: 8.2, h: 0.55, fontSize: 14.5,
      lineSpacing: 20 });
  });
  folio(s);
  s.addNotes("H1 compares C against B, not A. B is the honest control.");
}

// 5 — scope and design decisions
{
  const s = light("Scope and design decisions", "What was built, and what was ruled out");
  card(s, M, 1.72, 6.0, 4.6);
  T(s, "A closed library of 14 methods", { x: M + 0.4, y: 1.98, w: 5.3,
    h: 0.4, fontFace: H, fontSize: 18, bold: true, color: TEXT });
  [["Two groups", "Student t · Welch t · Mann–Whitney"],
   ["Three or more groups", "One-way ANOVA · Welch ANOVA · Kruskal–Wallis"],
   ["Categorical", "Chi-square · Fisher exact"],
   ["Association", "Pearson · Spearman"],
   ["Regression", "OLS · Logistic · Poisson · Negative binomial"],
  ].forEach(([k, v], i) => {
    const y = 2.55 + i * 0.58;
    T(s, k, { x: M + 0.4, y, w: 2.2, h: 0.5, fontSize: 13, bold: true,
      color: TEXT });
    T(s, v, { x: M + 2.6, y, w: 3.2, h: 0.55, fontSize: 13, lineSpacing: 17 });
  });
  T(s, "+ abstain — a decision, not a method", { x: M + 0.4, y: 5.55,
    w: 5.3, h: 0.4, fontSize: 14, bold: true, color: AMBER });
  [["Closed, so it is scorable",
    "An open library turns method choice into an essay-grading problem."],
   ["No general code execution",
    "It would let the model bypass the policy and make traces incomparable."],
   ["Out of scope, measured anyway",
    "Paired, repeated-measures, mixed, time-series and survival designs enter " +
    "the benchmark as abstention cases."],
  ].forEach(([h, d], i) => {
    const y = 1.72 + i * 1.57;
    card(s, 6.95, y, 5.65, 1.42);
    T(s, h, { x: 7.3, y: y + 0.22, w: 5.0, h: 0.4, fontSize: 15.5,
      bold: true, color: TEXT });
    T(s, d, { x: 7.3, y: y + 0.64, w: 5.0, h: 0.7, fontSize: 13,
      lineSpacing: 18 });
  });
  folio(s);
  s.addNotes("Justify the closed library and the absence of code execution.");
}

// 6 — how it works: architecture and protocol
{
  const s = light("How it works: one shared core, one ordered protocol",
                  "Architecture and System C");
  [["A", A_COL, "Direct", "No tools; sees C's step-one diagnostics"],
   ["B", B_COL, "Tool loop", "Same tools and schema; no ordering"],
   ["C", C_COL, "Protocol", "Must validate the design first"],
  ].forEach(([l, col, name, d], i) => {
    const x = M + i * 4.0;
    card(s, x, 1.72, 3.8, 1.0);
    badge(s, l, col, x + 0.24, 1.97, 0.48);
    T(s, name, { x: x + 0.88, y: 1.82, w: 2.8, h: 0.34, fontSize: 16,
      bold: true, color: TEXT });
    T(s, d, { x: x + 0.88, y: 2.17, w: 2.8, h: 0.46, fontSize: 12,
      lineSpacing: 15 });
  });
  card(s, M, 2.88, W - 2 * M, 0.58, INK);
  T(s, "SHARED CORE", { x: M + 0.35, y: 3.03, w: 2.0, h: 0.28, fontSize: 10.5,
    bold: true, charSpacing: 2, color: MUTED });
  T(s, "Tool registry   ·   Result store   ·   Report schema   ·   Trace log", {
    x: M + 2.3, y: 2.98, w: 9.4, h: 0.38, fontSize: 15, bold: true,
    color: "FFFFFF" });

  const steps = [
    ["Parse", "Question, variables, outcome"],
    ["Validate design", "Independence, pairing, time, clustering"],
    ["Enumerate", "Methods the design admits"],
    ["Diagnose", "Only checks that could change the choice"],
    ["Select or abstain", "Choose, or decline with a reason"],
    ["Execute", "Run through a validated library"],
    ["Verify", "Check report against every result"],
  ];
  const bw = 1.58, sg = 0.12;
  steps.forEach(([h, d], i) => {
    const x = M + i * (bw + sg), hot = i === 1 || i === 4;
    card(s, x, 3.62, bw, 1.98, hot ? MINT : CARD);
    T(s, String(i + 1), { x: x + 0.16, y: 3.74, w: 0.5, h: 0.46, fontFace: H,
      fontSize: 22, bold: true, color: hot ? C_COL : MUTED });
    T(s, h, { x: x + 0.16, y: 4.22, w: bw - 0.26, h: 0.56, fontSize: 13,
      bold: true, color: TEXT, lineSpacing: 16 });
    T(s, d, { x: x + 0.16, y: 4.8, w: bw - 0.26, h: 0.72, fontSize: 11,
      lineSpacing: 14 });
  });
  T(s, "Only control flow differs, so baseline fairness is provable from the " +
    "code layout. Steps 2 and 5 carry the result: design validation removes " +
    "invalid methods before any diagnostic runs, and step 5 is where the system " +
    "is allowed to decline.",
    { x: M, y: 5.78, w: W - 2 * M, h: 0.78, fontSize: 13.5, italic: true,
      lineSpacing: 19 });
  folio(s);
  s.addNotes("Architecture on top, the seven-step protocol below. B can run every " +
    "check; it lacks the ordering and the permission to stop.");
}

// 7 — provenance contract
{
  const s = light("The provenance contract", "The model cannot write a number");
  T(s, "Rather than inspecting a finished report for fabrication, fabrication is " +
    "made structurally impossible.",
    { x: M, y: 1.72, w: W - 2 * M, h: 0.5, fontFace: H, fontSize: 18,
      bold: true, color: TEXT });
  [["Registered", "Every tool result is stored under a stable key in a run-scoped store."],
   ["Rejected", "The report schema refuses raw numeric literals in prose."],
   ["Referenced", "The model writes a reference such as {{r7.welch_t.p_value}}."],
   ["Resolved", "References are substituted at render; an unknown one fails the run."],
  ].forEach(([h, d], i) => {
    const x = M + i * 3.03;
    card(s, x, 2.5, 2.85, 2.35);
    T(s, String(i + 1), { x: x + 0.3, y: 2.72, w: 0.6, h: 0.55, fontFace: H,
      fontSize: 28, bold: true, color: i === 3 ? B_COL : C_COL });
    T(s, h, { x: x + 0.3, y: 3.32, w: 2.3, h: 0.42, fontSize: 16, bold: true,
      color: TEXT });
    T(s, d, { x: x + 0.3, y: 3.78, w: 2.3, h: 0.95, fontSize: 12.5,
      lineSpacing: 17 });
  });
  card(s, M, 5.12, W - 2 * M, 1.25);
  T(s, "Stated honestly", { x: M + 0.4, y: 5.32, w: 4, h: 0.35, fontSize: 14,
    bold: true, color: AMBER });
  T(s, "For System C this makes numerical fidelity an architectural guarantee, " +
    "not an empirical finding. Its measurable counterpart is how often the model " +
    "reached for a reference that did not exist.",
    { x: M + 0.4, y: 5.67, w: W - 2 * M - 0.8, h: 0.62, fontSize: 13.5,
      lineSpacing: 19 });
  folio(s);
  s.addNotes("Pre-empt the tautology objection: it is a design property.");
}

// 8 — benchmark and evaluation
{
  const s = light("Benchmark and evaluation", "Method");
  card(s, M, 1.72, COL, 4.82);
  T(s, "THE BENCHMARK", { x: M + 0.35, y: 1.95, w: 5, h: 0.28, fontSize: 11,
    bold: true, charSpacing: 2, color: MUTED });
  [["64", "cases", C_COL], ["52", "supported", A_COL],
   ["12", "abstention", AMBER], ["48", "held out", INK]].forEach(([v, l, col], i) => {
    const x = M + 0.35 + i * 1.3;
    T(s, v, { x, y: 2.28, w: 1.25, h: 0.62, fontFace: H, fontSize: 32,
      bold: true, color: col });
    T(s, l, { x, y: 2.88, w: 1.25, h: 0.28, fontSize: 11.5 });
  });
  T(s, "Gold labels from the realised sample", { x: M + 0.35, y: 3.32,
    w: 5.1, h: 0.34, fontSize: 14, bold: true, color: TEXT });
  T(s, "Design facts come from the generator; distributional facts from the " +
    "data actually drawn. 48 of 64 labels are derived, not judged.",
    { x: M + 0.35, y: 3.68, w: 5.1, h: 0.78, fontSize: 12.5, lineSpacing: 17 });
  [["Bank Marketing", "45,211", "UCI 222"], ["Online Shoppers", "12,330", "UCI 468"],
   ["Seoul Bike Sharing", "8,760", "UCI 560"], ["Student Performance", "649", "UCI 320"],
  ].forEach(([name, rows, id], i) => {
    const y = 4.58 + i * 0.36;
    T(s, name, { x: M + 0.35, y, w: 2.6, h: 0.32, fontSize: 12.5, bold: true,
      color: TEXT });
    T(s, rows + " rows", { x: M + 2.95, y, w: 1.45, h: 0.32, fontSize: 12.5 });
    T(s, id, { x: M + 4.4, y, w: 1.0, h: 0.32, fontSize: 11.5, color: MUTED });
  });

  card(s, X2, 1.72, COL, 4.82);
  T(s, "THE EVALUATION", { x: X2 + 0.35, y: 1.95, w: 5, h: 0.28, fontSize: 11,
    bold: true, charSpacing: 2, color: MUTED });
  [["Frozen split", "48 held-out cases never examined in development"],
   ["Frozen prompts", "Instructions fingerprinted before the held-out run"],
   ["Repetitions", "Two runs per case, 288 graded runs"],
   ["Pinned model", "Claude Haiku 4.5, fixed identifier and effort"],
  ].forEach(([h, d], i) => {
    const y = 2.3 + i * 0.52;
    T(s, h, { x: X2 + 0.35, y, w: 1.7, h: 0.3, fontSize: 12.5, bold: true,
      color: TEXT });
    T(s, d, { x: X2 + 2.05, y, w: 3.4, h: 0.46, fontSize: 12, lineSpacing: 15 });
  });
  T(s, "Metrics", { x: X2 + 0.35, y: 4.48, w: 5, h: 0.32, fontSize: 14,
    bold: true, color: TEXT });
  T(s, "Accuracy with Wilson intervals · abstention and unsafe rate · report " +
    "validity · failure stage",
    { x: X2 + 0.35, y: 4.8, w: 5.1, h: 0.55, fontSize: 12.5, lineSpacing: 17 });
  T(s, "Inference", { x: X2 + 0.35, y: 5.44, w: 5, h: 0.32, fontSize: 14,
    bold: true, color: TEXT });
  T(s, "Per-case majority, then McNemar's exact test with a bootstrap interval.",
    { x: X2 + 0.35, y: 5.76, w: 5.1, h: 0.55, fontSize: 12.5, lineSpacing: 17 });
  folio(s);
  s.addNotes("Benchmark left, evaluation controls right. The frozen split is the " +
    "control against tuning to the test.");
}

// 9 — accuracy and significance
{
  const s = light("Result: accuracy, and which differences are real",
                  "Held-out evaluation · H1");
  pairOfResults(s,
    { label: "METHOD-SELECTION ACCURACY", fig: "accuracy", col: C_COL,
      head: "C over B: +25 points",
      body: "Against a +10 target. Tools without a protocol scored below no " +
            "tools at all." },
    { label: "PAIRED COMPARISONS", fig: "paired", col: AMBER,
      head: "C over A: not established",
      body: "C over B is significant at p = 0.0018. C over A points the right " +
            "way but does not clear 0.05." });
  folio(s);
  s.addNotes("Name 75, 67, 89. Solid and filled means significant; dashed and " +
    "hollow means not. Say C over A is unresolved.");
}

// 10 — abstention and grounding
{
  const s = light("Result: declining the invalid, and grounding the report",
                  "Held-out evaluation · H2 and H3");
  pairOfResults(s,
    { label: "DECLINED ON DESIGN-HAZARD RUNS", fig: "abstention", col: C_COL,
      head: "C 78%, tool baseline 0%",
      body: "The sharpest separation in the study. H2 is supported." },
    { label: "REPORTS PASSING THE PROVENANCE CHECK", fig: "validity", col: C_COL,
      head: "43 of 96 ungrounded reports caught",
      body: "From the direct baseline. None reached a reader in any arm. H3 is " +
            "supported." });
  folio(s);
  s.addNotes("B at 100% on grounding: it uses real tools, so its numbers are " +
    "real. Its failure is choosing the wrong method, not inventing figures.");
}

// 11 — failure stage and coverage
{
  const s = light("Result: where each system fails, and what C gave up",
                  "Held-out evaluation · mechanism");
  pairOfResults(s,
    { label: "FAILURES BY STAGE", fig: "failures", col: C_COL,
      head: "Design-validation failures: 20 → 4",
      body: "Tool-only against protocol. The protocol removed the failure it " +
            "was built to remove." },
    { label: "COVERAGE AND ACCURACY", fig: "coverage", col: C_COL,
      head: "87% accurate on 85% answered",
      body: "A and B answered 95% and 98% of cases and were right less often. " +
            "C declines the right cases." });
  folio(s);
  s.addNotes("Totals: A 24, B 32, C 11 failures. Lower coverage with higher " +
    "accuracy is the signature of declining correctly, not at random.");
}

// 12 — hypotheses revisited
{
  const s = light("Hypotheses revisited", "Findings");
  [["H1", "Selection", "Supported", C_COL,
    "C over B: +25 points, McNemar p = 0.0018, 95% CI [+12.5, +39.6]."],
   ["H2", "Abstention", "Supported", C_COL,
    "Declined correctly 78% of the time; the tool baseline 0%."],
   ["H3", "Provenance", "Supported", C_COL,
    "51 ungrounded reports rejected across all arms; none reached a reader."],
   ["—", "C over A", "Unresolved", AMBER,
    "+12.5 points, p = 0.0703. Direction favours C; the sample cannot settle it."],
  ].forEach(([k, name, verdict, col, d], i) => {
    const y = 1.72 + i * 1.12;
    card(s, M, y, W - 2 * M, 0.96);
    T(s, k, { x: M + 0.35, y: y + 0.24, w: 0.8, h: 0.5, fontFace: H,
      fontSize: 22, bold: true, color: col });
    T(s, name, { x: M + 1.2, y: y + 0.29, w: 2.0, h: 0.4, fontSize: 15.5,
      bold: true, color: TEXT });
    s.addShape(p.ShapeType.roundRect, { x: M + 3.25, y: y + 0.27, w: 1.55,
      h: 0.42, rectRadius: 0.21, fill: { color: col },
      line: { color: col, width: 0 } });
    T(s, verdict, { x: M + 3.25, y: y + 0.27, w: 1.55, h: 0.42, fontSize: 12.5,
      bold: true, color: "FFFFFF", align: "center", valign: "middle" });
    T(s, d, { x: M + 5.1, y: y + 0.26, w: 6.5, h: 0.5, fontSize: 14 });
  });
  folio(s);
  s.addNotes("Three supported, one unresolved. Keep the unresolved row.");
}

// 13 — measurement rigour
{
  const s = light("Two defects found in the measurement itself", "Rigour");
  [["1", "A rejected report is not a lost run",
    "51 runs ended in an error. None were infrastructure: each had chosen a " +
    "method before its report failed the contract, and 37 had chosen " +
    "correctly. Discarding them — the obvious treatment — lifts the direct " +
    "baseline from 75.0% to 81.1%.",
    "Fix: score every run that reached a decision."],
   ["2", "A verdict that changed between sessions",
    "With two repetitions a disagreement has no majority. The tie was broken by " +
    "an ordering that varies per interpreter, so the C-over-A p-value moved " +
    "between 0.016 and 0.125 on identical data — across 0.05.",
    "Fix: ties go to the earliest repetition, enforced by a test."],
  ].forEach(([k, h, body, fix], i) => {
    const x = M + i * 6.1;
    card(s, x, 1.72, 5.9, 4.25);
    T(s, k, { x: x + 0.4, y: 1.95, w: 0.6, h: 0.6, fontFace: H, fontSize: 32,
      bold: true, color: AMBER });
    T(s, h, { x: x + 0.4, y: 2.6, w: 5.1, h: 0.45, fontFace: H, fontSize: 17,
      bold: true, color: TEXT });
    T(s, body, { x: x + 0.4, y: 3.12, w: 5.1, h: 1.95, fontSize: 13.5,
      lineSpacing: 19.5 });
    T(s, fix, { x: x + 0.4, y: 5.18, w: 5.1, h: 0.55, fontSize: 13.5,
      bold: true, color: C_COL });
  });
  T(s, "Neither raised an error. Both are recorded as formal deviations from the plan.",
    { x: M, y: 6.22, w: W - 2 * M, h: 0.45, fontSize: 14, italic: true });
  folio(s);
  s.addNotes("The system worked; the measurement had two silent defects.");
}

// 14 — limitations
{
  const s = light("Limitations and threats to validity", "What the evidence does not support");
  [["Model", "Held-out claims are scoped to Claude Haiku 4.5. Generalising to " +
    "frontier models requires re-running the evaluation."],
   ["Power", "Two repetitions and 48 cases. Enough to establish the primary " +
    "comparison; not enough to resolve C over A."],
   ["Interpretation", "The blinded scoring round failed its reliability check " +
    "(κ = −0.044). The metric is withheld rather than reported unreliably."],
   ["Review", "No independent second reviewer for the 16 public-data labels."],
   ["Scope", "Paired, repeated-measures, mixed, time-series and survival designs " +
    "are excluded from the library and tested only as abstention cases."],
  ].forEach(([k, d], i) => {
    const y = 1.72 + i * 0.93;
    card(s, M, y, W - 2 * M, 0.8);
    T(s, k.toUpperCase(), { x: M + 0.35, y: y + 0.26, w: 2.0, h: 0.3,
      fontSize: 11.5, bold: true, charSpacing: 1.5, color: AMBER });
    T(s, d, { x: M + 2.45, y: y + 0.13, w: 9.2, h: 0.58, fontSize: 13.5,
      lineSpacing: 18.5 });
  });
  folio(s);
  s.addNotes("Deliver calmly. Each limit is known, bounded and disclosed.");
}

// 15 — contributions and future work
{
  const s = light("Contributions and next steps", "Conclusion");
  card(s, M, 1.72, COL, 4.3);
  T(s, "WHAT THIS CONTRIBUTES", { x: M + 0.35, y: 1.95, w: 5, h: 0.28,
    fontSize: 11, bold: true, charSpacing: 2, color: MUTED });
  [["Controlled evidence", "A decision protocol, not tool access, drives valid " +
    "method selection."],
   ["A benchmark that scores declining", "Twelve of 64 cases reward " +
    "abstention, making it measurable."],
   ["Provenance by construction", "A report format in which an unsourced " +
    "number cannot exist."],
  ].forEach(([h, d], i) => {
    const y = 2.38 + i * 1.18;
    badge(s, String(i + 1), C_COL, M + 0.35, y, 0.46);
    T(s, h, { x: M + 0.98, y: y - 0.02, w: 4.5, h: 0.36, fontSize: 15,
      bold: true, color: TEXT });
    T(s, d, { x: M + 0.98, y: y + 0.36, w: 4.5, h: 0.62, fontSize: 12.5,
      lineSpacing: 17 });
  });
  card(s, X2, 1.72, COL, 4.3);
  T(s, "WHAT COMES NEXT", { x: X2 + 0.35, y: 1.95, w: 5, h: 0.28, fontSize: 11,
    bold: true, charSpacing: 2, color: MUTED });
  [["Resolve C over A", "A larger held-out set and more repetitions."],
   ["Frontier models", "Test whether the gain persists as capability rises."],
   ["Interpretation scoring", "A second blinded round with the rebuilt rubric."],
   ["Wider library", "Paired, mixed-effects and time-series designs."],
  ].forEach(([h, d], i) => {
    const y = 2.38 + i * 0.88;
    T(s, h, { x: X2 + 0.35, y, w: 5.1, h: 0.34, fontSize: 14.5, bold: true,
      color: TEXT });
    T(s, d, { x: X2 + 0.35, y: y + 0.34, w: 5.1, h: 0.4, fontSize: 12.5 });
  });
  T(s, "Structure, not tooling, is what makes an LLM a reliable statistician.",
    { x: M, y: 6.2, w: W - 2 * M, h: 0.45, fontFace: H, fontSize: 18,
      bold: true, color: C_COL });
  folio(s);
  s.addNotes("End on the one-line conclusion and pause.");
}

// 16 — artefacts and questions
{
  const s = dark();
  T(s, "See it running", { x: M, y: 1.3, w: 9, h: 0.75, fontFace: H,
    fontSize: 36, bold: true, color: "FFFFFF" });
  T(s, "Every case, every answer each system gave, and every step it took — " +
    "inspectable without installing anything.",
    { x: M, y: 2.12, w: 10, h: 0.6, fontSize: 16, color: ICE });
  [["LIVE EVALUATION", "ai-statistician.netlify.app",
    "https://ai-statistician.netlify.app", C_COL],
   ["SOURCE, DATA AND LOGS", "github.com/Vishal4507/AI_statistician",
    "https://github.com/Vishal4507/AI_statistician", ICE],
  ].forEach(([k, label, url, col], i) => {
    const x = M + i * 6.1;
    s.addShape(p.ShapeType.roundRect, { x, y: 3.05, w: 5.9, h: 1.5,
      rectRadius: 0.06, fill: { color: INK_SOFT },
      line: { color: "35485A", width: 1 } });
    T(s, k, { x: x + 0.4, y: 3.3, w: 5.1, h: 0.28, fontSize: 10.5, bold: true,
      charSpacing: 2, color: MUTED });
    T(s, label, { x: x + 0.4, y: 3.66, w: 5.2, h: 0.5, fontSize: 17,
      bold: true, color: col, hyperlink: { url } });
  });
  T(s, "Thank you — questions welcome.", { x: M, y: 5.35, w: 9, h: 0.55,
    fontFace: H, fontSize: 24, bold: true, color: "FFFFFF" });
  folio(s, true);
  s.addNotes("If time allows, show the Seoul bike case live.");
}

p.writeFile({ fileName: OUT }).then((f) => console.log("wrote " + f));
