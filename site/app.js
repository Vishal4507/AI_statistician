/* AI Statistician — static benchmark explorer.
 *
 * Everything here reads precomputed JSON. No statistics are recalculated in the
 * browser: the premise of the project is that validated libraries perform every
 * numerical operation, so reimplementing any of it here would undermine it.
 */

const SYSTEM_LABEL = {
  A_direct: "A · Direct LLM",
  B_tools: "B · LLM with tools",
  C_protocol: "C · Structured agent",
};

const state = { meta: null, cases: [], runs: {}, view: "overview" };

const $ = (sel, root = document) => root.querySelector(sel);
const app = () => $("#app");

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const pct = (v) => (v === null || v === undefined || Number.isNaN(v) ? "—" : (v * 100).toFixed(1) + "%");
const num = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v) ? "—" : Number(v).toFixed(d));

// ---------------------------------------------------------------- boot

async function boot() {
  try {
    const [meta, cases, runs] = await Promise.all([
      fetch("data/meta.json").then((r) => r.json()),
      fetch("data/cases.json").then((r) => r.json()),
      fetch("data/runs.json").then((r) => r.json()),
    ]);
    Object.assign(state, { meta, cases, runs });
    render();
  } catch (err) {
    app().innerHTML =
      `<div class="callout warn"><span class="kicker">Could not load data</span>
       <p>${esc(err.message)}</p>
       <p>The explorer needs <code>data/*.json</code> beside it. Regenerate with
       <code>python scripts/export_site.py</code>, and serve over HTTP rather than
       opening the file directly — <code>fetch</code> is blocked on
       <code>file://</code>.</p></div>`;
  }
}

document.addEventListener("click", (e) => {
  const tab = e.target.closest(".tab");
  if (!tab) return;
  // The status page sits in the tab strip but is a separate document, not a
  // view. Without this, clicking it would clear state.view and re-render the
  // explorer to its fallback in the moment before the browser navigated away.
  if (tab.tagName === "A") return;
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("is-active"));
  tab.classList.add("is-active");
  state.view = tab.dataset.view;
  render();
  window.scrollTo({ top: 0 });
});

function render() {
  const views = { overview, results, cases: casesView, reports, methods };
  app().innerHTML = (views[state.view] || overview)();
  wireFilters();
}

// ---------------------------------------------------------------- overview

