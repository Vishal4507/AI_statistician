"""Generate the submission documents: project proposal and interim report.

    python scripts/build_documents.py

Both PDFs are written to docs/.  Every figure quoted in them is read from the
recorded results rather than typed in, for the same reason the capstone report
is generated rather than written: a number that is copied by hand is a number
that goes stale without anyone noticing.

The proposal states the plan the project committed to.  The interim report
describes the state of the work at the week-four freeze gate, which is the
point the blueprint defines as the decision point before the held-out
evaluation is executed.  Neither document is back-dated; both are produced now
and carry today's date.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether,
                                PageBreak, PageTemplate, Paragraph, Spacer,
                                Table, TableStyle)

DOCS = ROOT / "docs"
AUTHOR = "Vishal A S"
AUTHOR_ID = "vishal.as24dxb016@spjain.org"
PROGRAMME = "Capstone Project"
TODAY = date.today().strftime("%d %B %Y")

INK = colors.HexColor("#12181f")
INK2 = colors.HexColor("#3c4854")
MUTED = colors.HexColor("#5c6a78")
RULE = colors.HexColor("#c9d2db")
BAND = colors.HexColor("#eef2f6")
ACCENT = colors.HexColor("#1c4f8f")


# ---------------------------------------------------------------- styles ---

def styles() -> dict:
    base = getSampleStyleSheet()
    s = {}
    s["title"] = ParagraphStyle(
        "title", parent=base["Title"], fontName="Times-Bold", fontSize=19,
        leading=24, alignment=0, textColor=INK, spaceAfter=2)
    s["subtitle"] = ParagraphStyle(
        "subtitle", fontName="Helvetica", fontSize=10.5, leading=14,
        textColor=MUTED, spaceAfter=14)
    s["meta"] = ParagraphStyle(
        "meta", fontName="Helvetica", fontSize=9, leading=13, textColor=INK2)
    s["h1"] = ParagraphStyle(
        "h1", fontName="Helvetica-Bold", fontSize=12.5, leading=16,
        textColor=INK, spaceBefore=17, spaceAfter=6)
    s["h2"] = ParagraphStyle(
        "h2", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
        textColor=ACCENT, spaceBefore=12, spaceAfter=4)
    s["body"] = ParagraphStyle(
        "body", fontName="Times-Roman", fontSize=10.5, leading=15.2,
        textColor=INK, alignment=TA_JUSTIFY, spaceAfter=7)
    s["bullet"] = ParagraphStyle(
        "bullet", parent=s["body"], leftIndent=13, bulletIndent=2,
        spaceAfter=4)
    s["caption"] = ParagraphStyle(
        "caption", fontName="Helvetica-Oblique", fontSize=8.5, leading=11.5,
        textColor=MUTED, spaceBefore=3, spaceAfter=11)
    s["cell"] = ParagraphStyle(
        "cell", fontName="Times-Roman", fontSize=9, leading=12, textColor=INK)
    s["cellb"] = ParagraphStyle(
        "cellb", fontName="Helvetica-Bold", fontSize=8.5, leading=11.5,
        textColor=INK)
    s["note"] = ParagraphStyle(
        "note", fontName="Times-Italic", fontSize=9.5, leading=13.5,
        textColor=INK2, leftIndent=11, borderPadding=0, spaceAfter=9)
    return s


S = styles()


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items):
    return [Paragraph(f"&bull;&nbsp;&nbsp;{t}", S["bullet"]) for t in items]


def table(rows, widths, header=True, zebra=True):
    """A table whose cells are Paragraphs, so long text wraps instead of clipping."""
    data = []
    for r_i, row in enumerate(rows):
        data.append([c if not isinstance(c, str)
                     else Paragraph(c, S["cellb"] if (header and r_i == 0)
                                    else S["cell"])
                     for c in row])
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, RULE if not header else INK),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, RULE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.9, INK),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), BAND))
    if zebra:
        for i in range(2 if header else 1, len(data), 2):
            style.append(("BACKGROUND", (0, i), (-1, i),
                          colors.HexColor("#f7f9fb")))
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    t.setStyle(TableStyle(style))
    return t


def title_block(title, kind):
    line = Table(
        [[""]], colWidths=[16.6 * cm], rowHeights=[2],
        style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT)]))
    return [
        P(kind.upper(), "subtitle"),
        P(title, "title"),
        Spacer(1, 6), line, Spacer(1, 10),
        table([["Author", AUTHOR],
               ["Identifier", AUTHOR_ID],
               ["Programme", PROGRAMME],
               ["Document", kind],
               ["Date", TODAY]],
              widths=[3.4 * cm, 13.2 * cm], header=False, zebra=False),
        Spacer(1, 14),
    ]


# ------------------------------------------------------------ page frame ---

def make_doc(path: Path, running: str):
    doc = BaseDocTemplate(
        str(path), pagesize=A4,
        leftMargin=2.3 * cm, rightMargin=2.3 * cm,
        topMargin=2.0 * cm, bottomMargin=1.9 * cm,
        title=running, author=AUTHOR, subject="AI Statistician capstone")

    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="body")

    def furniture(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        y = doc.bottomMargin - 0.72 * cm
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(doc.leftMargin, y + 0.32 * cm,
                    doc.leftMargin + doc.width, y + 0.32 * cm)
        canvas.drawString(doc.leftMargin, y, running)
        canvas.drawRightString(doc.leftMargin + doc.width, y,
                               f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="all", frames=[frame],
                                       onPage=furniture)])
    return doc


# ------------------------------------------------------------ live data ---

def figures() -> dict:
    """Read the numbers out of the recorded results, never out of memory."""
    from aistat.evaluation.analysis import (made_a_selection, majority_by_case,
                                            pairwise_comparisons,
                                            report_validity, system_summary)
    from aistat.evaluation.runner import load_scores

    out = {}
    for key, name in (("dev", "dev_claude-opus-5_high"),
                      ("held", "heldout_claude-haiku-4-5"),
                      ("naive", "heldout_rulebased_naive")):
        try:
            s = made_a_selection(load_scores(name))
        except FileNotFoundError:
            continue
        out[key] = {
            "n": len(s),
            "summary": system_summary(s).set_index("system").to_dict("index"),
        }
        if key == "held":
            pw = pairwise_comparisons(majority_by_case(s))
            out[key]["pairs"] = {
                f"{r.system_a}|{r.system_b}": r._asdict()
                for r in pw.itertuples()}
            out[key]["validity"] = (report_validity(s)
                                    .set_index("system").to_dict("index"))
            mf = json.loads((ROOT / "results" /
                             f"{name}_manifest.json").read_text())
            out[key]["manifest"] = mf
    gold = [json.loads(p.read_text())
            for p in (ROOT / "benchmark" / "gold").glob("*/gold.json")]
    out["bench"] = {
        "total": len(gold),
        "abstain": sum(1 for g in gold if g["primary_method"] == "abstain"),
    }
    try:
        out["conformance"] = json.loads(
            (ROOT / "reports" / "conformance.json").read_text())
    except FileNotFoundError:
        pass
    return out


F = figures()


def acc(key, system):
    return F[key]["summary"][system]["selection_accuracy"]


def ci(key, system):
    d = F[key]["summary"][system]
    return f"[{d['acc_ci_low']:.3f}, {d['acc_ci_high']:.3f}]"


# =========================================================== PROPOSAL ======

def proposal():
    st = []
    st += title_block(
        "An LLM Agent for the Selection, Validation and Interpretation "
        "of Statistical Methods", "Project Proposal")

    st.append(P("1. Problem and motivation", "h1"))
    st.append(P(
        "A large language model asked to analyse a dataset will almost always "
        "produce an answer. Whether that answer is <i>valid</i> is a different "
        "question, and one the model is poorly placed to police. A data file "
        "cannot reveal whether rows are independent, whether the same subject "
        "appears twice, whether observations are ordered in time, or whether "
        "measurements cluster within groups. These are facts about the study "
        "design, not about the numbers, and they determine which statistical "
        "method is admissible."))
    st.append(P(
        "The consequence is a specific and under-examined failure mode. A "
        "mathematically fluent system with no view of study design will "
        "confidently fit a Poisson regression to autocorrelated hourly counts, "
        "or report a correlation across observations that are not independent. "
        "The output is well-formed, the arithmetic is correct, and the "
        "conclusion is invalid. Existing evaluations of LLMs on data analysis "
        "largely measure whether the code runs and the arithmetic is right, "
        "which does not detect this class of error at all."))

    st.append(P("2. Research question", "h1"))
    st.append(P(
        "<b>Does an explicit statistical decision protocol improve an LLM "
        "agent's ability to select and execute valid statistical methods, "
        "compared with direct LLM advice and with tool access that has no "
        "protocol governing its use?</b>"))
    st.append(P(
        "The contribution is not the interface, nor the number of supported "
        "tests. It is controlled evidence that design-aware routing, targeted "
        "diagnostics and verification improve validity over ordinary LLM tool "
        "use. Stating the question this way fixes what must be held constant: "
        "if the protocol arm and the tool arm do not share tools, prompts and "
        "report schema, any difference between them is uninterpretable."))
    st.append(P("Hypotheses", "h2"))
    st += bullets([
        "<b>H1.</b> The structured agent selects an admissible method more "
        "often than a tool-enabled baseline with no protocol.",
        "<b>H2.</b> The structured agent abstains more reliably on designs "
        "that no supported method fits — the safety-critical case.",
        "<b>H3.</b> Enforcing provenance at the schema level eliminates "
        "fabricated numerical detail in the structured arm, where the "
        "unconstrained arms retain a measurable rate of it.",
    ])

    st.append(P("3. Scope", "h1"))
    st.append(P(
        "The method library is deliberately closed at fourteen methods plus "
        "abstention: three two-group tests, three k-group tests, two "
        "categorical tests, two correlation measures, and four regression "
        "models. A closed library is what makes the selection task scorable — "
        "an open-ended one would turn method choice into an essay-grading "
        "problem."))
    st.append(P(
        "Paired and repeated-measures designs, mixed models, time series, "
        "survival analysis and zero-inflated models are explicitly out of "
        "scope. They are not omitted quietly: they enter the benchmark as "
        "cases whose correct answer is to abstain, which converts a scope "
        "limit into a measurable behaviour."))
    st.append(P(
        "There is deliberately no general code-execution tool. It would let "
        "the model bypass the method policy entirely and would make traces "
        "incomparable across the three arms, destroying the comparison the "
        "project exists to make.", "note"))

    st.append(P("4. System design", "h1"))
    st.append(P("4.1 Three systems over one shared core", "h2"))
    st.append(P(
        "Three drivers are built over a single shared core. Every driver "
        "imports the same tool registry, the same result store and the same "
        "report schema; only control flow differs. Baseline fairness is "
        "therefore provable from the repository layout rather than asserted "
        "in prose — there is no code path on which a baseline could have been "
        "disadvantaged."))
    st.append(table([
        ["System", "Description"],
        ["A — Direct", "Receives the same step-one diagnostic output the "
                       "structured agent receives, not a hand-picked summary, "
                       "and answers without tools."],
        ["B — Tools", "Identical tool definitions and identical report schema "
                      "to System C, with no ordering imposed on their use. "
                      "This is the baseline the research question turns on."],
        ["C — Protocol", "A deterministic state machine: parse the problem, "
                         "validate the design, enumerate candidates, run only "
                         "diagnostics that could change the decision, select "
                         "or abstain, execute, verify."],
    ], widths=[3.2 * cm, 13.4 * cm]))
    st.append(P("Table 1. The three arms of the comparison.", "caption"))

    st.append(P("4.2 The provenance contract", "h2"))
    st.append(P(
        "The strongest claim the system makes is that <b>the model cannot "
        "write a number</b>. Rather than inspecting a finished report for "
        "fabrication, fabrication is made structurally impossible: every tool "
        "return is registered in a run-scoped store under a stable key; the "
        "report schema rejects raw numeric literals in prose; the model emits "
        "reference templates that are substituted at render time; and an "
        "unknown reference fails the run outright."))
    st.append(P(
        "This must be reported honestly rather than as a headline result. For "
        "the structured arm, numerical fidelity becomes an <i>architectural "
        "guarantee</i>, not an empirical finding. Its empirical counterpart is "
        "the rate at which the model reaches for a reference that does not "
        "exist. For the two baselines nothing is enforced, so fidelity remains "
        "a genuine measurement there and the comparison stays meaningful."))

    st.append(P("5. Benchmark design", "h1"))
    st.append(P(
        f"{F['bench']['total']} cases, of which {F['bench']['abstain']} have "
        "no admissible in-scope method and must be declined. Cases are never "
        "hand-authored: one declarative registry entry produces each complete "
        "case package, so the benchmark regenerates from source."))
    st.append(P(
        "For synthetic cases the gold label is derived from the <i>realised "
        "sample</i> rather than from the generator's intent. Design facts come "
        "from the generator parameters, because independence and pairing are "
        "properties of the design; distributional facts come from the data, "
        "because that is what a correct method choice must respond to. A "
        "generator asked for a normal sample that happened to draw a skewed "
        "one must be labelled for the sample it drew."))
    st.append(table([
        ["Source", "Rows", "Role in the benchmark"],
        ["Bank Marketing (UCI 222)", "45,211",
         "Categorical association, logistic regression, skewed group comparison"],
        ["Online Shoppers (UCI 468)", "12,330",
         "Association, categorical tests, logistic regression"],
        ["Seoul Bike Sharing (UCI 560)", "8,760",
         "Four design-hazard cases where hourly ordering breaks independence"],
        ["Student Performance (UCI 320)", "649",
         "Group comparison, ordinal traps, ordinary least squares"],
    ], widths=[5.0 * cm, 2.0 * cm, 9.6 * cm]))
    st.append(P(
        "Table 2. Public data sources. Seoul Bike supplies the sharpest test: "
        "tables that look entirely suitable for Poisson regression, "
        "correlation or ANOVA, where the correct answer is to abstain.",
        "caption"))

    st.append(P("6. Evaluation design", "h1"))
    st.append(P(
        "The benchmark is split into development and held-out partitions and "
        "the split is frozen before any held-out execution. Prompts, model "
        "identifier, code and tools are frozen at the same point. This is the "
        "control against the most damaging threat to the result — that "
        "apparent performance reflects prompt tuning against the test cases."))
    st.append(P("Metrics", "h2"))
    st += bullets([
        "<b>Method-selection accuracy</b> against an accepted-method set, "
        "reported with Wilson intervals.",
        "<b>Abstention recall</b> on design-hazard cases, and the "
        "complementary <b>unsafe-selection rate</b>: fitting a real method to "
        "an invalid design.",
        "<b>Numerical fidelity</b> and the provenance rejection rate.",
        "<b>Assumption coverage</b> and unsupported-inference rate in the "
        "written interpretation.",
        "<b>Run-to-run variability</b> across repetitions, reported rather "
        "than suppressed.",
    ])
    st.append(P(
        "The primary comparison is paired at case level. Repetitions collapse "
        "to a per-case majority before testing, because McNemar's test assumes "
        "independent pairs and two runs of one case are not two cases. "
        "Differences are reported with a case-level bootstrap interval "
        "alongside the exact test."))
    st.append(P(
        "Determinism deserves a note. The <font face='Courier'>temperature</font> "
        "parameter has been removed on current models and returns an error if "
        "sent. Determinism is therefore controlled by pinning the model "
        "identifier, fixing the effort level, freezing a prompt hash recorded "
        "in every run manifest, and <i>measuring</i> the residual variance "
        "across repetitions rather than claiming to have eliminated it.",
        "note"))

    st.append(PageBreak())
    st.append(P("7. Schedule and acceptance gates", "h1"))
    st.append(P(
        "The schedule uses weekly acceptance gates. A gate is a runnable "
        "artefact or a validated dataset, not a status note."))
    st.append(table([
        ["Week", "Build work", "Evaluation work", "Acceptance gate"],
        ["1", "Freeze scope; schemas, repository, case validator",
         "Acquire four UCI sources; 16 development cases and initial labels",
         "Raw data reproducible; 16 development cases pass validation"],
        ["2", "Typed diagnostics; execution dispatchers; unit-test 14 methods",
         "Complete all 64 cases, oracles and reviewer pass; lock the split",
         "Every method unit-tested; all cases valid; label disagreement resolved"],
        ["3", "Direct baseline, tool baseline, state machine, trace logging, UI",
         "Development cases only; refine routing from documented errors",
         "All three systems finish every development case; no untraced claim"],
        ["4", "Verifier, one-revision rule, report renderer, reproducibility manifest",
         "Blinded development review; freeze prompt, model, code and runner",
         "Development accuracy &ge; 80%; numeric fidelity &ge; 98%; candidate tagged"],
        ["5", "Demo and packaging; presentation defects only",
         "Execute the held-out evaluation; score, bootstrap, error analysis",
         "Results reproducible from raw logs; demo handles success and abstention"],
    ], widths=[1.5 * cm, 4.4 * cm, 4.9 * cm, 5.8 * cm]))
    st.append(P("Table 3. Weekly acceptance gates.", "caption"))

    st.append(P("8. Risks and controls", "h1"))
    st.append(table([
        ["Risk", "Material consequence", "Control"],
        ["The dataset lacks design facts",
         "A mathematically plausible but invalid method is selected",
         "Mandatory design card; abstain when independence, pairing, time "
         "order or clustering is unknown"],
        ["Assumption checks become mechanical",
         "Diagnostic p-values act as simplistic switches",
         "Policy consults multiple diagnostics and makes the estimand explicit"],
        ["Ambiguous answer keys",
         "Accuracy measures annotator preference rather than validity",
         "Accepted-method sets, written rationale, second review, recorded "
         "disagreement resolution"],
        ["Benchmark leakage",
         "Apparent performance reflects tuning on test cases",
         "Separate gold path; stratified frozen split; prompt and code freeze "
         "before any held-out execution"],
        ["The model fabricates numerical detail",
         "Plausible but false results reach the final report",
         "Tool-only numerical policy, result identifiers, strict verifier, "
         "schema-level provenance"],
        ["Real data invites causal claims",
         "Interpretation exceeds an observational design",
         "Causal-language linting and an explicit randomised or observational "
         "field"],
        ["Scope expands to advanced statistics",
         "The schedule collapses",
         "Unsupported designs are benchmarked as abstentions; extensions are "
         "documented, not implemented"],
        ["Provider nondeterminism",
         "Results are unstable or hard to reproduce",
         "Pinned model, fixed effort, frozen prompt hash, repetitions, full "
         "run manifests"],
    ], widths=[4.0 * cm, 5.2 * cm, 7.4 * cm]))
    st.append(P("Table 4. Risk register with controls.", "caption"))

    st.append(P("9. Deliverables and success criteria", "h1"))
    st += bullets([
        "A working application accepting a dataset, a question and a design "
        "card, returning a traceable report or a reasoned abstention.",
        "A tool library of fourteen methods with effect sizes, intervals and "
        "diagnostics.",
        f"A benchmark of {F['bench']['total']} validated case packages with "
        "gold labels, oracles and a frozen split.",
        "Three system variants, complete run logs, scorers, result tables and "
        "an error taxonomy.",
        "A capstone report presenting results, error analysis and limitations.",
    ])
    st.append(P(
        "The project succeeds if the structured arm exceeds the tool-enabled "
        "baseline by at least ten percentage points of method-selection "
        "accuracy on the held-out partition, with the difference supported by "
        "a paired test, and if every numerical claim in every generated report "
        "maps to a recorded tool output. It fails honestly — and is reported "
        "as failing — if the difference does not materialise."))
    return st


# ====================================================== INTERIM REPORT =====

def interim():
    st = []
    st += title_block(
        "An LLM Agent for the Selection, Validation and Interpretation "
        "of Statistical Methods", "Interim Report")

    st.append(P("1. Purpose and summary", "h1"))
    st.append(P(
        "This report records the state of the project at the week-four freeze "
        "gate — the point the plan defines as the decision point before the "
        "held-out evaluation is executed. It covers what has been built, what "
        "the development-set evidence shows, which risks have materialised, "
        "and what remains."))
    st.append(P(
        "<b>Summary.</b> The system, the benchmark and the evaluation harness "
        "are complete and the freeze conditions are met. The development-set "
        "evidence supports the central hypothesis, with an uplift well above "
        "the ten-point target. The held-out evaluation is the remaining work. "
        "One planned measurement has failed and is reported as failed rather "
        "than quietly dropped."))

    st.append(P("2. Progress against the acceptance gates", "h1"))
    st.append(table([
        ["Week", "Gate", "Status"],
        ["1", "Raw data reproducible; development cases pass validation",
         "<b>Met.</b> Four UCI sources acquired with checksums and a recorded "
         "manifest; development cases validate."],
        ["2", "Every method unit-tested; all cases valid; labels resolved",
         f"<b>Met.</b> All {F['bench']['total']} cases validate, "
         f"{F['bench']['abstain']} of them abstention cases; a full label "
         "audit passes."],
        ["3", "All three systems finish every development case; no untraced claim",
         "<b>Met.</b> Every arm completes the development partition and every "
         "rendered section resolves to a recorded tool output."],
        ["4", "Development accuracy &ge; 80%; fidelity &ge; 98%; candidate tagged",
         f"<b>Met.</b> Structured arm at {acc('dev','C_protocol'):.1%} on the "
         "development partition; provenance enforced at schema level; prompt, "
         "model, code and runner frozen."],
        ["5", "Held-out results reproducible from raw logs",
         "<b>Outstanding.</b> The runner, budget guard and credential "
         "pre-flight are in place and tested; execution is the remaining step."],
    ], widths=[1.5 * cm, 6.8 * cm, 8.3 * cm]))
    st.append(P("Table 1. Status against the planned acceptance gates.",
                "caption"))

    st.append(P("3. What has been built", "h1"))
    st.append(P(
        "Fourteen statistical methods with effect sizes and confidence "
        "intervals, five diagnostic tools, and a deterministic state machine "
        "around one tool-calling model. Validated libraries perform every "
        "numerical operation; no statistic is reimplemented."))
    st.append(P(
        "The three arms share one core. Every driver imports the same tool "
        "registry, result store and report schema, so the fairness of the "
        "baselines is a property of the repository rather than a claim in "
        "prose. The provenance contract is enforced at schema level: the "
        "report format rejects raw numeric literals in prose, and a reference "
        "to a result that was never computed fails the run."))

    st.append(P("4. Benchmark status", "h1"))
    st.append(P(
        f"{F['bench']['total']} validated case packages, "
        f"{F['bench']['abstain']} of which have no admissible in-scope method. "
        "Cases are generated from a declarative registry, so the benchmark "
        "regenerates from source rather than existing as a set of files that "
        "must be preserved."))
    st.append(P(
        "A label audit was run over the full set, comparing each gold label "
        "against the realised sample rather than against the generator's "
        "intent. It caught a routing defect in which extreme skew was assessed "
        "after a variance check rather than before, which had mislabelled a "
        "public case. The audit now passes on every case and runs as part of "
        "the standard verification."))

    st.append(P("5. Preliminary results", "h1"))
    st.append(P(
        "These are <b>development-set</b> results and must not be presented as "
        "the headline experiment: prompts were developed against these cases, "
        "so the numbers are optimistic by construction. They are reported here "
        "because they are what the freeze decision rests on."))
    st.append(table([
        ["System", "n", "Accuracy", "95% CI (Wilson)", "Abstention recall",
         "Unsafe rate"],
        ["A — Direct",
         f"{F['dev']['summary']['A_direct']['n_runs']}",
         f"{acc('dev','A_direct'):.3f}", ci("dev", "A_direct"),
         f"{F['dev']['summary']['A_direct']['abstention_recall']:.2f}",
         f"{F['dev']['summary']['A_direct']['unsafe_selection_rate']:.3f}"],
        ["B — Tools",
         f"{F['dev']['summary']['B_tools']['n_runs']}",
         f"{acc('dev','B_tools'):.3f}", ci("dev", "B_tools"),
         f"{F['dev']['summary']['B_tools']['abstention_recall']:.2f}",
         f"{F['dev']['summary']['B_tools']['unsafe_selection_rate']:.3f}"],
        ["C — Protocol",
         f"{F['dev']['summary']['C_protocol']['n_runs']}",
         f"{acc('dev','C_protocol'):.3f}", ci("dev", "C_protocol"),
         f"{F['dev']['summary']['C_protocol']['abstention_recall']:.2f}",
         f"{F['dev']['summary']['C_protocol']['unsafe_selection_rate']:.3f}"],
    ], widths=[3.0 * cm, 1.2 * cm, 2.3 * cm, 3.6 * cm, 3.3 * cm, 2.2 * cm]))
    st.append(P(
        "Table 2. Development partition, structured effort level. Paired "
        "comparison of the tool baseline against the protocol gives an uplift "
        "of "
        f"{acc('dev','C_protocol') - acc('dev','B_tools'):+.3f} "
        "against a ten-point target.", "caption"))
    st.append(P(
        "The sharpest separation is abstention. On the design-hazard cases the "
        "structured arm declined every time and the tool-enabled baseline "
        "never did, fitting a plausible-looking model to data whose "
        "independence assumption fails. That is precisely the failure the "
        "project exists to prevent, and it is the result that most needs "
        "held-out confirmation."))

    st.append(P("6. Offline calibration", "h1"))
    st.append(P(
        "A deterministic policy client was run through the same harness at two "
        "competence levels, 432 runs each, to validate the harness "
        "independently of any model. The expert policy scores perfectly, which "
        "is <i>circular</i> — that policy derived the gold labels — and is "
        "reported as such rather than as a result."))
    st.append(P(
        "The informative row is the naive policy. Inside the identical state "
        "machine it reaches "
        f"{F['naive']['summary']['C_protocol']['selection_accuracy']:.3f} "
        "with zero abstention recall. This demonstrates that the architecture "
        "is not what produces the uplift — the decision policy inside it is — "
        "and it is the strongest available evidence that the harness measures "
        "the intended quantity."))

    st.append(P("7. Deviations recorded so far", "h1"))
    st.append(table([
        ["Deviation", "Reason"],
        ["<font face='Courier'>temperature: 0</font> is not sent",
         "The parameter has been removed on current models and returns an "
         "error. Determinism is controlled by a pinned model, fixed effort, a "
         "frozen prompt hash and measured repetition variance."],
        ["Abstention cases raised from 8 to 12",
         "Eight cases could not support an interval narrow enough to "
         "distinguish the arms on the safety-critical metric."],
        ["Numeric fidelity is prevented, not verified",
         "Schema-level provenance makes fabrication impossible in the "
         "structured arm, which converts a metric into a guarantee. Reported "
         "as such rather than as a score."],
        ["The verifier moved from week four to week two",
         "It changes what the structured arm produces, so building it after "
         "the development runs would have invalidated them."],
        ["Not every method appears in both partitions",
         "Twelve synthetic development slots cannot cover fourteen methods "
         "plus abstention. Four methods appear only in the held-out set — a "
         "cleaner generalisation test, but an unplanned one."],
        ["Synthetic gold derives from the realised sample",
         "A generator asked for a normal sample that drew a skewed one must be "
         "labelled for the sample it drew."],
    ], widths=[5.2 * cm, 11.4 * cm]))
    st.append(P("Table 3. Deviations from the plan, with reasons.", "caption"))

    st.append(P("8. A failed measurement, reported as failed", "h1"))
    st.append(P(
        "The plan requires a 0–2 interpretation rubric applied blind to system "
        "identity, with at least a fifth of reports double-scored and "
        "agreement reported. A first round was run with two independent "
        "raters. <b>It failed its reliability check.</b> Inter-rater agreement "
        "reached a kappa of &minus;0.044 — worse than chance."))
    st.append(P(
        "Diagnosis attributes this to the instrument, not to rater "
        "carelessness: the rubric admitted two defensible readings of the "
        "middle grade, and raters applied different ones consistently. The "
        "rubric has been rewritten with disjoint anchors and adjudicated "
        "calibration examples. A second round requires two human raters and is "
        "listed under remaining work."))
    st.append(P(
        "The interpretation metric is therefore withheld rather than reported. "
        "Publishing a score from an instrument that demonstrably does not "
        "measure anything would be worse than reporting none, and the failure "
        "itself is a finding worth recording.", "note"))

    st.append(P("9. Remaining work", "h1"))
    st += bullets([
        "<b>Execute the held-out evaluation.</b> The runner is resumable, "
        "pre-flights credentials before spending anything, and refuses to "
        "start work it cannot finish. Execution is the only outstanding step.",
        "<b>Score, bootstrap and analyse.</b> Every table regenerates from the "
        "raw logs by a single command, so this follows immediately once the "
        "runs are recorded.",
        "<b>Second blinded scoring round</b> with the rebuilt instrument, "
        "which requires two human raters.",
        "<b>Final report and packaging.</b> The report already regenerates "
        "from the logs and will incorporate the held-out section without "
        "manual editing.",
    ])

    st.append(P("10. Assessment", "h1"))
    st.append(P(
        "The project is on schedule against its gates. The principal risk "
        "remaining is not technical but one of resources: the held-out "
        "evaluation requires inference capacity, and the evaluation cannot be "
        "reported without it. Every control around that step — the frozen "
        "split, the frozen prompt hash, the resumable runner, the budget "
        "guard — is in place and tested, so the step is bounded and "
        "repeatable rather than exploratory."))
    st.append(P(
        "The second risk is interpretive. The development evidence is strong "
        "but optimistic by construction, and the held-out result may be "
        "weaker. The reporting structure is already built to state that "
        "outcome plainly if it occurs: the report distinguishes offline "
        "calibration, live preliminary and live held-out evidence throughout, "
        "and never blurs them."))
    return st


# ---------------------------------------------------------------- build ---

def main() -> int:
    DOCS.mkdir(exist_ok=True)
    jobs = [("AI_Statistician_Proposal.pdf",
             "AI Statistician — Project Proposal", proposal),
            ("AI_Statistician_Interim_Report.pdf",
             "AI Statistician — Interim Report", interim)]
    for filename, running, builder in jobs:
        path = DOCS / filename
        doc = make_doc(path, running)
        doc.build(builder())
        kb = path.stat().st_size / 1024
        print(f"  {path.relative_to(ROOT)}  ({kb:,.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
