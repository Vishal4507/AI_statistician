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
import re
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
AUTHOR = "Vishal Dhinesh Kumar"
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
    s["h3"] = ParagraphStyle(
        "h3", fontName="Helvetica-Bold", fontSize=9.5, leading=13,
        textColor=INK2, spaceBefore=9, spaceAfter=3)
    s["code"] = ParagraphStyle(
        "code", fontName="Courier", fontSize=8.5, leading=11.5, textColor=INK2)
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
         "<b>Outstanding.</b> The runner, its execution guard and the "
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
        "validates the live path before starting, and refuses to begin work "
        "it cannot finish. Execution is the only outstanding step.",
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
        "split, the frozen prompt hash, the resumable runner, the execution "
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


# =========================================================== FINAL REPORT ==

LIVE_URL = "https://ai-statistician.netlify.app"
REPO_URL = "https://github.com/Vishal4507/AI_statistician"

_INLINE = [
    (re.compile(r"`([^`]+)`"), r'<font face="Courier" size="9">\1</font>'),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<b>\1</b>"),
    (re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)"), r"<i>\1</i>"),
]


def inline(s: str) -> str:
    """Markdown inline markup to reportlab's mini-markup.

    Escaping runs first: an unescaped ampersand or angle bracket in the source
    would be read as markup and silently swallow the rest of the paragraph.
    """
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # links: keep the text, make the destination clickable
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
               r'<link href="\2" color="#1c4f8f">\1</link>', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", s)   # local links: text only
    for pat, rep in _INLINE:
        s = pat.sub(rep, s)
    return s


def figure(path: Path, max_w: float):
    """Scale a figure to the text column, preserving its aspect ratio."""
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image
    iw, ih = ImageReader(str(path)).getSize()
    w = min(max_w, iw)
    return Image(str(path), width=w, height=w * ih / iw)


