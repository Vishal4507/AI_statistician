// Presentation deck for the AI Statistician capstone.
// Written for an audience with no statistics and no AI background.
const pptx = require("pptxgenjs");
const path = require("path");

const OUT = "/Users/vishal/ai-statistician/docs/AI_Statistician_Presentation.pptx";
const FIG = "/Users/vishal/ai-statistician/reports/figures";

// ---- palette ---------------------------------------------------------------
const INK      = "14202B";   // dominant dark
const INK_SOFT = "22303D";
const PAPER    = "F4F7FA";   // light content ground
const CARD     = "FFFFFF";
const TEXT     = "16222E";
const TEXT_2   = "4A5A69";
const MUTED    = "8496A6";
const A_COL    = "2F6FD0";   // system A — carried from the report figures
const B_COL    = "DD6027";   // system B
const C_COL    = "129B68";   // system C
const AMBER    = "C8891B";
const ICE      = "CFE0F2";

const H = "Cambria";         // header face
const B = "Calibri";         // body face

const p = new pptx();
p.layout = "LAYOUT_WIDE";    // 13.3 x 7.5
p.author = "Vishal Dhinesh Kumar";
p.title = "AI Statistician";

const W = 13.3, HT = 7.5, M = 0.7;

// ---- helpers ---------------------------------------------------------------
function darkSlide() {
  const s = p.addSlide();
  s.background = { color: INK };
  return s;
}
function lightSlide(title, kicker) {
  const s = p.addSlide();
  s.background = { color: PAPER };
  if (kicker) {
    s.addText(kicker.toUpperCase(), {
      x: M, y: 0.52, w: 8, h: 0.28, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 11, bold: true, charSpacing: 2, color: MUTED,
    });
  }
  s.addText(title, {
    x: M, y: 0.84, w: W - 2 * M, h: 0.72, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 32, bold: true, color: TEXT,
  });
  return s;
}
// the deck's one repeated motif: a lettered disc for each system
function badge(s, letter, color, x, y, d = 0.52) {
  s.addShape(p.ShapeType.ellipse, {
    x, y, w: d, h: d, fill: { color }, line: { color, width: 0 },
  });
  s.addText(letter, {
    x, y, w: d, h: d, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 16, bold: true, color: "FFFFFF",
    align: "center", valign: "middle",
  });
}
function card(s, x, y, w, h, fill = CARD) {
  s.addShape(p.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.06, fill: { color: fill },
    line: { color: "E2E9F0", width: 1 },
    shadow: { type: "outer", angle: 90, blur: 10, offset: 2,
              color: "9FB0C0", opacity: 0.22 },
  });
}

// ============================================================ 1. title ======
{
  const s = darkSlide();
  s.addText("Can an AI be trusted", {
    x: M, y: 2.02, w: 10.4, h: 0.80, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 44, bold: true, color: "FFFFFF",
  });
  s.addText("to choose the right statistical test?", {
    x: M, y: 2.90, w: 10.4, h: 0.85, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 44, bold: true, color: C_COL,
  });
  s.addText(
    "Building an AI that knows when it should not answer — and measuring whether that helps.",
    { x: M, y: 3.95, w: 9.6, h: 0.5, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 16, color: ICE });
  ["A", "B", "C"].forEach((l, i) =>
    badge(s, l, [A_COL, B_COL, C_COL][i], M + i * 0.68, 4.75, 0.52));
  s.addText("Vishal Dhinesh Kumar   ·   Capstone Project", {
    x: M, y: 6.45, w: 9, h: 0.32, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 13, color: MUTED });
  s.addNotes("Opening line: every one of us has asked an AI a question and gotten " +
    "a confident answer back. This project asks a narrower question — when the " +
    "task is statistics, is that confident answer actually correct? And can we " +
    "build something that knows when to stop?");
}