function overview() {
  const m = state.meta;
  const expert = state.runs["heldout_rulebased_expert"];
  const naive = state.runs["heldout_rulebased_naive"];
  const live = state.runs["dev_claude-opus-5_high"];

  const c = (b) => b?.per_system.find((s) => s.system === "C_protocol");
  const bT = (b) => b?.per_system.find((s) => s.system === "B_tools");

  return `
  <h2>What this is</h2>
  <p class="lede">A constrained statistical decision system. It receives a dataset,
    a question and a design card; selects a method from a closed library of 14;
    executes it through validated SciPy and statsmodels tools; checks diagnostics;
    and produces a traceable interpretation — or abstains when no supported method
    is valid.</p>

  <div class="stats">
    <div><span class="v accent">${m.n_cases}</span><span class="k">benchmark cases</span></div>
    <div><span class="v">${m.n_supported}</span><span class="k">supported</span></div>
    <div><span class="v risk">${m.n_abstention}</span><span class="k">abstention</span></div>
    <div><span class="v">${m.n_dev} / ${m.n_heldout}</span><span class="k">dev / held out</span></div>
    <div><span class="v ok">${pct(m.label_audit?.agreement_rate)}</span><span class="k">label audit agreement</span></div>
  </div>

  <h3>The claim this system defends</h3>
  <p><strong>The model cannot write a number.</strong> Every tool return is registered
    in a run-scoped store; the report schema rejects raw numeric literals; the model
    emits <code>{{r7.welch_t.p_value}}</code> templates substituted at render time;
    an unknown reference fails the run.</p>
  <p>The consequence is stated honestly rather than claimed as a result: for the
    structured agent, numerical fidelity is an <em>architectural guarantee</em>, not
    an empirical finding. The empirical counterpart is the provenance rejection
    rate — how often the model reached for a reference that did not exist.</p>

  ${live ? `
  <h3>Live evidence — Claude Opus 5, development set</h3>
  <p class="lede">Real model runs. Preliminary: development set, small samples,
    one repetition.</p>
  ${systemTable(live)}
  <div class="callout">
    <span class="kicker">Where the systems separate</span>
    <p>On the design-hazard cases the structured agent abstained every time; the
      tool-enabled baseline never did, fitting a plausible-looking model to data
      whose independence assumption fails. That is the failure this project exists
      to prevent.</p>
  </div>` : ""}

  <h3>Offline calibration — and why the expert row is circular</h3>
  <p>A deterministic policy client implements the same interface as the live path,
    which makes the harness runnable and testable without an API key. It is
    <strong>not an arm of the experiment</strong>.</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Client</th><th class="num">B</th><th class="num">C</th>
      <th class="num">C abstention recall</th><th>Reading</th></tr></thead>
    <tbody>
      <tr><td>Expert policy</td><td class="num">${pct(bT(expert)?.accuracy)}</td>
        <td class="num">${pct(c(expert)?.accuracy)}</td>
        <td class="num">${pct(c(expert)?.abstention_recall)}</td>
        <td><strong>Circular</strong> — this policy derived the gold labels</td></tr>
      <tr class="hi"><td>Naive policy</td><td class="num">${pct(bT(naive)?.accuracy)}</td>
        <td class="num">${pct(c(naive)?.accuracy)}</td>
        <td class="num">${pct(c(naive)?.abstention_recall)}</td>
        <td><strong>Informative</strong> — see below</td></tr>
    </tbody></table></div>
  <p>The naive row is the useful one. Inside the <em>same state machine</em>, a policy
    that ignores the design card and treats assumption-test p-values as switches drops
    to ${pct(c(naive)?.accuracy)} with zero abstention recall.
    <strong>The architecture alone does not produce the uplift; the decision policy
    inside it does.</strong></p>

  <h3>Data sources</h3>
  <div class="tablewrap"><table>
    <thead><tr><th>Dataset</th><th class="num">UCI</th><th class="num">Rows</th><th>DOI</th></tr></thead>
    <tbody>${Object.entries(m.sources || {}).map(([k, v]) => `
      <tr><td>${esc(k.replace(/_/g, " "))}</td><td class="num">${v.uci_id}</td>
        <td class="num">${v.n_rows.toLocaleString()}</td>
        <td><code>${esc(v.doi)}</code></td></tr>`).join("")}
    </tbody></table></div>
  <p>All CC BY 4.0. Raw files are written once and never overwritten; row counts and
    SHA-256 hashes are recorded so the benchmark rebuilds identically.</p>`;
}

function systemTable(bundle) {
  return `<div class="tablewrap"><table>
    <thead><tr><th>System</th><th class="num">n</th><th class="num">Accuracy</th>
      <th class="num">Abstention recall</th><th class="num">Unsafe rate</th>
      <th class="num">Assumption coverage</th><th class="num">Tool calls</th></tr></thead>
    <tbody>${bundle.per_system.map((s) => `
      <tr${s.system === "C_protocol" ? ' class="hi"' : ""}>
        <td>${esc(SYSTEM_LABEL[s.system] || s.system)}</td>
        <td class="num">${s.n}</td><td class="num">${pct(s.accuracy)}</td>
        <td class="num">${pct(s.abstention_recall)}</td>
        <td class="num">${pct(s.unsafe_rate)}</td>
        <td class="num">${pct(s.assumption_coverage)}</td>
        <td class="num">${num(s.mean_tool_calls, 1)}</td></tr>`).join("")}
    </tbody></table></div>`;
}

// ---------------------------------------------------------------- results

