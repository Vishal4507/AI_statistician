"""AI Statistician demo (blueprint section 6 step 14, section 12).

    streamlit run app/streamlit_app.py

Accepts a CSV, a question, an analysis objective and a design card; shows the
selected method or abstention, the decisive evidence, rejected alternatives,
diagnostics, the full trace, and a downloadable report.

Handles malformed input and unsupported designs without silently selecting a
method -- part of the definition of done.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import streamlit as st

from aistat.agents.base import BENCH, Case
from aistat.agents.llm import api_key_available
from aistat.agents.policy import infer_task
from aistat.agents.rulebased import RuleBasedClient
from aistat.agents.systems import SYSTEMS

st.set_page_config(page_title="AI Statistician", layout="wide")

DEMO_CASES = {
    "Welch ANOVA -- unequal variances, unbalanced groups": "syn_welch_anova_1",
    "Poisson to negative binomial -- one permitted revision": "syn_negbin_1",
    "Abstain -- hourly bike demand, serial dependence": "pub_bike_1",
    "Abstain -- repeated measures per subject": "syn_abstain_repeated_measures_1",
    "Sparse 2x2 -- Fisher exact": "syn_fisher_1",
    "Ordinal predictor -- Spearman": "syn_spearman_1",
}


def _empty_card() -> dict:
    return {"observational_unit": "", "sampling_unit": "",
            "repeated_id_column": None, "time_column": None, "pairing": False,
            "clustering_column": None, "randomized": False,
            "intended_population": "", "known_missingness": None}


# --------------------------------------------------------------------------

st.title("AI Statistician")
st.caption("LLM-guided selection, validation, execution and interpretation of "
           "statistical methods. Every number in the report is substituted from "
           "a recorded tool result -- the model cannot write one.")

with st.sidebar:
    st.header("Configuration")
    system = st.selectbox("System", list(SYSTEMS),
                          index=list(SYSTEMS).index("C_protocol"))
    st.caption({"A_direct": "Baseline: advice from summaries, no tools.",
                "B_tools": "Baseline: tools, no ordered protocol.",
                "C_protocol": "Structured agent: state machine, one revision, "
                              "verifier."}[system])
    engine = st.radio("Engine", ["Offline policy (deterministic)", "Claude"],
                      help="The offline engine runs the decision policy in "
                           "Python and needs no API key.")
    if engine == "Claude":
        if not api_key_available():
            st.error("ANTHROPIC_API_KEY is not set. Falling back to the offline "
                     "engine.")
            engine = "Offline policy (deterministic)"
        else:
            # Default to the model the held-out evaluation actually ran
            # on: it is the configuration these results describe, and it
            # is five times cheaper for anyone trying the demo. Any
            # model id is accepted.
            model = st.text_input("Model", "claude-haiku-4-5")
            effort = st.select_slider("Effort",
                                      ["low", "medium", "high", "xhigh", "max"],
                                      value="high")
    st.divider()
    source = st.radio("Input", ["Benchmark case", "Upload a CSV"])

# -- input ------------------------------------------------------------------

case = None
if source == "Benchmark case":
    label = st.selectbox("Case", list(DEMO_CASES))
    try:
        case = Case.load(DEMO_CASES[label])
    except FileNotFoundError:
        st.error("Benchmark not built. Run `make benchmark` first.")
        st.stop()
    st.info(f"**{case.case_id}** ({case.split}) -- {case.question}")
else:
    up = st.file_uploader("Analysis table (CSV)", type="csv")
    question = st.text_area("Analytical question",
                            "Do the two groups differ in the outcome?")
    objective = st.text_input("Analysis objective",
                              "compare two independent groups on a continuous outcome")
    if up is not None:
        try:
            df = pd.read_csv(up)
        except Exception as exc:
            st.error(f"Could not read that CSV: {exc}")
            st.stop()
        if df.empty or df.shape[1] < 2:
            st.error("The table needs at least two columns and one row.")
            st.stop()

        st.subheader("Design card")
        st.caption("A CSV cannot reveal whether rows are independent. If a "
                   "material fact is unknown, leave it blank -- the correct "
                   "behaviour is then to ask or abstain.")
        c1, c2, c3 = st.columns(3)
        card = _empty_card()
        none = "(none)"
        cols = [none] + list(df.columns)
        with c1:
            card["observational_unit"] = st.text_input("Observational unit", "")
            card["sampling_unit"] = st.text_input("Sampling unit", "")
            card["intended_population"] = st.text_input("Intended population", "")
        with c2:
            v = st.selectbox("Repeated-ID column", cols)
            card["repeated_id_column"] = None if v == none else v
            v = st.selectbox("Time column", cols)
            card["time_column"] = None if v == none else v
            v = st.selectbox("Clustering column", cols)
            card["clustering_column"] = None if v == none else v
        with c3:
            card["pairing"] = st.checkbox("Observations are paired")
            card["randomized"] = st.checkbox("Assignment was randomised")

        st.subheader("Variable roles")
        roles = {}
        rc = st.columns(min(4, len(df.columns)))
        for i, col in enumerate(df.columns):
            with rc[i % len(rc)]:
                roles[col] = st.selectbox(
                    col, ["context", "outcome", "group", "variable",
                          "predictor", "exposure"], key=f"role_{col}")
        roles = {k: v for k, v in roles.items() if v != "context"} or \
            {c: "context" for c in df.columns}

        if not card["observational_unit"] or not card["sampling_unit"]:
            card["observational_unit"] = card["observational_unit"] or "unknown"
            card["sampling_unit"] = card["sampling_unit"] or "unknown"

        case = Case(case_id="uploaded", split="dev", df=df, question=question,
                    objective=objective, card=card,
                    manifest={"variable_roles": roles, "case_id": "uploaded",
                              "origin": "synthetic", "split": "dev",
                              "n_rows": len(df)})

if case is None:
    st.stop()

# -- run --------------------------------------------------------------------

left, right = st.columns([2, 3])
with left:
    st.subheader("Data")
    st.dataframe(case.df.head(12), height=260, use_container_width=True)
    st.caption(f"{len(case.df):,} rows x {case.df.shape[1]} columns")
    with st.expander("Design card"):
        st.json(case.card)
    task = infer_task(case.df, case.roles)
    st.caption(f"Inferred task: **{task.kind}**")

if not st.button("Run analysis", type="primary"):
    st.stop()

if engine == "Claude":
    from aistat.agents.llm import AnthropicClient
    client = AnthropicClient(model=model, effort=effort)
else:
    client = RuleBasedClient("expert")

with st.spinner("Running..."):
    result = SYSTEMS[system](client).run(case)

with right:
    st.subheader("Decision")
    if result.error:
        st.error(f"Run failed: {result.error}")
    if result.method == "abstain":
        st.warning(f"**Abstained** -- {result.abstain_reason}")
        st.caption("No supported method is valid for this design. Selecting one "
                   "anyway would produce a plausible but invalid result.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Method", result.method.replace("_", " "))
        c2.metric("Tool calls", result.n_tool_calls)
        c3.metric("Revised", "yes" if result.revised else "no")

    rej = (result.selection or {}).get("rejected_alternatives") or {}
    if rej:
        st.markdown("**Rejected alternatives**")
        for alt, why in rej.items():
            st.markdown(f"- `{alt}` — {why}")

st.divider()
tabs = st.tabs(["Report", "Diagnostics", "Verification", "Trace", "Provenance"])

with tabs[0]:
    titles = {"problem_statement": "Problem statement", "data_audit": "Data audit",
              "method_decision": "Method decision", "results": "Results",
              "interpretation": "Interpretation", "limitations": "Limitations"}
    for key, title in titles.items():
        if key in result.rendered:
            st.markdown(f"**{title}**")
            st.write(result.rendered[key])
    md = "\n\n".join(f"## {t}\n\n{result.rendered.get(k, '')}"
                     for k, t in titles.items())
    st.download_button("Download report (Markdown)",
                       f"# Analysis report — {case.case_id}\n\n{md}\n",
                       file_name=f"{case.case_id}_report.md", mime="text/markdown")

with tabs[1]:
    shown = 0
    for ev in result.trace.events:
        if ev["kind"] != "tool_call" or ev.get("is_error"):
            continue
        st.markdown(f"**{ev['tool']}** `{ev['call_id']}`")
        st.caption(json.dumps(ev["arguments"]))
        shown += 1
    if not shown:
        st.caption("No diagnostics were requested.")

with tabs[2]:
    v = result.verification or {}
    if not v:
        st.caption("No verification pass recorded.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Passed", "yes" if v.get("passed") else "no")
        c2.metric("Findings", v.get("n_findings", 0))
        c3.metric("Provenance clean", "yes" if v.get("provenance_clean") else "no")
        for f in v.get("findings", []):
            icon = {"critical": "🔴", "major": "🟠", "minor": "🟡"}.get(f["severity"], "")
            st.markdown(f"{icon} **{f['check']}** — {f['detail']}")

with tabs[3]:
    st.code(" → ".join(result.trace.signature), language=None)
    st.dataframe(pd.DataFrame(result.trace.events), use_container_width=True,
                 height=340)

with tabs[4]:
    st.caption("Every number in the report resolves to one of these recorded "
               "tool results. An unknown reference fails the run.")
    keys = result.metadata.get("provenance_keys", [])
    used = set(result.metadata.get("refs_used", []))
    c1, c2, c3 = st.columns(3)
    c1.metric("Recorded values", len(keys))
    c2.metric("Cited in the report", len(used))
    c3.metric("Provenance rejections", result.provenance_rejections)
    st.caption("A rejection is an attempt to cite a value no tool produced. For "
               "the structured agent this is the empirical counterpart to "
               "numerical fidelity, which is otherwise guaranteed by construction.")
    if keys:
        st.dataframe(pd.DataFrame({"reference": keys,
                                   "cited in report": [k in used for k in keys]}),
                     use_container_width=True, height=320)