// ========================================================== 2. problem ======
{
  const s = lightSlide("An AI always gives you an answer", "The problem");
  s.addText(
    "That is the feature. It is also the danger. Ask it to analyse data and it " +
    "will produce something that reads well, uses the right words, and does the " +
    "arithmetic correctly.",
    { x: M, y: 1.72, w: 6.1, h: 1.1, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 16, color: TEXT_2, lineSpacing: 24 });
  s.addText("None of that tells you the answer is valid.", {
    x: M, y: 2.95, w: 6.1, h: 0.5, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 21, bold: true, color: TEXT });
  s.addText(
    "Validity depends on how the data was collected — facts a spreadsheet cannot " +
    "show you. Were these measurements independent? Is the same person in there " +
    "twice? Are the rows in time order?",
    { x: M, y: 3.55, w: 6.1, h: 1.45, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 16, color: TEXT_2, lineSpacing: 24 });

  card(s, 7.3, 1.62, 5.3, 4.1);
  s.addText("The failure nobody notices", {
    x: 7.7, y: 1.95, w: 4.5, h: 0.36, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 13, bold: true, charSpacing: 1, color: MUTED });
  [
    ["Well written", "Reads like a real analysis"],
    ["Arithmetic correct", "Every number adds up"],
    ["Method invalid", "The wrong test for this data"],
  ].forEach(([t, d], i) => {
    const y = 2.5 + i * 0.95;
    const col = i === 2 ? B_COL : C_COL;
    s.addShape(p.ShapeType.ellipse, {
      x: 7.7, y: y + 0.06, w: 0.3, h: 0.3,
      fill: { color: col }, line: { color: col, width: 0 } });
    s.addText(i === 2 ? "✕" : "✓", {
      x: 7.7, y: y + 0.06, w: 0.3, h: 0.3, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 13, bold: true, color: "FFFFFF",
      align: "center", valign: "middle" });
    s.addText(t, { x: 8.15, y, w: 4.1, h: 0.34, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 16, bold: true, color: TEXT });
    s.addText(d, { x: 8.15, y: y + 0.34, w: 4.1, h: 0.34, isTextBox: true,
      margin: 0, fontFace: B, fontSize: 13, color: TEXT_2 });
  });
  s.addText("A confident, wrong answer is worse than no answer.", {
    x: 7.7, y: 5.16, w: 4.6, h: 0.5, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 14, italic: true, color: B_COL });
  s.addNotes("The point to land: the three things people use to judge whether an " +
    "answer is good — it reads well, the maths checks out, it sounds confident — " +
    "are exactly the three things that stay true when the method is wrong.");
}

// ========================================================== 3. example ======
{
  const s = lightSlide("A real example from the project", "What that looks like");
  card(s, M, 1.62, 5.7, 4.2);
  s.addText("Seoul bike rentals", {
    x: M + 0.4, y: 1.95, w: 4.9, h: 0.4, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 20, bold: true, color: TEXT });
  s.addText("8,760 rows — one for every hour of a year.", {
    x: M + 0.4, y: 2.38, w: 4.9, h: 0.32, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 14, color: MUTED });
  s.addText([
    { text: "Question: does temperature affect how many bikes are rented?",
      options: { bullet: true, breakLine: true } },
    { text: "The table looks perfect for a standard correlation test.",
      options: { bullet: true, breakLine: true } },
    { text: "Every AI tested reached for exactly that test.",
      options: { bullet: true } },
  ], { x: M + 0.4, y: 2.95, w: 4.9, h: 1.6, isTextBox: true, margin: 0,
       fontFace: B, fontSize: 15, color: TEXT_2, paraSpaceAfter: 10 });
  s.addText("And it is the wrong test.", {
    x: M + 0.4, y: 4.75, w: 4.9, h: 0.45, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 19, bold: true, color: B_COL });

  card(s, 6.9, 1.62, 5.7, 4.2);
  s.addText("Why it is wrong", {
    x: 7.3, y: 1.95, w: 4.9, h: 0.4, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 20, bold: true, color: TEXT });
  s.addText(
    "That test assumes each row is independent of the others. But 2pm looks like " +
    "1pm because it is one hour later on the same day — the rows carry each " +
    "other's information.",
    { x: 7.3, y: 2.45, w: 4.9, h: 1.3, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 15, color: TEXT_2, lineSpacing: 22 });
  s.addText(
    "Nothing in the spreadsheet says so. You only know it because you know how " +
    "the data was collected.",
    { x: 7.3, y: 3.8, w: 4.9, h: 0.9, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 15, color: TEXT_2, lineSpacing: 22 });
  s.addText("The correct answer is to decline.", {
    x: 7.3, y: 4.75, w: 4.9, h: 0.45, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 19, bold: true, color: C_COL });
  s.addNotes("This is the whole project in one slide. If the audience takes away " +
    "only one thing, it should be that the data looked fine and the answer was " +
    "still wrong, and the reason lives outside the file.");
}

