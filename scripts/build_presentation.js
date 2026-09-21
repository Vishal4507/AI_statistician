// Capstone presentation deck — AI Statistician.
//
//   node scripts/build_presentation.js
//
// Built for an academic audience: the problem statement leads, the method is
// shown in enough detail to be judged, the held-out figures are the evidence,
// and the limits are stated on their own slide rather than left to questions.
// Every number on a slide matches the recorded held-out run.
const pptx = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "docs", "AI_Statistician_Presentation.pptx");
const F = (p) => path.join(ROOT, "reports", "figures", p);

const FIGS = {
  accuracy:   { path: F("slides/accuracy.png"),   ratio: 1.930 },
  paired:     { path: F("slides/paired.png"),     ratio: 2.413 },
  abstention: { path: F("slides/abstention.png"), ratio: 2.072 },
  validity:   { path: F("slides/validity.png"),   ratio: 2.115 },
  failures:   { path: F("fig7_heldout_failures.png"),      ratio: 1.891 },
  coverage:   { path: F("fig6_heldout_risk_coverage.png"), ratio: 1.395 },
};
for (const [k, v] of Object.entries(FIGS)) {
  if (!fs.existsSync(v.path)) throw new Error(`missing figure ${k}: ${v.path}`);
}

// ---- palette ---------------------------------------------------------------
const INK = "14202B", INK_SOFT = "22303D", PAPER = "F4F7FA", CARD = "FFFFFF";
const TEXT = "16222E", TEXT_2 = "4A5A69", MUTED = "8496A6", LINE = "E2E9F0";
const A_COL = "2F6FD0", B_COL = "DD6027", C_COL = "129B68";
const AMBER = "C8891B", ICE = "CFE0F2";
const H = "Cambria", B = "Calibri";

const p = new pptx();
p.layout = "LAYOUT_WIDE";                 // 13.3 x 7.5 in
p.author = "Vishal Dhinesh Kumar";
p.title = "AI Statistician";
const W = 13.3, M = 0.7;
let n = 0;                                 // slide counter for the folio