function results() {
  const figures = [
    ["fig1_accuracy.png", "Method-selection accuracy with Wilson 95% intervals."],
    ["fig4_abstention.png", "Abstention recall on design-hazard cases — the sharpest separation."],
    ["fig2_risk_coverage.png", "Risk–coverage: accuracy among answered cases, against how many were answered."],
    ["fig3_failures.png", "Failure counts by stage of the error taxonomy."],
  ];
  return `
  <h2>Results</h2>
  <p class="lede">Three kinds of evidence, kept separate. Conflating them would be
    the easiest way to make this project look stronger than it is.</p>
  ${figures.map(([f, cap]) => `<figure class="site-figure">
      <img src="figures/${f}" alt="${esc(cap)}" loading="lazy">
      <figcaption>${esc(cap)}</figcaption></figure>`).join("")}
  ${Object.entries(state.runs).map(([key, b]) => `
    <h3>${esc(b.label)}</h3>
    <p class="meta"><span class="chip">${b.n_runs} runs</span>
       <span class="chip">${b.n_cases} cases</span>
       ${key.includes("claude") ? '<span class="chip accent">live model</span>'
                                : '<span class="chip">offline policy</span>'}</p>
    ${systemTable(b)}
    ${b.failures.length ? `
      <p class="section-title">Failure taxonomy</p>
      <div class="tablewrap"><table>
        <thead><tr><th>System</th><th>Stage</th><th class="num">Runs</th></tr></thead>
        <tbody>${b.failures.map((f) => `<tr><td>${esc(SYSTEM_LABEL[f.system] || f.system)}</td>
          <td><code>${esc(f.stage)}</code></td><td class="num">${f.n}</td></tr>`).join("")}
        </tbody></table></div>` : "<p>No failures recorded.</p>"}`).join("")}

  <div class="callout warn">
    <span class="kicker">Not present</span>
    <p>The held-out evaluation on a live model has not been run — it requires API
      credit. The runner is resumable and the benchmark is frozen, so it can be
      executed at any time without invalidating anything above. Everything shown
      here is either an offline calibration or preliminary development-set evidence,
      and is labelled as such.</p>
  </div>`;
}

// ---------------------------------------------------------------- cases

function casesView() {
  const families = [...new Set(state.cases.map((c) => c.family))].sort();
  const methods = state.meta.methods;
  return `
  <h2>Benchmark</h2>
  <p class="lede">64 cases — ${state.meta.n_supported} supported,
    ${state.meta.n_abstention} abstention. Never hand-authored: one declarative
    registry entry produces the whole six-file package, and synthetic gold is derived
    from the realised sample rather than the requested generator parameters.</p>

  <div class="filters">
    <label>Split <select id="f-split"><option value="">all</option>
      <option value="dev">dev</option><option value="heldout">held out</option></select></label>
    <label>Origin <select id="f-origin"><option value="">all</option>
      <option value="synthetic">synthetic</option><option value="public">public</option></select></label>
    <label>Family <select id="f-family"><option value="">all</option>
      ${families.map((f) => `<option>${esc(f)}</option>`).join("")}</select></label>
    <label>Gold <select id="f-gold"><option value="">all</option>
      ${methods.map((m) => `<option>${esc(m)}</option>`).join("")}</select></label>
    <input id="f-text" type="search" placeholder="search questions…" aria-label="Search questions">
    <span class="count" id="f-count"></span>
  </div>
  <div id="case-list"></div>`;
}

function renderCases() {
  const f = {
    split: $("#f-split")?.value || "",
    origin: $("#f-origin")?.value || "",
    family: $("#f-family")?.value || "",
    gold: $("#f-gold")?.value || "",
    text: ($("#f-text")?.value || "").toLowerCase(),
  };
  const rows = state.cases.filter((c) =>
    (!f.split || c.split === f.split) &&
    (!f.origin || c.origin === f.origin) &&
    (!f.family || c.family === f.family) &&
    (!f.gold || c.gold_method === f.gold) &&
    (!f.text || c.question.toLowerCase().includes(f.text) ||
      c.case_id.toLowerCase().includes(f.text)));

  $("#f-count").textContent = `${rows.length} of ${state.cases.length}`;
  $("#case-list").innerHTML = rows.map(caseCard).join("") ||
    '<p class="loading">No cases match.</p>';
}