// ========================================================= 4. question ======
{
  const s = darkSlide();
  s.addText("THE QUESTION", {
    x: M, y: 1.5, w: 8, h: 0.3, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 11, bold: true, charSpacing: 2, color: MUTED });
  s.addText("If you give an AI the right tools, does it use them well?", {
    x: M, y: 2.0, w: 11.2, h: 1.5, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 38, bold: true, color: "FFFFFF", lineSpacing: 46 });
  s.addText(
    "Or does it also need a fixed procedure telling it what to check, in what " +
    "order, before it is allowed to answer?",
    { x: M, y: 3.75, w: 10.2, h: 0.9, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 18, color: ICE, lineSpacing: 28 });
  s.addText(
    "To answer that fairly, I built three versions that differ in exactly one way.",
    { x: M, y: 5.2, w: 10.2, h: 0.5, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 16, italic: true, color: C_COL });
  s.addNotes("Emphasise 'exactly one way' — that is what makes it an experiment " +
    "rather than a demo. Same tools, same output format, same everything except " +
    "whether a procedure governs the order of work.");
}

// ==================================================== 5. three versions =====
{
  const s = lightSlide("Three versions, one difference", "The experiment");
  const rows = [
    ["A", A_COL, "Just ask the AI",
     "No tools. It answers from what it knows, like asking a knowledgeable colleague."],
    ["B", B_COL, "Give it the tools",
     "It can run real statistical tests, in whatever order it likes. No procedure."],
    ["C", C_COL, "Tools plus a procedure",
     "Same tools — but it must check the study design first, and may decline."],
  ];
  rows.forEach(([l, col, t, d], i) => {
    const y = 1.72 + i * 1.42;
    card(s, M, y, W - 2 * M, 1.22);
    badge(s, l, col, M + 0.42, y + 0.35, 0.54);
    s.addText(t, { x: M + 1.22, y: y + 0.26, w: 3.5, h: 0.38, isTextBox: true,
      margin: 0, fontFace: H, fontSize: 19, bold: true, color: TEXT });
    s.addText(d, { x: M + 4.9, y: y + 0.28, w: 6.6, h: 0.7, isTextBox: true,
      margin: 0, fontFace: B, fontSize: 15, color: TEXT_2, lineSpacing: 21 });
  });
  s.addText(
    "A and B are the honest comparisons. If C wins, it is the procedure that " +
    "won — not better tools, and not a better model.",
    { x: M, y: 6.1, w: 11.4, h: 0.6, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 15, italic: true, color: TEXT_2 });
  s.addNotes("All three share one codebase. The tools, the output format and the " +
    "model are identical. Only the control flow differs, so the comparison cannot " +
    "be accused of stacking the deck.");
}

// ======================================================== 6. idea one =======
{
  const s = lightSlide("“I don’t know” is an allowed answer", "Design idea 1");
  s.addText(
    "The AI chooses from a fixed menu of 14 statistical methods. It cannot " +
    "invent one, and it cannot write its own code to escape the menu.",
    { x: M, y: 1.72, w: 6.0, h: 1.0, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 16, color: TEXT_2, lineSpacing: 24 });
  s.addText("There is a fifteenth option: decline.", {
    x: M, y: 2.85, w: 6.0, h: 0.45, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 21, bold: true, color: C_COL });
  s.addText(
    "Declining is not a failure. On 12 of the 64 test problems, declining is the " +
    "only correct answer — the study design rules out every method available.",
    { x: M, y: 3.42, w: 6.0, h: 1.0, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 16, color: TEXT_2, lineSpacing: 24 });
  s.addText(
    "This turns a limitation into something measurable. Knowing when to stop " +
    "becomes a score, not an excuse.",
    { x: M, y: 4.55, w: 6.0, h: 0.8, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 15, italic: true, color: TEXT_2, lineSpacing: 22 });

  card(s, 7.2, 1.62, 5.4, 4.3);
  s.addText("64 test problems", {
    x: 7.6, y: 1.92, w: 4.6, h: 0.38, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 13, bold: true, charSpacing: 1, color: MUTED });
  s.addText("52", { x: 7.6, y: 2.42, w: 1.5, h: 0.85, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 52, bold: true, color: C_COL });
  s.addText("have a correct method to use", {
    x: 9.15, y: 2.72, w: 3.2, h: 0.5, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 14, color: TEXT_2 });
  s.addText("12", { x: 7.6, y: 3.6, w: 1.5, h: 0.85, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 52, bold: true, color: AMBER });
  s.addText("have none — declining is the right answer", {
    x: 9.15, y: 3.8, w: 3.2, h: 0.7, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 14, color: TEXT_2 });
  s.addText(
    "Those 12 are the safety test. Answering them at all is the dangerous mistake.",
    { x: 7.6, y: 4.85, w: 4.7, h: 0.75, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 13, italic: true, color: MUTED, lineSpacing: 19 });
  s.addNotes("The menu being closed is what makes the task scorable. If the AI " +
    "could invent methods, judging its choice would be an essay-grading problem.");
}