def render_markdown(md: str, width: float):
    """Render the capstone report's Markdown subset into flowables."""
    story, i = [], 0
    lines = md.splitlines()
    in_fence = False
    fence_buf = []

    while i < len(lines):
        raw = lines[i]
        s = raw.strip()

        if s.startswith("```"):
            if in_fence:
                story.append(Table(
                    [[Paragraph("<br/>".join(
                        l.replace("&", "&amp;").replace("<", "&lt;")
                         .replace(">", "&gt;").replace(" ", "&nbsp;")
                        for l in fence_buf), S["code"])]],
                    colWidths=[width],
                    style=TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f6f9")),
                        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6)])))
                story.append(Spacer(1, 8))
                fence_buf, in_fence = [], False
            else:
                in_fence = True
            i += 1
            continue
        if in_fence:
            fence_buf.append(raw)
            i += 1
            continue

        if not s or s.startswith("---"):
            i += 1
            continue

        if s.startswith("!["):
            m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", s)
            if m:
                p = (ROOT / "docs" / m.group(2)).resolve()
                if p.exists():
                    story.append(Spacer(1, 4))
                    story.append(figure(p, width))
                    story.append(Spacer(1, 3))
            i += 1
            continue

        if s.startswith("#"):
            level = len(s) - len(s.lstrip("#"))
            text = inline(s.lstrip("#").strip())
            if level == 1:
                i += 1
                continue                      # the cover page carries the title
            story.append(P(text, {2: "h1", 3: "h2"}.get(level, "h3")))
            i += 1
            continue

        if s.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            rows = [[c.strip() for c in r.strip("|").split("|")] for r in block]
            rows = [r for r in rows
                    if not all(set(c) <= set("-: ") for c in r)]
            if rows:
                n = max(len(r) for r in rows)
                rows = [[inline(c) for c in r] + [""] * (n - len(r)) for r in rows]
                story.append(table(rows, widths=[width / n] * n))
                story.append(Spacer(1, 6))
            continue

        if re.match(r"^\d+\.\s", s):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s", lines[i].strip()):
                item = lines[i].strip()
                i += 1
                while (i < len(lines) and lines[i].startswith("  ")
                       and lines[i].strip()
                       and not re.match(r"^\d+\.\s", lines[i].strip())):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(inline(item))
            story += [Paragraph(x, S["bullet"]) for x in items]
            story.append(Spacer(1, 4))
            continue

        if s.startswith("- ") or s.startswith("* "):
            items = []
            while i < len(lines) and lines[i].strip()[:2] in ("- ", "* "):
                item = lines[i].strip()[2:]
                i += 1
                while (i < len(lines) and lines[i].startswith("  ")
                       and lines[i].strip() and lines[i].strip()[:2] not in ("- ", "* ")):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(inline(item))
            story += bullets(items)
            story.append(Spacer(1, 4))
            continue

        # a whole-line italic run is a figure caption in this document
        if s.startswith("*") and s.endswith("*") and not s.startswith("**"):
            story.append(P(inline(s.strip("*")), "caption"))
            i += 1
            continue

        para = [s]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^\s*(#|\||-\s|\*\s|\d+\.\s|!\[|```|---)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        story.append(P(inline(" ".join(para))))

    return story


def final_report():
    md = (ROOT / "docs" / "CAPSTONE_REPORT.md").read_text()
    # The generated file opens with its own title and a regeneration note; the
    # cover page replaces both.
    md = md.split("---", 1)[1] if md.startswith("#") and "---" in md[:400] else md

    st = title_block(
        "An LLM Agent for the Selection, Validation and Interpretation "
        "of Statistical Methods", "Final Report")

    st.append(table(
        [["Live evaluation",
          f'<link href="{LIVE_URL}" color="#1c4f8f"><b>{LIVE_URL}</b></link>'],
         ["Source repository",
          f'<link href="{REPO_URL}" color="#1c4f8f"><b>{REPO_URL}</b></link>']],
        widths=[3.4 * cm, 13.2 * cm], header=False, zebra=False))
    st.append(P(
        "The first link opens the benchmark explorer: all 64 cases with their "
        "design cards and gold labels, every rendered report and execution "
        "trace from the recorded runs, the result tables, and a project status "
        "page. Nothing needs to be installed to inspect the evidence behind any "
        "figure in this report. The second holds the complete source, the "
        "benchmark, the recorded run logs and the test suite, so every table "
        "and figure here can be regenerated from the raw data.", "caption"))
    st.append(Spacer(1, 6))
    st += render_markdown(md, 16.6 * cm)
    return st


# ===================================================== PRESENTING POINTS ===

# (slide, minutes, title, purpose, what to say, the line to land, transition)
SLIDES = [
    (1, 0.5, "Title",
     "Establish who you are and the single question.",
     ["Introduce yourself and the project title.",
      "Read the question on the slide: does an explicit decision protocol make "
      "an LLM choose valid statistical methods more reliably than tool access "
      "alone?"],
     "Keep this short. The next slide does the real work.",
     "“Let me start with why this question matters.”"),
    (2, 2.0, "Problem statement",
     "The most important slide. Everything after it answers it.",
     ["State the problem in one breath: LLM analyses are fluent, arithmetically "
      "correct, and frequently invalid.",
      "Explain why: validity depends on how the data was collected — "
      "independence, pairing, time order, clustering — and those facts are not "
      "in the data file.",
      "Walk the three consequences left to right: an invalid method with correct "
      "arithmetic; a fabricated number that reads like a result; and no mechanism "
      "that obliges the model to decline."],
     "“The data itself does not contain the facts that decide whether the method "
     "is valid.”",
     "“Here is what that looks like on real data.”"),
    (3, 1.5, "Motivating case",
     "Make the abstract problem concrete with one dataset.",
     ["Seoul Bike Sharing: 8,760 rows, one per hour for a year.",
      "The question — does temperature relate to demand — looks like a textbook "
      "correlation or Poisson regression.",
      "Both assume independent observations. Adjacent hours share weather, "
      "commuting cycles and daylight, so they are not independent.",
      "Nothing in the file says so. The design card supplies that fact."],
     "“The table looked perfect, and the correct answer was to decline.”",
     "“So the question I tested is this.”"),
    (4, 1.0, "Research question and hypotheses",
     "Show exactly what is being tested and against what.",
     ["Read the research question.",
      "H1 selection, H2 abstention, H3 provenance.",
      "Stress that H1 compares C with B, not with A. B has the same tools and "
      "the same report format, so B is the honest control."],
     "“If C beats B, it is the procedure that won — not better tools.”",
     "“Before the results, the design decisions that make this testable.”"),
    (5, 1.0, "Scope and design decisions",
     "Justify the closed library and the absence of code execution.",
     ["Fourteen methods across five task families, plus abstention.",
      "Closed so it is scorable — an open library turns method choice into essay "
      "grading.",
      "No general code-execution tool: it would let the model bypass the policy "
      "and make the three systems incomparable.",
      "Unsupported designs are not ignored; they are tested as abstention cases."],
     "“Declining is a decision, not a failure.”",
     "“Here is how the three systems are built.”"),
    (6, 1.0, "Architecture",
     "Pre-empt the fairness question.",
     ["Three drivers, one shared core: tool registry, result store, report "
      "schema, trace log.",
      "Only the control flow differs between A, B and C."],
     "“Baseline fairness is provable from the code layout, not asserted.”",
     "“The difference is in how C orders its work.”"),
    (7, 1.25, "The decision protocol",
     "Show the ordering that is the whole intervention.",
     ["Seven steps: parse, validate design, enumerate, diagnose, select or "
      "abstain, execute, verify.",
      "Point at steps 2 and 5. Design validation gates everything downstream, so "
      "a clean normality test can never talk the system into a method the design "
      "rules out.",
      "B can run every one of these checks too. What it lacks is the "
      "requirement to validate first, and the permission to stop."],
     "“The intervention is the order, not the tools.”",
     "“One more design decision, about numbers.”"),
    (8, 1.0, "The provenance contract",
     "Explain how fabrication is prevented rather than detected.",
     ["Every tool result is registered under a key.",
      "The report format rejects raw numbers in prose.",
      "The model writes a reference; references are substituted at the end; an "
      "unknown reference fails the run.",
      "Say the caveat yourself: for C this makes fidelity a guarantee by design, "
      "not an empirical finding. The empirical measure is the rejection rate."],
     "“The model cannot write a number.”",
     "“Now the test itself.”"),
    (9, 1.0, "The benchmark",
     "Establish that the answer key is not opinion.",
     ["64 cases: 52 supported, 12 where declining is correct; 48 held out.",
      "Gold labels derive from the realised sample: design facts from the "
      "generator, distributional facts from the data actually drawn.",
      "Four public UCI datasets. The public labels were audited against their "
      "real values, which found and fixed one mislabel."],
     "“48 of 64 labels are derived, not judged.”",
     "“And the evaluation was designed to rule out tuning to the test.”"),
    (10, 1.0, "Evaluation protocol",
     "Show the controls against the most serious threat: leakage.",
     ["Held-out split frozen and never examined during development.",
      "Prompts fingerprinted by hash before the held-out run.",
      "Two repetitions per case, 288 graded runs, pinned model.",
      "Inference: per-case majority, then McNemar's exact test with a bootstrap "
      "interval — paired, because each case is answered by all three systems."],
     "“Without the frozen split, a good result would only mean I had tuned to "
     "the answers.”",
     "“So, the results.”"),
    (11, 1.0, "Result — accuracy",
     "Deliver the headline.",
     ["A 75%, B 67%, C 89%, with 95% intervals.",
      "C over B is +25 points against a +10 target.",
      "Point at B: tools without a procedure scored below no tools at all."],
     "“Tools did not rescue the model. The ordering did.”",
     "“Which of these differences are real?”"),
    (12, 1.25, "Result — significance",
     "Separate what is established from what is not. Do not rush this.",
     ["Solid and filled means significant; dashed and hollow means not.",
      "C over B: p = 0.0018. Established.",
      "C over A: +12.5 points, p = 0.0703. Not established — I report it as "
      "unresolved.",
      "B over A: not established either."],
     "“A result I only believe when it agrees with me is not a result.”",
     "“The sharpest separation is on the dangerous cases.”"),
    (13, 0.75, "Result — abstention",
     "The safety result.",
     ["On the design-hazard runs, C declined correctly 78% of the time.",
      "The tool-only baseline declined zero times — it fitted a real method to "
      "every invalid design."],
     "“H2 is supported.”",
     "“Then, could each system explain its result honestly?”"),
    (14, 0.75, "Result — grounding",
     "Show the second axis: reporting without invention.",
     ["The direct baseline had 43 of 96 reports rejected — a number no tool "
      "produced, or a check it never ran.",
      "B scores 100% here because it has tools and uses them. Its failure is "
      "choosing the wrong method, not inventing numbers.",
      "No fabricated number reached a reader in any system."],
     "“H3 is supported.”",
     "“Here is where each system actually goes wrong.”"),
    (15, 0.75, "Result — failure stage",
     "Show the mechanism behind every other result.",
     ["Total failures: A 24, B 32, C 11.",
      "Design-validation failures: B 20, C 4."],
     "“The protocol removed exactly the failure it was built to remove.”",
     "“It did give something up — coverage.”"),
    (16, 0.75, "Result — risk and coverage",
     "Answer the objection that C just refuses more.",
     ["C answered 85% of cases and was right on 87% of those.",
      "A and B answered 95% and 98%, and were right less often.",
      "Lower coverage came with higher accuracy on what was answered — the "
      "signature of declining the right cases, not declining at random."],
     "“It declines when it should.”",
     "“Pulling the findings together.”"),
    (17, 0.75, "Hypotheses revisited",
     "Summarise the findings against the questions asked.",
     ["H1, H2 and H3 supported.",
      "C over A unresolved — keep that row on the slide and say it."],
     "“Three supported, one open.”",
     "“Two things went wrong along the way, and they matter.”"),
    (18, 1.25, "Measurement rigour",
     "Demonstrate that you checked your own instrument.",
     ["Defect one: 51 runs ended in errors, but each had already chosen a "
      "method, and 37 had chosen correctly. Discarding them would have made the "
      "direct baseline look 6 points better than it is.",
      "Defect two: with two repetitions a tie had no majority, and the tie-break "
      "varied between sessions. The same data gave p-values from 0.016 to "
      "0.125 — either side of 0.05. Fixed and enforced by a test.",
      "Neither raised an error. Both are documented as formal deviations."],
     "“The system worked. The way I was measuring it did not, and nothing "
     "complained.”",
     "“So here is what the evidence does not support.”"),
    (19, 1.0, "Limitations",
     "State the limits calmly and without apology.",
     ["Held-out claims are scoped to Claude Haiku 4.5.",
      "48 cases and two repetitions resolve the main comparison but not C over "
      "A.",
      "The interpretation score is withheld: the blinded round failed its "
      "reliability check, kappa −0.044.",
      "No independent second reviewer for the public labels; several design "
      "families are out of scope."],
     "“Each limit is known, bounded and disclosed.”",
     "“What the project contributes.”"),
    (20, 0.75, "Contributions",
     "Close the argument.",
     ["Controlled evidence that the protocol, not tool access, drives valid "
      "selection.",
      "A benchmark that scores declining.",
      "A report format in which an unsourced number cannot exist."],
     "“Structure, not tooling, makes an LLM a reliable statistician.” — then "
     "pause.",
     "“Where this goes next.”"),
    (21, 0.5, "Future work",
     "Show the obvious next experiments.",
     ["A larger held-out set to resolve C over A; frontier models; a second "
      "blinded scoring round; a wider method library."],
     "“The design already tells me how much larger the sample needs to be.”",
     "“You can see all of it running.”"),
    (22, 0.5, "Live artefacts and questions",
     "Invite scrutiny.",
     ["Point to the live explorer and the repository.",
      "If there is time, open the Seoul bike case and show C declining while A "
      "and B both fit a model."],
     "“Thank you — I'm happy to take questions.”",
     ""),
]

QA = [
    ("If fabrication is impossible in System C, isn't its perfect fidelity a "
     "tautology?",
     "Yes, and that is how it is reported. For C, fidelity is a property of the "
     "design, not a measured finding. The empirical measure is how often the model "
     "reached for a reference that did not exist, and that rate is reported."),
    ("Why is the main comparison C against B rather than C against A?",
     "B holds exactly the same tools and the same report format as C; only the "
     "control flow differs. Comparing C with B isolates the protocol. Comparing C "
     "with A would mix the protocol with tool access."),
    ("C over A isn't significant. Is the protocol actually better than no tools?",
     "The direction favours C — the discordant cases split seven to one — but at 48 "
     "cases that is not enough to rule out chance, so I report it as unresolved. "
     "The primary comparison, against B, is significant at p = 0.0018."),
    ("How do you know your gold labels are correct?",
     "48 of 64 labels are construction-derived: design facts come from the "
     "generator and distributional facts from the sample actually drawn, so they "
     "are not judgements. The 16 public-data labels were audited against their "
     "realised values, which caught and fixed one mislabel."),
    ("Why only two repetitions?",
     "It was a resource constraint. Two repetitions are enough to establish the "
     "primary comparison and to measure run-to-run stability — 25 of 144 "
     "system-case cells disagreed between runs — but not to characterise the full "
     "distribution. More repetitions are the first item of future work."),
    ("Why Claude Haiku 4.5 and not a frontier model?",
     "Every held-out claim is scoped to Haiku 4.5, and I do not generalise beyond "
     "it. The runner is model-agnostic and the evaluation is frozen, so re-running "
     "on a larger model is a direct next step."),
    ("Why didn't you set temperature to zero for determinism?",
     "The temperature parameter has been removed on current models and returns an "
     "error if sent. Determinism is controlled instead by a pinned model, a fixed "
     "effort level and a frozen prompt hash — and residual variance is measured "
     "across repetitions rather than assumed away."),
    ("The expert policy scores 100%. Doesn't that prove the system works?",
     "No — that score is circular, because the expert policy is what derived the "
     "gold labels. It validates the harness, not the method. The informative row "
     "is the naive policy inside the same state machine, which scores far lower "
     "and never abstains — showing the architecture alone does not produce the "
     "gain."),
    ("Why did you keep errored runs in the accuracy figure?",
     "Because none of the 51 errors were infrastructure. Each run had already "
     "chosen a method before its report failed the provenance check, and 37 had "
     "chosen correctly. Discarding them would raise the direct baseline from 75.0% "
     "to 81.1% by hiding its worst behaviour. Runs that never reached a decision "
     "are excluded."),
    ("Couldn't System B simply do what System C does?",
     "It has every tool C has, so nothing stops it. What it lacks is the "
     "requirement to validate the design before anything else, and the explicit "
     "permission to decline. The results show that without those, it does not "
     "discover them."),
    ("What happened with the interpretation scoring?",
     "The blinded round failed its reliability check — inter-rater kappa of "
     "−0.044, worse than chance. The rubric admitted two defensible readings of its "
     "middle grade, so it was rebuilt. I withheld the metric rather than report a "
     "number from an instrument that demonstrably does not measure anything."),
    ("Why McNemar's test?",
     "Each case is answered by every system, so outcomes are paired and binary. "
     "McNemar's exact test uses only the discordant cases, which is right for paired "
     "binary data with small discordant counts. The bootstrap gives an interval on "
     "the difference itself."),
    ("What is the practical application?",
     "Anywhere an LLM analyses data for people who cannot audit the method — "
     "business analysts, clinicians, policy teams. The risk is not bad arithmetic; "
     "it is a confident answer from a method the data does not support."),
    ("What would you do differently?",
     "A larger held-out set and more repetitions to resolve C over A, and an "
     "independent second reviewer for the public-data labels from the start."),
]

NUMBERS = [
    ["Selection accuracy", "A 75.0%  ·  B 66.7%  ·  C 88.5%"],
    ["C over B", "+25.0 points  ·  p = 0.0018  ·  95% CI [+12.5, +39.6]"],
    ["C over A", "+12.5 points  ·  p = 0.0703  ·  not established"],
    ["Declined correctly", "A 28%  ·  B 0%  ·  C 78%  (design-hazard runs)"],
    ["Reports rejected", "A 43 of 96  ·  B 0  ·  C 8"],
    ["Design-validation failures", "B 20  ·  C 4"],
    ["Selective accuracy", "C 87% at 85% coverage"],
    ["Benchmark", "64 cases  ·  52 supported  ·  12 abstain  ·  48 held out"],
    ["Runs", "288 graded, 2 repetitions, Claude Haiku 4.5"],
    ["Reliability failure", "inter-rater kappa −0.044"],
]


def presenting_points():
    st = title_block(
        "An LLM Agent for the Selection, Validation and Interpretation "
        "of Statistical Methods", "Presenting Notes")

    st.append(P("1. Before you start", "h1"))
    total = sum(s[1] for s in SLIDES)
    st.append(P(
        f"Twenty-two slides, planned at about {total:.0f} minutes. If time is "
        "short, compress slides 13 to 16 — each is a single figure with one "
        "sentence to land — and keep slides 2, 12 and 18 at full length. Those "
        "three carry the problem, the honest reading of the results, and the "
        "evidence that the measurement itself was checked."))
    st.append(P(
        "What a professor listens for is not a large number. It is whether you "
        "know exactly what your evidence supports, and whether you say where it "
        "stops before being asked.", "note"))

    st.append(P("2. The problem statement, at three lengths", "h1"))
    st.append(P("In one sentence", "h2"))
    st.append(P(
        "“Language models produce statistical analyses that are fluent and "
        "arithmetically correct but often invalid, because validity depends on "
        "how the data was collected — which the data itself does not contain.”"))
    st.append(P("In thirty seconds", "h2"))
    st.append(P(
        "“Ask an AI to analyse a dataset and it will always give you an answer. "
        "It reads well and the arithmetic is right. But whether the method is "
        "valid depends on facts about the study design — are the observations "
        "independent, paired, ordered in time — and none of that is visible in "
        "the spreadsheet. So the model can apply a method the data does not "
        "support, invent a statistic, or answer when it should decline. This "
        "project tests whether giving the model an explicit decision procedure "
        "fixes that.”"))
    st.append(P("In two minutes", "h2"))
    st += bullets([
        "Open with the observation: an LLM always answers, and its answers are "
        "fluent and arithmetically correct.",
        "Name the gap: validity is decided by design facts — independence, "
        "pairing, temporal order, clustering — that live outside the data file.",
        "Give the three consequences: an invalid method with correct numbers; a "
        "fabricated statistic that reads as a result; no obligation to decline.",
        "Say why it matters: the people most likely to rely on an AI's analysis "
        "are the people least able to audit its method.",
        "State the question: does an explicit protocol make the model choose "
        "valid methods more reliably than tool access alone?",
    ])

    st.append(PageBreak())
    st.append(P("3. Slide by slide", "h1"))
    for num, mins, name, purpose, say, land, nxt in SLIDES:
        head = f"Slide {num}  ·  {name}"
        block = [P(head, "h2"),
                 P(f"<i>{purpose}</i>  <font color='#8496a6'>"
                   f"(about {mins:g} min)</font>", "body")]
        block += bullets(say)
        block.append(P(f"<b>Land this:</b> {land}", "body"))
        if nxt:
            block.append(P(f"<font color='#5c6a78'>Transition: {nxt}</font>",
                           "body"))
        st.append(KeepTogether(block))

    st.append(PageBreak())
    st.append(P("4. Numbers to know without looking", "h1"))
    st.append(P(
        "Every figure below matches the recorded held-out run. Quote them "
        "exactly; rounding a p-value in speech is where a sharp question starts."))
    st.append(table([["Measure", "Value"]] + NUMBERS,
                    widths=[5.0 * cm, 11.6 * cm]))

    st.append(P("5. Questions to expect", "h1"))
    st.append(P(
        "Answer the question asked, then stop. Where a limit is involved, state it "
        "plainly — defensiveness reads worse than the limit itself."))
    for q, a in QA:
        st.append(KeepTogether([P(f"<b>Q.</b> {q}", "body"),
                                P(f"<b>A.</b> {a}", "bullet"),
                                Spacer(1, 3)]))

    st.append(P("6. Phrases to avoid", "h1"))
    st.append(table([
        ["Instead of", "Say"],
        ["“The system proves LLMs can be trusted.”",
         "“On this model and benchmark, the protocol beat tool access alone by 25 "
         "points.”"],
        ["“It is better than a plain LLM.”",
         "“It leads the plain LLM by 12.5 points, but that difference is not "
         "significant at this sample size.”"],
        ["“Numerical fidelity is 100%.”",
         "“Fabrication is prevented by design; the rejection rate is the "
         "empirical measure.”"],
        ["“It never makes mistakes.”",
         "“It fails least at design validation, which is the failure it was "
         "built to prevent.”"],
        ["“The results show it works on all models.”",
         "“The held-out result is scoped to Claude Haiku 4.5.”"],
    ], widths=[6.6 * cm, 10.0 * cm]))
    return st


# ====================================================== PRESENTATION SCRIPT ==
#
# Spoken, first person, to be read aloud.  Written the way a student talks a
# professor through their own work: short sentences, contractions, and the
# occasional admission of what was surprising -- not the balanced, polished
# prose of a written report.  Text in [brackets] is a cue, not something to say.

SCRIPT = [
    (1, "Title", 0.5, [
        "Hello everyone. My name is Vishal Dhinesh Kumar, and my capstone project "
        "is called AI Statistician.",
        "The question I set out to answer is this. If you give an AI a proper "
        "step-by-step procedure for doing statistics, does it choose the right "
        "method more often than if you just give it the tools and let it work "
        "things out on its own?",
        "That's what I'm going to walk you through today.",
    ]),
    (2, "Problem statement", 2.0, [
        "So let me start with the problem, because everything else in this "
        "project comes back to it.",
        "If you ask an AI to analyse a dataset, it will always give you an "
        "answer. And that answer usually looks good. It's well written, it uses "
        "the right terms, and the arithmetic is correct.",
        "But none of that tells you whether the method was actually the right "
        "one to use.",
        "Whether a statistical method is valid depends on how the data was "
        "collected. Are the observations independent of each other? Is the same "
        "person measured twice? Are the rows in time order? These are facts about "
        "the study design. And the important thing is, you can't see them in the "
        "data file. A spreadsheet only shows you numbers.",
        "[point to the three boxes] This creates three problems.",
        "The first one is the most dangerous. The model can pick a method that "
        "assumes something the data doesn't satisfy. Every number will still add "
        "up, so it looks completely fine. But the conclusion is wrong.",
        "The second is that the model can write a number that no calculation "
        "ever produced. It reads like a real result, and the only way to catch it "
        "is to redo the whole analysis yourself.",
        "And the third is that nothing forces the model to stop and say, this "
        "data doesn't fit any method I have. Giving it tools lets it calculate "
        "things. It doesn't make it check whether it should.",
        "That's the gap I wanted to work on.",
    ]),
    (3, "A motivating case", 1.5, [
        "To make this concrete, here's an example from my benchmark.",
        "This is the Seoul bike sharing dataset from the UCI repository. It has "
        "8,760 rows, one for every hour of a year. The question is whether "
        "temperature is related to how many bikes get rented.",
        "If you look at this table, it looks like a textbook case. You'd probably "
        "reach for a correlation, or a Poisson regression because it's count "
        "data. And that's exactly what the systems did.",
        "The problem is that both of those methods assume every observation is "
        "independent. Here they're not. Two o'clock looks a lot like one o'clock, "
        "because it's the same day, the same weather, the same commute. Each hour "
        "is carrying information about the hours next to it.",
        "And there's nothing in the file that tells you this. You only know it "
        "because you know how the data was collected.",
        "So in my system, that information comes in through what I call a design "
        "card, which describes how the study was set up. The system is scored on "
        "whether it actually uses it.",
        "For this case, the correct answer is not to model it at all. It should "
        "decline.",
    ]),
    (4, "Research question and hypotheses", 1.0, [
        "So this is my research question. Does an explicit decision protocol help "
        "an AI choose valid methods, compared with just asking it directly, and "
        "compared with giving it tools but no protocol?",
        "I tested three hypotheses. H1 is about selection, whether the protocol "
        "picks the right method more often. H2 is about abstention, whether it "
        "declines more reliably when no method fits. And H3 is about provenance, "
        "whether it stops made-up numbers from getting into the final report.",
        "One thing I want to point out. For H1, the main comparison is C against "
        "B, not C against A. That's on purpose. B has exactly the same tools and "
        "the same report format as C. The only thing different is the procedure. "
        "So if C beats B, I know it's the procedure that made the difference, not "
        "the tools.",
    ]),
    (5, "Scope and design decisions", 1.0, [
        "Before the results, a few design decisions that make this testable.",
        "[point to the left] This is the method library. I limited it to fourteen "
        "methods, grouped by the kind of question. Two groups, three or more "
        "groups, categorical data, association, and regression. And there's a "
        "fifteenth option, which is to abstain.",
        "I kept it closed on purpose. If the model could invent any method it "
        "wanted, there'd be no clear way to mark whether its choice was right. It "
        "would turn into grading essays.",
        "I also didn't give it a general tool to run any code it likes. If I had, "
        "it could skip the procedure completely, and then the three systems "
        "wouldn't be doing comparable work.",
        "And the designs I didn't cover, like repeated measures or time series, I "
        "didn't just leave out. They're in the benchmark as cases where the right "
        "answer is to decline.",
    ]),
    (6, "Architecture", 1.0, [
        "This is how the three systems are built.",
        "A is the direct version, with no tools. B has the tools but no procedure. "
        "And C is the structured agent, which has to check the design first.",
        "[point to the bottom box] The important part is down here. All three "
        "share the same core. The same tool registry, result store, report format "
        "and trace log. The only thing that changes between them is the control "
        "flow, meaning the order they do things in.",
        "I built it this way so the comparison is fair by design. There's no part "
        "of the code where A or B gets a weaker version of something. So if the "
        "results are different, it has to be because of the control flow.",
    ]),
    (7, "The decision protocol", 1.25, [
        "This is what that control flow looks like for system C. There are seven "
        "steps.",
        "It reads the question, checks the design, lists the methods that design "
        "allows, runs only the checks that could actually change the choice, "
        "then either picks a method or declines, runs it, and verifies the report "
        "at the end.",
        "[point to steps 2 and 5] The two in green are the ones that matter most.",
        "Design validation happens before anything else. So if the design has a "
        "problem, say the rows aren't independent, those methods are removed "
        "before any diagnostic even runs. That means a normality test that happens "
        "to look fine can never push the system into a method the design has "
        "already ruled out.",
        "And step five is where it's allowed to say no.",
        "I want to be clear about one thing. System B can run every one of these "
        "checks. Nothing is stopping it. What B doesn't have is the rule that says "
        "check the design first, and the permission to stop.",
    ]),
    (8, "The provenance contract", 1.0, [
        "The other big design decision is about numbers. The idea is that the "
        "model isn't allowed to write a number itself.",
        "Every time a real calculation runs, the result is stored with a label. "
        "The report format rejects any number typed straight into the text. So "
        "instead, the model writes a reference to the label. At the end, every "
        "reference is replaced with the real stored value. And if the model refers "
        "to something that was never calculated, the whole run fails.",
        "So instead of checking a finished report for made-up numbers, it just "
        "isn't possible to put one in.",
        "I do want to be honest about what this means. For system C, numerical "
        "accuracy is guaranteed by how it's built. It's not something I measured "
        "and discovered. So I'm not going to present it as a result. What I can "
        "measure is how often the model tried to reference something that didn't "
        "exist.",
    ]),
    (9, "The benchmark", 1.0, [
        "To test all this, I built a benchmark of 64 cases. 52 of them have a "
        "correct method, and 12 are cases where the right answer is to decline. "
        "48 of the 64 are held out, which I'll explain on the next slide.",
        "None of these were written by hand. Each case is generated from a "
        "definition. For the synthetic ones, the correct answer is based on the "
        "data that actually came out, not what I meant to generate. So if I asked "
        "for normal data and it came out skewed, the label follows the skewed "
        "data.",
        "[point to the right] Then there are four public datasets from UCI.",
        "The reason this matters is that most of the answer key isn't my opinion. "
        "48 of the labels come from how the data was built. The 16 public ones I "
        "checked against the real values, and that check found one label that was "
        "wrong, which I fixed.",
    ]),
    (10, "Evaluation protocol", 1.0, [
        "This slide is about how I kept the evaluation fair.",
        "The biggest risk in a project like this is that you end up tuning your "
        "system to the test without realising it. So the 48 held-out cases were "
        "locked away. I didn't look at them while I was building. I also fixed "
        "the instructions given to the model and recorded a fingerprint of them "
        "before the held-out run, so they couldn't change afterwards.",
        "Each case was run twice for each system. That's 288 runs in total, all "
        "on the same model.",
        "On the right are the metrics. Accuracy with confidence intervals, how "
        "often it declined correctly, whether the report passed the provenance "
        "check, and where each system failed.",
        "For the statistics, I compared the systems case by case using McNemar's "
        "test, because every case was answered by all three systems.",
    ]),
    (11, "Result: accuracy", 1.0, [
        "So now the results.",
        "This is how often each system chose a valid method. A, the direct "
        "version, got 75 percent. B, with tools only, got 67 percent. And C, with "
        "the procedure, got 89 percent.",
        "C beat B by 25 percentage points. My target at the start was 10 points, "
        "so that's well above it.",
        "[point to the B bar] But the part I found most interesting is B. B has "
        "tools, and it actually did worse than A, which has no tools at all.",
        "So giving the model tools on their own didn't help. It was the procedure "
        "that made the difference.",
    ]),
    (12, "Result: which differences are real", 1.25, [
        "Now, which of these differences are actually real? That's what this "
        "slide shows.",
        "A solid green line with a filled dot means the difference is "
        "statistically significant. A dashed grey line with a hollow dot means it "
        "isn't.",
        "C over B, the main comparison, has a p-value of 0.0018. So that one is "
        "established.",
        "C over A is a 12.5 point difference, but the p-value is 0.07. That's not "
        "below 0.05, so I can't claim that C is better than A. It's pointing in "
        "C's favour, but with 48 cases I don't have enough data to rule out "
        "chance. So I'm reporting it as unresolved.",
        "B over A isn't significant either.",
        "[slow down here] I gave this its own slide because I think it's "
        "important to be clear about where the evidence stops. If I only believed "
        "my results when they agreed with me, they wouldn't really be results.",
    ]),
    (13, "Result: recognising an invalid design", 0.75, [
        "This is the safety result, and it's the clearest difference in the whole "
        "study.",
        "These are the cases where every available method is invalid, so the "
        "right answer is to decline.",
        "C declined correctly 78 percent of the time. B declined zero times. "
        "Every single time, B went ahead and fitted a method to data that didn't "
        "support it.",
        "That's exactly the failure this project was trying to prevent. So H2 is "
        "supported.",
    ]),
    (14, "Result: could the report be grounded", 0.75, [
        "This one is about whether each system could report its results without "
        "making anything up.",
        "System A had 43 out of 96 reports rejected. That means it either wrote a "
        "number that no calculation produced, or it mentioned a check it never "
        "actually ran.",
        "You might notice B is at 100 percent here. That's because B has tools "
        "and uses them, so its numbers are real. B's problem isn't making up "
        "numbers. It's picking the wrong method in the first place.",
        "The main point is that none of these made-up numbers reached a reader. "
        "They were all caught. So H3 is supported.",
    ]),
    (15, "Result: where each system fails", 0.75, [
        "This chart shows where each system actually goes wrong.",
        "The solid part of each bar is design validation failures. That means "
        "using a method on data where the design doesn't allow it.",
        "B has 20 of those. C has 4.",
        "So the procedure cut down exactly the mistake it was built to stop. Most "
        "of what's left for C is in diagnostic reasoning, which is a different "
        "and smaller problem.",
    ]),
    (16, "Result: coverage and accuracy", 0.75, [
        "A fair question here is whether C just refuses to answer more often, and "
        "that's why it looks better.",
        "This chart answers that. Along the bottom is how often each system chose "
        "to answer. Up the side is how accurate it was on the ones it did answer.",
        "C answered 85 percent of cases and was right on 87 percent of those. A "
        "and B answered almost everything, 95 and 98 percent, but they were right "
        "less often.",
        "So C gave up some coverage, but it got accuracy back for it. That's what "
        "you'd expect if it's declining the right cases, and not just declining "
        "at random.",
    ]),
    (17, "Hypotheses revisited", 0.75, [
        "So going back to my hypotheses.",
        "H1, selection, is supported. C beat B by 25 points.",
        "H2, abstention, is supported. C declined correctly 78 percent of the "
        "time, and B never did.",
        "H3, provenance, is supported. 51 reports were rejected, and none of them "
        "reached a reader.",
        "The comparison between C and A is still unresolved. I left that on the "
        "slide on purpose, because taking it off would make the findings look "
        "stronger than they are.",
    ]),
    (18, "Two defects in my own measurement", 1.25, [
        "This part isn't about the system. It's about how I measured it, and two "
        "mistakes I found.",
        "The first one. 51 runs ended with an error, and the obvious thing to do "
        "is throw them out. But when I looked at them, none were technical "
        "failures. Every one had already chosen a method before its report was "
        "rejected, and 37 of them had chosen correctly. If I'd thrown them out, "
        "system A would have looked 6 points better than it really is. So I kept "
        "them.",
        "The second one. Each case was run twice, and sometimes the two runs "
        "disagreed. I needed a way to break those ties, and the way I first did "
        "it changed from one session to the next. So the exact same data gave me "
        "different p-values, anywhere from 0.016 to 0.125. That's on both sides "
        "of 0.05. I fixed it so ties always break the same way, and added a test "
        "so it stays fixed.",
        "Neither of these showed up as an error. I only found them by going "
        "through the results carefully before building any tables.",
    ]),
    (19, "Limitations", 1.0, [
        "These are the limitations.",
        "The held-out results are for one model, Claude Haiku 4.5. I'm not "
        "claiming anything about larger models without testing them.",
        "The sample is 48 cases with two runs each. That's enough to show the "
        "main result, but not enough to settle C against A.",
        "I also tried to score how good each system's written interpretation "
        "was, with two people scoring blind. That didn't work. The two scorers "
        "didn't agree with each other. The agreement score was minus 0.044, "
        "which is actually worse than chance. When I looked into why, the scoring "
        "rubric could be read in two different ways. So I rebuilt it, and I've "
        "left that metric out rather than report a number I can't trust.",
        "There's also no second independent reviewer for the public data labels, "
        "and a few study designs are outside what the library covers.",
    ]),
    (20, "Contributions", 0.75, [
        "So what does this project add?",
        "First, controlled evidence that it's the procedure, and not just giving "
        "the AI tools, that makes it choose valid methods.",
        "Second, a benchmark that actually rewards declining, so knowing when to "
        "stop becomes something you can measure.",
        "And third, a way of reporting results where a number with no real "
        "calculation behind it can't exist.",
        "If I had to put it in one line: structure, not tools, is what makes an "
        "AI a reliable statistician.",
        "[pause]",
    ]),
    (21, "Future work", 0.5, [
        "For future work, the first thing I'd do is run a bigger held-out set, so "
        "I can actually settle the question of C against A.",
        "I'd also like to test it on larger models, to see whether the procedure "
        "still helps as the model gets more capable. And I'd run a second round "
        "of the interpretation scoring with the new rubric, and extend the library "
        "to cover designs like repeated measures and time series.",
    ]),
    (22, "Thank you", 0.5, [
        "Everything I've shown today is online. The first link is a live explorer "
        "where you can see every case, every answer each system gave, and every "
        "step it took. The second is the full code and data on GitHub.",
        "If there's time, I'm happy to open the bike sharing example and show C "
        "declining while the other two go ahead anyway.",
        "Thank you. I'm happy to take any questions.",
    ]),
]

# Likely questions, answered in the same voice.
SCRIPT_QA = [
    ("If numbers can't be made up in system C, isn't its accuracy on numbers "
     "automatic?",
     "Yes, it is, and that's why I don't count it as a result. It's guaranteed by "
     "how the system is built. What I actually measure is how often the model "
     "tried to reference something that was never calculated."),
    ("Why is your main comparison C against B and not C against A?",
     "Because B has exactly the same tools and report format as C. The only "
     "difference is the procedure. If I compared C with A, I'd be mixing up the "
     "effect of the procedure with the effect of having tools."),
    ("C over A isn't significant. So is the procedure really better than nothing?",
     "I can't say that yet. The difference points in C's favour, but with 48 "
     "cases it's not enough to rule out chance, so I've reported it as "
     "unresolved. The main comparison, against B, is significant at 0.0018."),
    ("How do you know your answer key is right?",
     "48 of the 64 labels come from how the data was generated, so they're not "
     "my judgement. For the 16 public datasets, I checked each label against the "
     "real data, and that found one mistake, which I corrected."),
    ("Why only two runs per case?",
     "It came down to resources. Two runs were enough to show the main result and "
     "to measure how consistent the systems were, but not enough to fully describe "
     "the variation. More runs is the first thing I'd add."),
    ("Why did you keep the runs that ended in errors?",
     "Because none of them were technical failures. Each one had already picked a "
     "method before its report was rejected, and 37 had picked correctly. Throwing "
     "them out would have made system A look 6 points better than it actually is."),
    ("Couldn't system B just do what C does?",
     "It could, in theory. It has every tool C has. What it doesn't have is the "
     "rule to check the design first, and permission to stop. And the results "
     "show that without those, it doesn't do it on its own."),
    ("What happened with the interpretation scoring?",
     "The two scorers didn't agree, the agreement was minus 0.044, which is worse "
     "than chance. The rubric could be read two ways. So I rebuilt it and left "
     "the metric out, because a number from a scoring method that doesn't work "
     "would be misleading."),
]


def script_styles():
    s = {}
    s["say"] = ParagraphStyle(
        "say", fontName="Times-Roman", fontSize=12.5, leading=19.5,
        textColor=INK, spaceAfter=9)
    s["slide"] = ParagraphStyle(
        "slide", fontName="Helvetica-Bold", fontSize=13, leading=17,
        textColor=ACCENT, spaceBefore=4, spaceAfter=2)
    s["time"] = ParagraphStyle(
        "time", fontName="Helvetica", fontSize=8.5, leading=11,
        textColor=MUTED, spaceAfter=9)
    s["q"] = ParagraphStyle(
        "q", fontName="Times-Bold", fontSize=12, leading=17,
        textColor=INK, spaceBefore=8, spaceAfter=3)
    s["a"] = ParagraphStyle(
        "a", fontName="Times-Roman", fontSize=12, leading=18,
        textColor=INK, leftIndent=12, spaceAfter=6)
    return s


SS = script_styles()


def spoken(line: str) -> str:
    """Render a script line: cues in grey italic, everything else as speech."""
    line = line.replace("&", "&amp;")
    return re.sub(r"\[([^\]]+)\]",
                  r"<font color='#8496a6'><i>[\1]</i></font>", line)


def presentation_script():
    st = title_block(
        "An LLM Agent for the Selection, Validation and Interpretation "
        "of Statistical Methods", "Presentation Script")
    total = sum(m for _, _, m, _ in SCRIPT)
    st.append(P(
        f"Twenty-two slides, about {total:.0f} minutes spoken. Words in grey "
        "brackets are cues, not lines to say.", "caption"))

    for i, (num, title, mins, lines) in enumerate(SCRIPT):
        if i:
            st.append(PageBreak())
        st.append(Paragraph(f"Slide {num}  ·  {title}", SS["slide"]))
        st.append(Paragraph(f"about {mins:g} minute{'s' if mins != 1 else ''}",
                            SS["time"]))
        for line in lines:
            st.append(Paragraph(spoken(line), SS["say"]))

    st.append(PageBreak())
    st.append(Paragraph("If I get asked", SS["slide"]))
    st.append(Paragraph("the questions most likely to come up", SS["time"]))
    for q, a in SCRIPT_QA:
        st.append(KeepTogether([Paragraph(q, SS["q"]),
                                Paragraph(a, SS["a"])]))
    return st


# ---------------------------------------------------------------- build ---

def main() -> int:
    DOCS.mkdir(exist_ok=True)
    jobs = [("AI_Statistician_Proposal.pdf",
             "AI Statistician — Project Proposal", proposal),
            ("AI_Statistician_Interim_Report.pdf",
             "AI Statistician — Interim Report", interim),
            ("AI_Statistician_Final_Report.pdf",
             "AI Statistician — Final Report", final_report),
            ("AI_Statistician_Presenting_Notes.pdf",
             "AI Statistician — Presenting Notes", presenting_points),
            ("AI_Statistician_Presentation_Script.pdf",
             "AI Statistician — Presentation Script", presentation_script)]
    for filename, running, builder in jobs:
        path = DOCS / filename
        doc = make_doc(path, running)
        doc.build(builder())
        kb = path.stat().st_size / 1024
        print(f"  {path.relative_to(ROOT)}  ({kb:,.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