// ---- helpers ---------------------------------------------------------------
function folio(s, dark) {
  n += 1;
  s.addText(String(n), {
    x: W - M - 0.6, y: 6.92, w: 0.6, h: 0.3, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 10, color: dark ? "55697C" : MUTED, align: "right" });
}
function dark() {
  const s = p.addSlide(); s.background = { color: INK }; return s;
}
function light(title, kicker) {
  const s = p.addSlide(); s.background = { color: PAPER };
  if (kicker) s.addText(kicker.toUpperCase(), {
    x: M, y: 0.52, w: 9, h: 0.28, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 11, bold: true, charSpacing: 2, color: MUTED });
  s.addText(title, {
    x: M, y: 0.84, w: W - 2 * M, h: 0.72, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 30, bold: true, color: TEXT });
  return s;
}
function card(s, x, y, w, h, fill = CARD) {
  s.addShape(p.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.06, fill: { color: fill },
    line: { color: LINE, width: 1 },
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
function T(s, text, o) {                    // text box with the house defaults
  s.addText(text, Object.assign({ isTextBox: true, margin: 0, fontFace: B,
    fontSize: 15, color: TEXT_2 }, o));
}
// Fit a figure inside a box without distortion, on a white card so the
// figure's own white ground reads as part of the card.
function figure(s, key, x, y, maxW, maxH, pad = 0.22) {
  card(s, x, y, maxW, maxH);
  const r = FIGS[key].ratio, bw = maxW - 2 * pad, bh = maxH - 2 * pad;
  let w = bw, h = w / r;
  if (h > bh) { h = bh; w = h * r; }
  s.addImage({ path: FIGS[key].path,
    x: x + pad + (bw - w) / 2, y: y + pad + (bh - h) / 2, w, h });
}
function readout(s, x, y, w, h, heading, big, bigCol, body, tail) {
  card(s, x, y, w, h);
  T(s, heading, { x: x + 0.35, y: y + 0.3, w: w - 0.7, h: 0.3, fontSize: 12,
    bold: true, charSpacing: 1, color: MUTED });
  if (big) T(s, big, { x: x + 0.35, y: y + 0.62, w: w - 0.7, h: 0.8,
    fontFace: H, fontSize: 44, bold: true, color: bigCol });
  T(s, body, { x: x + 0.35, y: y + (big ? 1.5 : 0.7), w: w - 0.7,
    h: h - (big ? 1.5 : 0.7) - (tail ? 1.05 : 0.3), fontSize: 14,
    lineSpacing: 20 });
  if (tail) T(s, tail, { x: x + 0.35, y: y + h - 1.0, w: w - 0.7, h: 0.8,
    fontSize: 13.5, italic: true, color: bigCol === MUTED ? TEXT_2 : bigCol,
    lineSpacing: 19 });
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
  s.addNotes("Introduce yourself and the one-line question. Keep this short — " +
    "the problem statement on the next slide does the real work.");
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

  const cols = [
    [A_COL, "Invalid method, correct arithmetic",
     "Independence, pairing, temporal order and clustering are properties of " +
     "the study design. A method that assumes them can be applied to data that " +
     "violates them, and every number will still add up."],
    [B_COL, "Fabricated numerical detail",
     "A model can write a plausible statistic that no calculation produced. " +
     "The prose reads as a result; checking it means redoing the analysis."],
    [AMBER, "No mechanism to decline",
     "Tool use gives the model the ability to compute. Nothing obliges it to " +
     "establish that computing is appropriate before it answers."],
  ];
  cols.forEach(([col, h, d], i) => {
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
  s.addNotes("This is the most important slide. State the problem in one breath: " +
    "fluent, correct arithmetic, often invalid. Then the three consequences. " +
    "The key phrase is 'the data itself does not contain' — design facts live " +
    "outside the spreadsheet.");
}

// 3 — motivating case
{
  const s = light("A motivating case from the benchmark", "The failure, concretely");
  card(s, M, 1.72, 5.75, 4.55);
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
  ], { x: M + 0.4, y: 2.95, w: 5.0, h: 1.65, fontSize: 14.5,
       paraSpaceAfter: 9 });
  T(s, "They are not.", { x: M + 0.4, y: 4.75, w: 5, h: 0.45, fontFace: H,
    fontSize: 20, bold: true, color: B_COL });
  T(s, "Adjacent hours share weather, commuter cycles and daylight — each row " +
    "carries information about its neighbours.",
    { x: M + 0.4, y: 5.2, w: 5.0, h: 0.85, fontSize: 13.5, lineSpacing: 19 });

  card(s, 6.85, 1.72, 5.75, 4.55);
  T(s, "Why a data-only system cannot see it", { x: 7.25, y: 2.0, w: 5,
    h: 0.4, fontFace: H, fontSize: 19, bold: true, color: TEXT });
  T(s, "Nothing in the matrix marks the rows as serially dependent. The " +
    "dependence is a fact about the collection process — known to whoever " +
    "gathered the data, invisible to anyone reading only the file.",
    { x: 7.25, y: 2.55, w: 4.95, h: 1.5, fontSize: 14.5, lineSpacing: 21 });
  T(s, "This project supplies that fact through a design card, and scores the " +
    "system on whether it acts on it.",
    { x: 7.25, y: 4.1, w: 4.95, h: 0.95, fontSize: 14.5, lineSpacing: 21 });
  T(s, "Correct answer: decline to model.", { x: 7.25, y: 5.35, w: 5,
    h: 0.45, fontFace: H, fontSize: 19, bold: true, color: C_COL });
  folio(s);
  s.addNotes("Walk through it as a story. The table looks perfect. Two standard " +
    "methods fit. Both are invalid because of how the data was collected. The " +
    "design card is how the system learns the fact the file cannot tell it.");
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
  const hyps = [
    ["H1", "Selection", "The protocol arm selects an admissible method more often " +
     "than the tool-enabled baseline."],
    ["H2", "Abstention", "The protocol arm declines more reliably on designs that " +
     "no supported method fits — the safety-critical case."],
    ["H3", "Provenance", "Schema-level provenance prevents fabricated numbers " +
     "from reaching a finished report."],
  ];
  hyps.forEach(([k, name, d], i) => {
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
  s.addNotes("Point out that H1 compares C against B, not against A. B has the " +
    "same tools and the same output format as C, so B is the honest control — " +
    "if C wins against B, it is the procedure that won.");
}

// 5 — scope and design decisions
{
  const s = light("Scope and design decisions", "What was built, and what was ruled out");
  card(s, M, 1.72, 6.0, 4.6);
  T(s, "A closed library of 14 methods", { x: M + 0.4, y: 1.98, w: 5.3,
    h: 0.4, fontFace: H, fontSize: 18, bold: true, color: TEXT });
  const lib = [
    ["Two groups", "Student t · Welch t · Mann–Whitney"],
    ["Three or more groups", "One-way ANOVA · Welch ANOVA · Kruskal–Wallis"],
    ["Categorical", "Chi-square · Fisher exact"],
    ["Association", "Pearson · Spearman"],
    ["Regression", "OLS · Logistic · Poisson · Negative binomial"],
  ];
  lib.forEach(([k, v], i) => {
    const y = 2.55 + i * 0.58;
    T(s, k, { x: M + 0.4, y, w: 2.2, h: 0.5, fontSize: 13, bold: true,
      color: TEXT });
    T(s, v, { x: M + 2.6, y, w: 3.2, h: 0.55, fontSize: 13, lineSpacing: 17 });
  });
  T(s, "+ abstain — a decision, not a method", { x: M + 0.4, y: 5.55,
    w: 5.3, h: 0.4, fontSize: 14, bold: true, color: AMBER });

  const dec = [
    ["Closed, so it is scorable",
     "An open library turns method choice into an essay-grading problem."],
    ["No general code execution",
     "It would let the model bypass the policy and make traces incomparable."],
    ["Out of scope, measured anyway",
     "Paired, repeated-measures, mixed, time-series and survival designs enter " +
     "the benchmark as abstention cases."],
  ];
  dec.forEach(([h, d], i) => {
    const y = 1.72 + i * 1.57;
    card(s, 6.95, y, 5.65, 1.42);
    T(s, h, { x: 7.3, y: y + 0.22, w: 5.0, h: 0.4, fontSize: 15.5, bold: true,
      color: TEXT });
    T(s, d, { x: 7.3, y: y + 0.64, w: 5.0, h: 0.7, fontSize: 13,
      lineSpacing: 18 });
  });
  folio(s);
  s.addNotes("The no-code-execution decision is the one a professor may probe. " +
    "The answer: a general tool would let the model skip the method policy, " +
    "and then the three arms would not be doing comparable work.");
}

// 6 — architecture
{
  const s = light("Three systems over one shared core", "Architecture");
  const drivers = [
    ["A", A_COL, "Direct", "No tools. Receives the same step-one diagnostics C receives."],
    ["B", B_COL, "Tool loop", "Identical tools and report schema. No ordering imposed."],
    ["C", C_COL, "Protocol", "A state machine that must validate the design first."],
  ];
  drivers.forEach(([l, col, name, d], i) => {
    const x = M + i * 4.0;
    card(s, x, 1.72, 3.8, 1.9);
    badge(s, l, col, x + 0.35, 1.98, 0.5);
    T(s, name, { x: x + 1.0, y: 2.03, w: 2.6, h: 0.42, fontFace: H,
      fontSize: 19, bold: true, color: TEXT });
    T(s, d, { x: x + 0.35, y: 2.65, w: 3.1, h: 0.85, fontSize: 13,
      lineSpacing: 18 });
    s.addShape(p.ShapeType.line, { x: x + 1.9, y: 3.62, w: 0, h: 0.5,
      line: { color: MUTED, width: 1.5, endArrowType: "triangle" } });
  });
  card(s, M, 4.18, W - 2 * M, 1.35, INK);
  T(s, "SHARED CORE", { x: M + 0.4, y: 4.38, w: 4, h: 0.28, fontSize: 11,
    bold: true, charSpacing: 2, color: MUTED });
  ["Tool registry", "Result store", "Report schema", "Trace log"].forEach((c, i) => {
    T(s, c, { x: M + 0.4 + i * 2.95, y: 4.78, w: 2.7, h: 0.5, fontSize: 17,
      bold: true, color: "FFFFFF" });
  });
  T(s, "Only control flow differs. Baseline fairness is therefore provable from " +
    "the repository layout rather than asserted: there is no code path on which " +
    "A or B could have been disadvantaged.",
    { x: M, y: 5.78, w: W - 2 * M, h: 0.75, fontSize: 14.5, italic: true,
      lineSpacing: 21 });
  folio(s);
  s.addNotes("This slide answers 'how do you know the comparison is fair?' before " +
    "it is asked. All three import the same four components.");
}

// 7 — the protocol
{
  const s = light("The structured agent's decision protocol", "System C");
  const steps = [
    ["Parse", "Question, variables and outcome type"],
    ["Validate design", "Independence, pairing, time order, clustering"],
    ["Enumerate", "Candidate methods the design admits"],
    ["Diagnose", "Only the checks that could change the choice"],
    ["Select or abstain", "Choose, or decline with a stated reason"],
    ["Execute", "Run through a validated statistical library"],
    ["Verify", "Check the report against every recorded result"],
  ];
  const bw = 1.58, gap = 0.12;
  steps.forEach(([h, d], i) => {
    const x = M + i * (bw + gap);
    const hot = i === 1 || i === 4;
    card(s, x, 1.95, bw, 2.75, hot ? "EAF6F0" : CARD);
    T(s, String(i + 1), { x: x + 0.18, y: 2.14, w: 0.6, h: 0.55, fontFace: H,
      fontSize: 28, bold: true, color: hot ? C_COL : MUTED });
    T(s, h, { x: x + 0.18, y: 2.78, w: bw - 0.3, h: 0.62, fontSize: 14,
      bold: true, color: TEXT, lineSpacing: 17 });
    T(s, d, { x: x + 0.18, y: 3.45, w: bw - 0.3, h: 1.15, fontSize: 11.5,
      lineSpacing: 15 });
  });
  card(s, M, 5.0, W - 2 * M, 1.4);
  T(s, "Steps 2 and 5 carry the result.", { x: M + 0.4, y: 5.22, w: 11,
    h: 0.4, fontSize: 16, bold: true, color: C_COL });
  T(s, "Design validation gates everything downstream: a hazard found at step 2 " +
    "removes methods before any diagnostic runs, so a clean-looking normality " +
    "test can never talk the system into a method the design rules out.",
    { x: M + 0.4, y: 5.62, w: W - 2 * M - 0.8, h: 0.7, fontSize: 13.5,
      lineSpacing: 19 });
  folio(s);
  s.addNotes("Emphasise ordering. B can run all the same checks as C — nothing " +
    "stops it. What it lacks is the requirement to validate the design first " +
    "and the permission to stop.");
}

// 8 — provenance contract
{
  const s = light("The provenance contract", "The model cannot write a number");
  T(s, "Rather than inspecting a finished report for fabrication, fabrication is " +
    "made structurally impossible.",
    { x: M, y: 1.72, w: W - 2 * M, h: 0.5, fontFace: H, fontSize: 18,
      bold: true, color: TEXT });
  const st = [
    ["Registered", "Every tool result is stored under a stable key in a run-scoped store."],
    ["Rejected", "The report schema refuses raw numeric literals in prose."],
    ["Referenced", "The model writes a reference such as {{r7.welch_t.p_value}}."],
    ["Resolved", "References are substituted at render; an unknown one fails the run."],
  ];
  st.forEach(([h, d], i) => {
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
  s.addNotes("Pre-empt the obvious objection: 'if fabrication is impossible, then " +
    "100% fidelity is not a result.' Agree — say it is a design property, and " +
    "that the rejection rate is the empirical measure.");
}

// 9 — benchmark
{
  const s = light("The benchmark: 64 cases, none hand-authored", "Method · data");
  const stats = [["64", "cases", C_COL], ["52", "supported", A_COL],
                 ["12", "abstention", AMBER], ["48", "held out", INK]];
  stats.forEach(([v, l, col], i) => {
    const x = M + i * 1.5;
    T(s, v, { x, y: 1.75, w: 1.4, h: 0.85, fontFace: H, fontSize: 44,
      bold: true, color: col });
    T(s, l, { x, y: 2.58, w: 1.4, h: 0.32, fontSize: 13 });
  });
  card(s, M, 3.15, 5.85, 3.2);
  T(s, "Gold labels from the realised sample", { x: M + 0.4, y: 3.4,
    w: 5.1, h: 0.4, fontSize: 15.5, bold: true, color: TEXT });
  T(s, "Design facts come from the generator's parameters, because " +
    "independence and pairing are properties of the design. Distributional " +
    "facts come from the data actually drawn, because that is what a correct " +
    "choice must respond to.",
    { x: M + 0.4, y: 3.85, w: 5.1, h: 1.5, fontSize: 13.5, lineSpacing: 19 });
  T(s, "A generator asked for a normal sample that drew a skewed one is " +
    "labelled for the sample it drew.",
    { x: M + 0.4, y: 5.42, w: 5.1, h: 0.75, fontSize: 13, italic: true,
      color: TEXT_2, lineSpacing: 18 });

  card(s, 6.85, 1.72, 5.75, 4.63);
  T(s, "Public sources", { x: 7.2, y: 1.98, w: 5, h: 0.4, fontSize: 15.5,
    bold: true, color: TEXT });
  const ds = [["Bank Marketing", "45,211", "UCI 222"],
              ["Online Shoppers", "12,330", "UCI 468"],
              ["Seoul Bike Sharing", "8,760", "UCI 560"],
              ["Student Performance", "649", "UCI 320"]];
  ds.forEach(([name, rows, id], i) => {
    const y = 2.55 + i * 0.62;
    T(s, name, { x: 7.2, y, w: 2.7, h: 0.4, fontSize: 14, bold: true,
      color: TEXT });
    T(s, rows + " rows", { x: 9.9, y, w: 1.5, h: 0.4, fontSize: 13.5 });
    T(s, id, { x: 11.35, y, w: 1.0, h: 0.4, fontSize: 12, color: MUTED });
  });
  T(s, "48 synthetic cases carry labels known by construction; 16 from public " +
    "data were validated against their realised values, which caught one " +
    "mislabel.",
    { x: 7.2, y: 5.12, w: 5.0, h: 1.05, fontSize: 13, lineSpacing: 18 });
  folio(s);
  s.addNotes("If asked how the answer key avoids being opinion: 48 of 64 labels " +
    "are derived from the generator and the realised sample, not judged by a " +
    "person. The public-data audit found and fixed one mislabel.");
}

// 10 — evaluation protocol
{
  const s = light("Evaluation protocol", "Method · measurement");
  const ctrls = [
    ["Frozen split", "48 held-out cases never examined during development."],
    ["Frozen prompts", "Instructions fingerprinted by hash before the held-out run."],
    ["Repetitions", "Two runs per system–case pair; 288 graded runs in total."],
    ["Pinned model", "Claude Haiku 4.5, fixed identifier and effort level."],
  ];
  ctrls.forEach(([h, d], i) => {
    const y = 1.72 + i * 1.1;
    card(s, M, y, 5.85, 0.95);
    T(s, h, { x: M + 0.35, y: y + 0.18, w: 5.2, h: 0.35, fontSize: 15,
      bold: true, color: TEXT });
    T(s, d, { x: M + 0.35, y: y + 0.52, w: 5.2, h: 0.38, fontSize: 13 });
  });
  card(s, 6.85, 1.72, 5.75, 4.2);
  T(s, "Metrics", { x: 7.2, y: 1.98, w: 5, h: 0.4, fontSize: 15.5, bold: true,
    color: TEXT });
  T(s, [
    { text: "Method-selection accuracy, Wilson 95% intervals",
      options: { bullet: true, breakLine: true } },
    { text: "Abstention recall and unsafe-selection rate",
      options: { bullet: true, breakLine: true } },
    { text: "Report validity under the provenance contract",
      options: { bullet: true, breakLine: true } },
    { text: "Failure stage from an error taxonomy",
      options: { bullet: true } },
  ], { x: 7.2, y: 2.45, w: 5.1, h: 1.75, fontSize: 13.5, paraSpaceAfter: 7 });
  T(s, "Inference", { x: 7.2, y: 4.3, w: 5, h: 0.35, fontSize: 15.5,
    bold: true, color: TEXT });
  T(s, "Paired at case level: repetitions collapse to a per-case majority, then " +
    "McNemar's exact test with a case-level bootstrap interval.",
    { x: 7.2, y: 4.7, w: 5.1, h: 1.05, fontSize: 13, lineSpacing: 18 });
  folio(s);
  s.addNotes("Why per-case majority: McNemar assumes independent pairs, and two " +
    "runs of the same case are not two cases. Counting both would inflate n.");
}

// 11 — result: accuracy
{
  const s = light("Result: method-selection accuracy", "Held-out evaluation · H1");
  figure(s, "accuracy", M, 1.72, 7.75, 4.65);
  readout(s, 8.65, 1.72, 3.95, 4.65, "C OVER B", "+25 pts", C_COL,
    "The protocol arm beats tool access alone against a target of +10. " +
    "Both arms hold identical tools and an identical report schema.",
    "Tools without a protocol scored below no tools at all.");
  folio(s);
  s.addNotes("Name the three numbers — 75, 67, 89 — then point at B. The version " +
    "with tools and no procedure is the lowest of the three. That is the most " +
    "surprising line in the results.");
}

// 12 — result: paired comparisons
{
  const s = light("Result: which differences are real", "Held-out evaluation · significance");
  figure(s, "paired", M, 1.72, W - 2 * M, 3.3);
  card(s, M, 5.25, 5.75, 1.15);
  T(s, "Established", { x: M + 0.35, y: 5.43, w: 5, h: 0.35, fontSize: 15,
    bold: true, color: C_COL });
  T(s, "C over B, p = 0.0018 — H1 is supported.", { x: M + 0.35, y: 5.8,
    w: 5.1, h: 0.45, fontSize: 13.5 });
  card(s, 6.85, 5.25, 5.75, 1.15);
  T(s, "Not established", { x: 7.2, y: 5.43, w: 5, h: 0.35, fontSize: 15,
    bold: true, color: AMBER });
  T(s, "C over A points the right way but does not clear 0.05 on 48 cases.",
    { x: 7.2, y: 5.8, w: 5.1, h: 0.45, fontSize: 13.5 });
  folio(s);
  s.addNotes("Solid and filled means significant; dashed and hollow means not. " +
    "Read the second row aloud and say you report it as unresolved. Volunteering " +
    "this is what makes the first row credible.");
}

// 13 — result: abstention
{
  const s = light("Result: recognising an invalid design", "Held-out evaluation · H2");
  figure(s, "abstention", M, 1.72, 7.75, 4.65);
  readout(s, 8.65, 1.72, 3.95, 4.65, "ON 18 DESIGN-HAZARD RUNS", "78%", C_COL,
    "The protocol arm declined correctly on the cases where every available " +
    "method is invalid. The tool-enabled baseline never declined once.",
    "The sharpest separation in the study — H2 is supported.");
  folio(s);
  s.addNotes("This is the safety result. B answering every hazard case means B " +
    "fitted a real method to data whose design rules it out, every time.");
}

// 14 — result: report grounding
{
  const s = light("Result: could the report be grounded?", "Held-out evaluation · H3");
  figure(s, "validity", M, 1.72, 7.75, 4.65);
  readout(s, 8.65, 1.72, 3.95, 4.65, "DIRECT BASELINE", "43 / 96", B_COL,
    "reports cited a number no tool produced, or a diagnostic never run. The " +
    "contract rejected every one before it reached a reader.",
    "No fabricated number shipped in any arm — H3 is supported.");
  folio(s);
  s.addNotes("Explain why B scores 100% here: it has tools and uses them, so its " +
    "numbers are real. Its failure is choosing the wrong method, not inventing " +
    "figures. The two metrics measure different things.");
}

// 15 — result: failure taxonomy
{
  const s = light("Result: where each system fails", "Held-out evaluation · error analysis");
  figure(s, "failures", M, 1.72, 7.75, 4.65);
  readout(s, 8.65, 1.72, 3.95, 4.65, "DESIGN-VALIDATION FAILURES", "20 → 4",
    C_COL,
    "Tool-only against protocol. The failures that remain in System C are " +
    "mostly diagnostic reasoning, not design.",
    "The protocol removed the failure it was built to remove.");
  folio(s);
  s.addNotes("Total failures: A 24, B 32, C 11. The point is the design-validation " +
    "segment — B has 20, C has 4. That is the mechanism behind every other " +
    "result.");
}

// 16 — result: risk-coverage
{
  const s = light("Result: the coverage it gave up, and why", "Held-out evaluation · risk–coverage");
  figure(s, "coverage", M, 1.72, 6.2, 4.65);
  readout(s, 7.1, 1.72, 5.5, 4.65, "SELECTIVE ACCURACY", "87%", C_COL,
    "System C answered 85% of cases and was right on 87% of those. A and B " +
    "answered nearly everything — 95% and 98% — and were right less often.",
    "Declining when it should is what lifts accuracy. It is not caution " +
    "for its own sake.");
  folio(s);
  s.addNotes("If asked whether C just refuses more: no. Lower coverage came with " +
    "higher accuracy on what it did answer, which is the signature of declining " +
    "the right cases rather than declining at random.");
}

// 17 — hypotheses revisited
{
  const s = light("Hypotheses revisited", "Findings");
  const rows = [
    ["H1", "Selection", "Supported", C_COL,
     "C over B: +25 points, McNemar p = 0.0018, 95% CI [+12.5, +39.6]."],
    ["H2", "Abstention", "Supported", C_COL,
     "Declined correctly 78% of the time; the tool baseline 0%."],
    ["H3", "Provenance", "Supported", C_COL,
     "51 ungrounded reports rejected across all arms; none reached a reader."],
    ["—", "C over A", "Unresolved", AMBER,
     "+12.5 points, p = 0.0703. Direction favours C; the sample cannot settle it."],
  ];
  rows.forEach(([k, name, verdict, col, d], i) => {
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
  s.addNotes("Three supported, one unresolved. Keep the unresolved row on the " +
    "slide — a findings table with no caveat reads as a sales pitch.");
}

// 18 — measurement rigour
{
  const s = light("Two defects found in the measurement itself", "Rigour");
  const d = [
    ["1", "A rejected report is not a lost run",
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
  ];
  d.forEach(([k, h, body, fix], i) => {
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
  s.addNotes("If asked what was hardest, this is the answer. The system worked; " +
    "the measurement had two silent defects that would each have produced a " +
    "wrong headline.");
}

// 19 — limitations
{
  const s = light("Limitations and threats to validity", "What the evidence does not support");
  const lim = [
    ["Model", "Held-out claims are scoped to Claude Haiku 4.5. Generalising to " +
     "frontier models requires re-running the evaluation."],
    ["Power", "Two repetitions and 48 cases. Enough to establish the primary " +
     "comparison; not enough to resolve C over A."],
    ["Interpretation", "The blinded scoring round failed its reliability check " +
     "(κ = −0.044). The metric is withheld rather than reported unreliably."],
    ["Review", "No independent second reviewer for the 16 public-data labels."],
    ["Scope", "Paired, repeated-measures, mixed, time-series and survival designs " +
     "are excluded from the library and tested only as abstention cases."],
  ];
  lim.forEach(([k, d], i) => {
    const y = 1.72 + i * 0.93;
    card(s, M, y, W - 2 * M, 0.8);
    T(s, k.toUpperCase(), { x: M + 0.35, y: y + 0.26, w: 2.0, h: 0.3,
      fontSize: 11.5, bold: true, charSpacing: 1.5, color: AMBER });
    T(s, d, { x: M + 2.45, y: y + 0.13, w: 9.2, h: 0.58, fontSize: 13.5,
      lineSpacing: 18.5 });
  });
  folio(s);
  s.addNotes("Deliver this calmly and without apology. Each limit is known, " +
    "bounded and disclosed in the report.");
}

// 20 — contributions
{
  const s = light("Contributions", "Conclusion");
  const c = [
    ["Controlled evidence",
     "A three-arm ablation over one shared core, showing that a decision protocol " +
     "— not tool access — drives valid method selection."],
    ["A benchmark that scores declining",
     "64 cases with construction-derived labels, twelve of which reward " +
     "abstention, turning a scope limit into a measurable behaviour."],
    ["Provenance by construction",
     "A report format in which a number without a recorded source cannot " +
     "exist, rather than one checked for fabrication afterwards."],
  ];
  c.forEach(([h, d], i) => {
    const y = 1.72 + i * 1.5;
    card(s, M, y, W - 2 * M, 1.32);
    badge(s, String(i + 1), C_COL, M + 0.4, y + 0.4, 0.52);
    T(s, h, { x: M + 1.2, y: y + 0.25, w: 10.4, h: 0.42, fontFace: H,
      fontSize: 18, bold: true, color: TEXT });
    T(s, d, { x: M + 1.2, y: y + 0.7, w: 10.4, h: 0.55, fontSize: 14,
      lineSpacing: 19 });
  });
  T(s, "Structure, not tooling, is what makes an LLM a reliable statistician.",
    { x: M, y: 6.3, w: W - 2 * M, h: 0.45, fontFace: H, fontSize: 17,
      bold: true, color: C_COL });
  folio(s);
  s.addNotes("End the findings on the one-line conclusion. Pause after it.");
}

// 21 — future work
{
  const s = light("Future work", "Next steps");
  const f = [
    ["Resolve C over A", "Enlarge the held-out set and repetitions to give the " +
     "comparison the power it currently lacks."],
    ["Frontier models", "Re-run the frozen evaluation on larger models to test " +
     "whether the protocol's gain persists as base capability rises."],
    ["Interpretation scoring", "Run a second blinded round with the rebuilt " +
     "rubric and two independent raters."],
    ["Wider method library", "Extend to paired, mixed-effects and time-series " +
     "designs now tested only as abstentions."],
  ];
  f.forEach(([h, d], i) => {
    const x = M + (i % 2) * 6.1, y = 1.72 + Math.floor(i / 2) * 2.3;
    card(s, x, y, 5.9, 2.1);
    T(s, h, { x: x + 0.4, y: y + 0.3, w: 5.1, h: 0.42, fontFace: H,
      fontSize: 17, bold: true, color: TEXT });
    T(s, d, { x: x + 0.4, y: y + 0.82, w: 5.1, h: 1.1, fontSize: 14,
      lineSpacing: 20 });
  });
  folio(s);
  s.addNotes("Frame the first item as the natural next experiment, not as a " +
    "weakness: the current design already tells you exactly how much larger " +
    "the sample needs to be.");
}

// 22 — artefacts and questions
{
  const s = dark();
  T(s, "See it running", { x: M, y: 1.3, w: 9, h: 0.75, fontFace: H,
    fontSize: 36, bold: true, color: "FFFFFF" });
  T(s, "Every case, every answer each system gave, and every step it took — " +
    "inspectable without installing anything.",
    { x: M, y: 2.12, w: 10, h: 0.6, fontSize: 16, color: ICE });
  const links = [
    ["LIVE EVALUATION", "ai-statistician.netlify.app",
     "https://ai-statistician.netlify.app", C_COL],
    ["SOURCE, DATA AND LOGS", "github.com/Vishal4507/AI_statistician",
     "https://github.com/Vishal4507/AI_statistician", ICE],
  ];
  links.forEach(([k, label, url, col], i) => {
    const x = M + i * 6.1;
    s.addShape(p.ShapeType.roundRect, { x, y: 3.05, w: 5.9, h: 1.5,
      rectRadius: 0.06, fill: { color: INK_SOFT },
      line: { color: "35485A", width: 1 } });
    T(s, k, { x: x + 0.4, y: 3.3, w: 5.1, h: 0.28, fontSize: 10.5,
      bold: true, charSpacing: 2, color: MUTED });
    T(s, label, { x: x + 0.4, y: 3.66, w: 5.2, h: 0.5, fontSize: 17,
      bold: true, color: col, hyperlink: { url } });
  });
  T(s, "Thank you — questions welcome.", { x: M, y: 5.35, w: 9, h: 0.55,
    fontFace: H, fontSize: 24, bold: true, color: "FFFFFF" });
  folio(s, true);
  s.addNotes("If time allows, open the live site and show the Seoul bike case: " +
    "System C declines while A and B both fit a model.");
}

p.writeFile({ fileName: OUT }).then((f) => console.log("wrote " + f));