// ======================================================== 7. idea two =======
{
  const s = lightSlide("The AI is not allowed to type a number", "Design idea 2");
  s.addText(
    "The biggest risk with an AI writing a report is that it produces a " +
    "convincing number that came from nowhere.",
    { x: M, y: 1.72, w: 11.4, h: 0.82, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 17, color: TEXT_2, lineSpacing: 25 });
  s.addText(
    "Rather than checking the finished report for invented numbers, the system " +
    "makes inventing them impossible.",
    { x: M, y: 2.62, w: 11.4, h: 0.72, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 20, bold: true, color: TEXT });

  const steps = [
    ["Every result is filed", "When a real calculation runs, its answer is stored under a label."],
    ["The AI writes labels", "In its report it writes the label, never a digit."],
    ["The label is swapped", "At the end, each label is replaced by the stored number."],
    ["Unknown label fails", "If it invents a label, the whole run is rejected."],
  ];
  steps.forEach(([t, d], i) => {
    const x = M + i * 3.05;
    card(s, x, 3.48, 2.85, 2.25);
    s.addText(String(i + 1), {
      x: x + 0.28, y: 3.70, w: 0.6, h: 0.55, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 30, bold: true, color: i === 3 ? B_COL : C_COL });
    s.addText(t, { x: x + 0.28, y: 4.32, w: 2.35, h: 0.48, isTextBox: true,
      margin: 0, fontFace: B, fontSize: 15, bold: true, color: TEXT });
    s.addText(d, { x: x + 0.28, y: 4.86, w: 2.35, h: 0.78, isTextBox: true,
      margin: 0, fontFace: B, fontSize: 12.5, color: TEXT_2, lineSpacing: 17 });
  });
  s.addText(
    "Every number in every report traces back to a calculation that actually ran.",
    { x: M, y: 5.95, w: 11.4, h: 0.5, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 15, italic: true, color: C_COL });
  s.addNotes("Analogy that works well: it is the difference between checking a " +
    "receipt for fraud and building a till that cannot print a line without a " +
    "scanned barcode behind it.");
}

// ========================================================= 8. testing =======
{
  const s = lightSlide("How it was tested", "The method");
  const stats = [
    ["64", "problems built\nfrom scratch", C_COL],
    ["48", "locked away\nuntil the end", A_COL],
    ["288", "graded runs\nacross 3 versions", INK],
  ];
  stats.forEach(([n, l, col], i) => {
    const x = M + i * 3.0;
    s.addText(n, { x, y: 1.75, w: 2.7, h: 1.0, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 58, bold: true, color: col });
    s.addText(l, { x, y: 2.82, w: 2.7, h: 0.8, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 14, color: TEXT_2, lineSpacing: 19 });
  });
  card(s, 9.9, 1.68, 2.7, 2.1);
  s.addText("Half the problems came from real public datasets, half were built " +
    "so the correct answer is known by construction.", {
    x: 10.2, y: 1.95, w: 2.1, h: 1.6, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 12.5, color: TEXT_2, lineSpacing: 17 });

  s.addText("The part that makes it a fair test", {
    x: M, y: 4.1, w: 11.4, h: 0.45, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 21, bold: true, color: TEXT });
  s.addText([
    { text: "48 of the 64 problems were sealed away and never looked at while building.",
      options: { bullet: true, breakLine: true } },
    { text: "The instructions given to the AI were frozen and fingerprinted before those ran.",
      options: { bullet: true, breakLine: true } },
    { text: "Each problem was run twice per version, to see whether answers stayed stable.",
      options: { bullet: true } },
  ], { x: M, y: 4.65, w: 11.4, h: 1.5, isTextBox: true, margin: 0,
       fontFace: B, fontSize: 15, color: TEXT_2, paraSpaceAfter: 9 });
  s.addNotes("Why this matters: without the sealed set, good results would just " +
    "mean the instructions had been tuned against the answers. The freeze is what " +
    "makes the number believable.");
}