function caseCard(c) {
  const abstain = c.gold_method === "abstain";
  const cols = c.columns.slice(0, 10);
  return `
  <article class="card ${abstain ? "abstain" : "supported"}">
    <h4><code>${esc(c.case_id)}</code>
      <span class="chip ${abstain ? "abstain" : "ok"}">${esc(c.gold_method)}</span>
      <span class="chip">${esc(c.split)}</span>
      <span class="chip">${esc(c.origin)}</span></h4>
    <p class="q">${esc(c.question)}</p>
    <p class="meta">
      <span>${c.n_rows.toLocaleString()} rows × ${c.columns.length} cols</span>
      ${c.accepted_methods.length > 1
        ? `<span>accepted: ${c.accepted_methods.map((m) => `<code>${esc(m)}</code>`).join(", ")}</span>` : ""}
      ${c.abstain_reason ? `<span>reason: <code>${esc(c.abstain_reason)}</code></span>` : ""}
      ${c.source ? `<span>source: ${esc(c.source)}</span>` : ""}
    </p>
    <details><summary>design card, data preview, gold rationale</summary>
      <div class="detail-body">
        <p class="section-title">Design card</p>
        <pre>${esc(JSON.stringify(c.design_card, null, 2))}</pre>
        <p class="section-title">Variable roles</p>
        <pre>${esc(JSON.stringify(c.variable_roles, null, 2))}</pre>
        <p class="section-title">Data preview</p>
        <div class="tablewrap"><table>
          <thead><tr>${cols.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>
          <tbody>${c.preview.map((r) => `<tr>${cols.map((h) =>
            `<td>${esc(r[h])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
        <p class="section-title">Gold rationale <span class="chip">not visible to the agent</span></p>
        <p class="prose">${esc(c.rationale)}</p>
        <p class="section-title">Required checks</p>
        <p class="prose">${c.required_checks.map((k) => `<code>${esc(k)}</code>`).join(" ")}</p>
      </div></details>
  </article>`;
}

// ---------------------------------------------------------------- reports

function reports() {
  const keys = Object.keys(state.runs);
  return `
  <h2>Reports &amp; traces</h2>
  <p class="lede">Every rendered report, with the state-machine trace that produced
    it. Numbers shown are substituted values — the model wrote references, not
    digits.</p>
  <div class="filters">
    <label>Run set <select id="r-run">
      ${keys.map((k) => `<option value="${esc(k)}">${esc(state.runs[k].label)}</option>`).join("")}
    </select></label>
    <label>System <select id="r-system"><option value="">all</option>
      ${Object.entries(SYSTEM_LABEL).map(([k, v]) =>
        `<option value="${esc(k)}">${esc(v)}</option>`).join("")}</select></label>
    <input id="r-text" type="search" placeholder="search case id…" aria-label="Search case id">
    <span class="count" id="r-count"></span>
  </div>
  <div id="report-list"></div>`;
}

function renderReports() {
  const run = $("#r-run")?.value || Object.keys(state.runs)[0];
  const sys = $("#r-system")?.value || "";
  const text = ($("#r-text")?.value || "").toLowerCase();
  const bundle = state.runs[run];
  if (!bundle) return;

  const rows = bundle.reports
    .filter((r) => (!sys || r.system === sys) &&
                   (!text || r.case_id.toLowerCase().includes(text)))
    .slice(0, 120);

  $("#r-count").textContent = `${rows.length} shown`;
  $("#report-list").innerHTML = rows.map(reportCard).join("") ||
    '<p class="loading">No reports match.</p>';
}

const SECTION_TITLES = {
  problem_statement: "Problem statement", data_audit: "Data audit",
  method_decision: "Method decision", results: "Results",
  interpretation: "Interpretation", limitations: "Limitations",
};

function reportCard(r) {
  const abstain = r.method === "abstain";
  return `
  <article class="card ${abstain ? "abstain" : "supported"}">
    <h4><code>${esc(r.case_id)}</code>
      <span class="chip accent">${esc(SYSTEM_LABEL[r.system] || r.system)}</span>
      <span class="chip ${abstain ? "abstain" : "ok"}">${esc(r.method)}</span>
      ${r.revised ? '<span class="chip">revised once</span>' : ""}
      <span class="chip">${r.n_tool_calls} tool calls</span>
      ${r.provenance_values ? `<span class="chip">${r.provenance_values} values recorded</span>` : ""}
      ${r.pre_fix_residue ? '<span class="chip abstain">pre-fix capture</span>' : ""}</h4>
    ${r.pre_fix_residue ? `<p class="meta"><em>Recorded before the reference pattern
      was widened. A store key containing spaces (a UCI column named
      "Rented Bike Count") could not match the pattern, so the template was emitted
      verbatim instead of failing. Kept as evidence; the current renderer blocks it.</em></p>` : ""}
    ${Object.keys(r.rejected || {}).length ? `<p class="meta">rejected:
      ${Object.entries(r.rejected).map(([m, why]) =>
        `<span><code>${esc(m)}</code> — ${esc(why)}</span>`).join(" ")}</p>` : ""}
    <details><summary>full report and trace</summary>
      <div class="detail-body">
        ${Object.entries(SECTION_TITLES).map(([k, t]) => r.rendered[k]
          ? `<p class="section-title">${t}</p><p class="prose">${esc(r.rendered[k])}</p>` : "").join("")}
        <p class="section-title">State-machine trace</p>
        <div class="trace">${esc((r.trace || []).join("  →  "))}</div>
        ${r.verification && Object.keys(r.verification).length ? `
          <p class="section-title">Verification</p>
          <pre>${esc(JSON.stringify(r.verification, null, 2))}</pre>` : ""}
      </div></details>
  </article>`;
}

// ---------------------------------------------------------------- methods

function methods() {
  const groups = [
    ["Two independent groups", ["student_t", "welch_t", "mann_whitney"]],
    ["Three or more groups", ["one_way_anova", "welch_anova", "kruskal_wallis"]],
    ["Two categorical", ["chi_square", "fisher_exact"]],
    ["Two continuous or ordinal", ["pearson", "spearman"]],
    ["Regression", ["ols", "logistic", "poisson", "negative_binomial"]],
  ];
  const counts = {};
  state.cases.forEach((c) => { counts[c.gold_method] = (counts[c.gold_method] || 0) + 1; });

  return `
  <h2>Method library</h2>
  <p class="lede">Closed by design. <code>abstain</code> is a decision, not a member
    of the library, and there is deliberately no general code-execution tool — it
    would let the model bypass the method policy and make traces incomparable across
    systems.</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Analytical task</th><th>Methods</th><th class="num">Cases</th></tr></thead>
    <tbody>${groups.map(([label, ms]) => `
      <tr><td>${esc(label)}</td>
        <td>${ms.map((m) => `<code>${esc(m)}</code>`).join(" ")}</td>
        <td class="num">${ms.reduce((a, m) => a + (counts[m] || 0), 0)}</td></tr>`).join("")}
      <tr class="hi"><td>No valid supported method</td>
        <td><code>abstain</code></td><td class="num">${counts["abstain"] || 0}</td></tr>
    </tbody></table></div>

  <h3>Decision principles</h3>
  <ul class="tight">
    <li><strong>Design validity precedes distribution checks.</strong> Dependence,
      pairing, clustering and time order invalidate every in-scope method regardless
      of how well the variable types fit.</li>
    <li><strong>Assumption tests are evidence, not switches.</strong> With large
      samples they reject trivial departures; with small samples they have little
      power. Group size, spread, skew and influence are weighed together.</li>
    <li><strong>Welch is the default</strong> when variances differ or groups are
      unbalanced. Student requires an affirmative equal-variance justification.</li>
    <li><strong>Rank tests describe stochastic ordering</strong>, not medians, unless
      the shapes match.</li>
    <li><strong>Pearson for an approximately linear relationship</strong> without
      dominant points; Spearman for monotone or ordinal ones.</li>
    <li><strong>Poisson versus negative binomial is decided from conditional
      dispersion</strong> after fitting — never from the marginal variance alone.</li>
    <li><strong>When a material design fact is unknown, ask or abstain.</strong></li>
  </ul>

  <h3>Label audit</h3>
  <p>Every label is re-derived from the case package alone, without reading gold:
    <strong>${state.meta.label_audit?.n_agree ?? "—"} of
    ${state.meta.label_audit?.n_cases ?? "—"} agree</strong>.</p>
  <div class="callout warn">
    <span class="kicker">Stated limitation</span>
    <p>${esc(state.meta.label_audit?.caveat || "")}</p>
  </div>`;
}

// ---------------------------------------------------------------- wiring

function wireFilters() {
  if (state.view === "cases") {
    ["f-split", "f-origin", "f-family", "f-gold"].forEach((id) =>
      $("#" + id)?.addEventListener("change", renderCases));
    $("#f-text")?.addEventListener("input", renderCases);
    renderCases();
  }
  if (state.view === "reports") {
    ["r-run", "r-system"].forEach((id) =>
      $("#" + id)?.addEventListener("change", renderReports));
    $("#r-text")?.addEventListener("input", renderReports);
    renderReports();
  }
}

boot();