// ========================================================== 9. result =======
{
  const s = lightSlide("How often did each version pick correctly?", "Result");
  s.addChart(p.ChartType.bar, [{
    name: "Correct choice",
    labels: ["A · Just ask", "B · Tools only", "C · Tools + procedure"],
    values: [75.0, 66.7, 88.5],
  }], {
    x: M, y: 1.75, w: 7.5, h: 4.25,
    barDir: "col", barGapWidthPct: 60,
    chartColors: [A_COL, B_COL, C_COL], varyColors: true,
    showTitle: false, showLegend: false,
    showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: '0.0"%"', dataLabelFontSize: 15,
    dataLabelFontBold: true, dataLabelColor: TEXT,
    valAxisMaxVal: 100, valAxisMinVal: 0,
    valAxisLabelColor: MUTED, catAxisLabelColor: TEXT_2,
    valAxisLabelFontSize: 11, catAxisLabelFontSize: 13,
    valGridLine: { color: "E2E9F0", size: 1 },
    catGridLine: { style: "none" },
  });
  card(s, 8.6, 1.75, 4.0, 4.25);
  s.addText("What this says", {
    x: 8.95, y: 2.02, w: 3.3, h: 0.38, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 13, bold: true, charSpacing: 1, color: MUTED });
  s.addText("+25", { x: 8.95, y: 2.45, w: 3.3, h: 0.8, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 48, bold: true, color: C_COL });
  s.addText("percentage points better than tools alone", {
    x: 8.95, y: 3.25, w: 3.3, h: 0.6, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 14, color: TEXT_2, lineSpacing: 19 });
  s.addText(
    "The target set at the start of the project was 10 points. This is a genuine " +
    "result, not a rounding difference.",
    { x: 8.95, y: 4.0, w: 3.3, h: 1.0, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 13.5, color: TEXT_2, lineSpacing: 19 });
  s.addText("Giving tools without a procedure did not help at all.", {
    x: 8.95, y: 5.05, w: 3.3, h: 0.75, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 13.5, italic: true, color: B_COL, lineSpacing: 19 });
  s.addNotes("Point at B. The version with tools and no procedure scored lower " +
    "than the version with no tools at all. Tools did not rescue it — the ordering " +
    "is what carried the gain.");
}

// ======================================================== 10. honesty =======
{
  const s = lightSlide("What the evidence does and does not support", "Being honest");
  card(s, M, 1.72, 5.75, 3.05);
  s.addShape(p.ShapeType.ellipse, { x: M + 0.4, y: 2.05, w: 0.34, h: 0.34,
    fill: { color: C_COL }, line: { color: C_COL, width: 0 } });
  s.addText("✓", { x: M + 0.4, y: 2.05, w: 0.34, h: 0.34, isTextBox: true,
    margin: 0, fontFace: B, fontSize: 14, bold: true, color: "FFFFFF",
    align: "center", valign: "middle" });
  s.addText("Established", { x: M + 0.9, y: 2.0, w: 4.4, h: 0.42, isTextBox: true,
    margin: 0, fontFace: H, fontSize: 20, bold: true, color: TEXT });
  s.addText(
    "The procedure beats tools alone by 25 points. The odds of seeing a gap this " +
    "large by chance are under 2 in 1,000.",
    { x: M + 0.4, y: 2.6, w: 5.0, h: 1.0, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 15, color: TEXT_2, lineSpacing: 22 });
  s.addText(
    "It also declined correctly 78% of the time on the dangerous problems, where " +
    "the tools-only version never did.",
    { x: M + 0.4, y: 3.62, w: 5.0, h: 1.0, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 15, color: TEXT_2, lineSpacing: 22 });

  card(s, 6.85, 1.72, 5.75, 3.05);
  s.addShape(p.ShapeType.ellipse, { x: 7.25, y: 2.05, w: 0.34, h: 0.34,
    fill: { color: AMBER }, line: { color: AMBER, width: 0 } });
  s.addText("!", { x: 7.25, y: 2.05, w: 0.34, h: 0.34, isTextBox: true,
    margin: 0, fontFace: B, fontSize: 14, bold: true, color: "FFFFFF",
    align: "center", valign: "middle" });
  s.addText("Not established", { x: 7.75, y: 2.0, w: 4.4, h: 0.42,
    isTextBox: true, margin: 0, fontFace: H, fontSize: 20, bold: true,
    color: TEXT });
  s.addText(
    "Against the no-tools version the procedure leads by 12.5 points — but on 48 " +
    "problems that gap is not large enough to rule out chance.",
    { x: 7.25, y: 2.6, w: 5.0, h: 1.15, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 15, color: TEXT_2, lineSpacing: 22 });
  s.addText(
    "I report it as unresolved rather than as a win. A bigger test would settle it.",
    { x: 7.25, y: 3.78, w: 5.0, h: 0.8, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 15, italic: true, color: TEXT_2, lineSpacing: 22 });

  s.addText(
    "Reporting the second box is the point. A result you only believe when it " +
    "agrees with you is not a result.",
    { x: M, y: 5.15, w: 11.4, h: 0.6, isTextBox: true, margin: 0,
      fontFace: H, fontSize: 18, bold: true, color: TEXT });
  s.addNotes("This slide is the one an examiner will respect most. Do not rush it. " +
    "The willingness to put the weak comparison on a slide is what separates a " +
    "measurement from a sales pitch.");
}

// ==================================================== 11. made-up numbers ===
{
  const s = lightSlide("Could each version explain itself honestly?", "The second test");
  s.addText(
    "Choosing the right method is only half the job. The other half is describing " +
    "what was found without inventing any part of it.",
    { x: M, y: 1.72, w: 11.4, h: 0.72, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 16, color: TEXT_2, lineSpacing: 24 });

  const rows = [
    ["A", A_COL, "Just ask", 43, "wrote a number that no calculation produced, or cited a check it never ran"],
    ["B", B_COL, "Tools only", 0, "never did — it had tools and used them"],
    ["C", C_COL, "Tools + procedure", 8, "occasionally reached for a result it had not computed"],
  ];
  rows.forEach(([l, col, name, n, d], i) => {
    const y = 2.5 + i * 1.18;
    card(s, M, y, W - 2 * M, 1.0);
    badge(s, l, col, M + 0.35, y + 0.24, 0.5);
    s.addText(name, { x: M + 1.05, y: y + 0.3, w: 2.5, h: 0.4, isTextBox: true,
      margin: 0, fontFace: B, fontSize: 16, bold: true, color: TEXT });
    s.addText(`${n} of 96`, { x: M + 3.6, y: y + 0.26, w: 1.5, h: 0.46,
      isTextBox: true, margin: 0, fontFace: H, fontSize: 22, bold: true,
      color: n > 20 ? B_COL : (n === 0 ? C_COL : AMBER) });
    s.addText(d, { x: M + 5.2, y: y + 0.3, w: 6.3, h: 0.5, isTextBox: true,
      margin: 0, fontFace: B, fontSize: 14, color: TEXT_2 });
  });
  s.addText(
    "Nearly half of the plain AI's analyses could not be grounded. Every one was " +
    "caught automatically rather than reaching a reader.",
    { x: M, y: 6.1, w: 11.4, h: 0.6, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 15, italic: true, color: TEXT_2 });
  s.addNotes("Worth saying out loud: 43 out of 96. If a person had been reading " +
    "those reports they would have had to check every figure by hand to notice.");
}

// ======================================================= 12. self-checks ====
{
  const s = lightSlide("Two mistakes I found in my own measurements",
                       "Checking the checker");
  card(s, M, 1.72, 5.75, 3.6);
  s.addText("1", { x: M + 0.4, y: 1.98, w: 0.6, h: 0.6, isTextBox: true,
    margin: 0, fontFace: H, fontSize: 32, bold: true, color: AMBER });
  s.addText("Throwing away the wrong failures", {
    x: M + 0.4, y: 2.62, w: 5.0, h: 0.42, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 18, bold: true, color: TEXT });
  s.addText(
    "51 runs ended in an error. The obvious move is to discard them. But those " +
    "runs had already chosen a method — and 37 had chosen correctly. Discarding " +
    "them would have made the weakest version look 6 points better than it is.",
    { x: M + 0.4, y: 3.12, w: 5.0, h: 1.9, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 14, color: TEXT_2, lineSpacing: 21 });

  card(s, 6.85, 1.72, 5.75, 3.6);
  s.addText("2", { x: 7.25, y: 1.98, w: 0.6, h: 0.6, isTextBox: true,
    margin: 0, fontFace: H, fontSize: 32, bold: true, color: AMBER });
  s.addText("A result that changed each time I ran it", {
    x: 7.25, y: 2.62, w: 5.0, h: 0.42, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 18, bold: true, color: TEXT });
  s.addText(
    "When the two runs of a problem disagreed, the tie was broken in a way that " +
    "varied between sessions. The same data gave different verdicts on repeat " +
    "analysis. Ties now break the same way every time, and a test enforces it.",
    { x: 7.25, y: 3.12, w: 5.0, h: 1.9, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 14, color: TEXT_2, lineSpacing: 21 });

  s.addText(
    "Neither raised an error. Both were found by looking at the runs before " +
    "building any table — and both are written up in the report.",
    { x: M, y: 5.62, w: 11.4, h: 0.6, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 15, italic: true, color: TEXT_2 });
  s.addNotes("If asked what was hardest: this. The system worked; the way I was " +
    "measuring it did not, and nothing complained. Finding these required " +
    "distrusting my own numbers.");
}

// ========================================================= 13. closing ======
{
  const s = darkSlide();
  s.addText("See it running", {
    x: M, y: 1.35, w: 8, h: 0.75, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 36, bold: true, color: "FFFFFF" });
  s.addText(
    "Every problem, every answer the AI gave, and every step it took to get " +
    "there — nothing to install.",
    { x: M, y: 2.2, w: 9.5, h: 0.6, isTextBox: true, margin: 0,
      fontFace: B, fontSize: 16, color: ICE });

  s.addShape(p.ShapeType.roundRect, {
    x: M, y: 3.1, w: 5.6, h: 1.55, rectRadius: 0.06,
    fill: { color: INK_SOFT }, line: { color: "35485A", width: 1 } });
  s.addText("EXPLORE THE RESULTS", {
    x: M + 0.4, y: 3.38, w: 4.8, h: 0.28, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 10.5, bold: true, charSpacing: 2, color: MUTED });
  s.addText("ai-statistician.netlify.app", {
    x: M + 0.4, y: 3.72, w: 4.9, h: 0.5, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 18, bold: true, color: C_COL,
    hyperlink: { url: "https://ai-statistician.netlify.app" } });

  s.addShape(p.ShapeType.roundRect, {
    x: 6.9, y: 3.1, w: 5.7, h: 1.55, rectRadius: 0.06,
    fill: { color: INK_SOFT }, line: { color: "35485A", width: 1 } });
  s.addText("READ THE CODE", {
    x: 7.3, y: 3.38, w: 4.9, h: 0.28, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 10.5, bold: true, charSpacing: 2, color: MUTED });
  s.addText("github.com/Vishal4507/AI_statistician", {
    x: 7.3, y: 3.72, w: 5.0, h: 0.5, isTextBox: true, margin: 0,
    fontFace: B, fontSize: 16, bold: true, color: ICE,
    hyperlink: { url: "https://github.com/Vishal4507/AI_statistician" } });

  s.addText("Thank you — questions welcome.", {
    x: M, y: 5.5, w: 9, h: 0.5, isTextBox: true, margin: 0,
    fontFace: H, fontSize: 22, bold: true, color: "FFFFFF" });
  s.addNotes("Offer to demonstrate live: open the site, pick the Seoul bike case " +
    "from slide 3, and show the structured version declining while the others " +
    "answer. That demo lands better than any summary.");
}

p.writeFile({ fileName: OUT }).then(f => console.log("wrote " + f));
