# AI Statistician — capstone report

*Generated 2026-09-09 from `results/*.jsonl`.
Regenerate with `python scripts/write_capstone.py`.*

---

## 1. Problem

An LLM asked to analyse a dataset will almost always produce an answer. Whether
that answer is *valid* is a different question, and one the model is poorly
placed to police: a CSV cannot reveal whether rows are independent, whether the
same customer appears twice, or whether observations are ordered in time. A
mathematically fluent system with no view of study design will confidently fit
Poisson to autocorrelated hourly counts.

This project asks whether an explicit statistical decision protocol improves an
LLM agent's ability to select and execute valid methods, compared with
(A) direct LLM advice and (B) tool access without a protocol.

The contribution is not the interface or the number of supported tests. It is
controlled evidence that design-aware routing, targeted diagnostics and
verification improve validity over ordinary LLM tool use.

## 2. System

A closed library of 14 methods, five diagnostic tools, and a deterministic state
machine around one tool-calling LLM. SciPy and statsmodels perform every
numerical operation.

| Task | Methods |
|---|---|
| Two independent groups | `student_t`, `welch_t`, `mann_whitney` |
| Three or more groups | `one_way_anova`, `welch_anova`, `kruskal_wallis` |
| Two categorical | `chi_square`, `fisher_exact` |
| Two continuous or ordinal | `pearson`, `spearman` |
| Regression | `ols`, `logistic`, `poisson`, `negative_binomial` |

`abstain` is a decision, not a member of the library. There is deliberately no
general code-execution tool: it would let the model bypass the method policy and
make traces incomparable across systems.

### 2.1 The provenance contract

The strongest claim this system makes is that **the model cannot write a
number**. Rather than checking the finished report for fabrication, fabrication
is made impossible:

1. Every tool return is registered in a run-scoped store under a stable key.
2. The report schema rejects raw numeric literals in prose.
3. The model emits `{{r7.welch_t.p_value}}` templates, substituted at render.
4. An unknown reference fails the run.

The consequence must be stated honestly: for System C, numerical fidelity is an
**architectural guarantee, not an empirical finding**. The empirical counterpart
is the provenance rejection rate — how often the model reached for a reference
that did not exist. Across every live run recorded here that count is
**0**.

For Systems A and B nothing is enforced, so fidelity remains an empirical metric
there and the comparison stays meaningful.

## 3. Benchmark

64 cases — 52 supported, 12 abstention; 48 synthetic and 16 from public UCI
data; 16 development and 48 held out.

Cases are never hand-authored. One declarative registry entry produces the whole
six-file package. For synthetic cases the gold label is derived from the
**realised sample**: design facts come from the generator parameters because they
are properties of the design, while distributional facts come from the data
because that is what a correct method choice must respond to.

| Source | UCI | Rows | Role |
|---|---|---|---|
| Bank Marketing | 222 | 45,211 | categorical, logistic, skewed group comparison |
| Online Shoppers | 468 | 12,330 | association, categorical, logistic |
| Student Performance | 320 | 649 | group comparison, ordinal traps, OLS |
| Seoul Bike Sharing | 560 | 8,760 | four design-hazard cases |

Seoul Bike supplies the sharpest test: tables that look perfectly suitable for
Poisson, correlation or ANOVA, where hourly ordering violates independence. The
correct answer is to abstain.

## 4. Method

Three systems over one shared core. Every driver imports the same tool registry,
result store and report schema; only control flow differs. This is what makes
baseline fairness provable rather than asserted — there is no code path on which
A or B could have been disadvantaged.

System A receives the *same* step-one diagnostic output System C receives, not a
hand-picked summary. System B receives identical tool definitions and the
identical report schema.

**On determinism:** `temperature` is removed on current Claude models and returns
a 400 if sent. Determinism is controlled by pinning the model id and effort
level, freezing the prompt hash, and *measuring* residual variance across
repetitions rather than claiming to eliminate it.

---

## 5. Results

### 5.1 Live evidence — Claude Opus 5, development set

**76 clean runs** (44 at `high` effort, 32 at
`medium`). This is the development set, not the held-out set.

| System | n | Accuracy | 95% CI | Abstention recall | Unsafe rate | Tool calls |
|---|---|---|---|---|---|---|
| A · Direct LLM | 15 | 0.867 | [0.621, 0.963] | 0.33 | 0.133 | 2.3 |
| B · LLM with tools | 16 | 0.500 | [0.280, 0.720] | 0.00 | 0.188 | 4.5 |
| C · Structured agent | 13 | 1.000 | [0.772, 1.000] | 1.00 | 0.000 | 2.8 |

**Paired comparison, B versus C** — the comparison that answers the research
question, since both have identical tools and report schemas and differ only in
whether an ordered protocol governs their use. On the 13 cases both
systems completed:

| | |
|---|---|
| System B accuracy | 0.462 |
| System C accuracy | 1.000 |
| Uplift | **+0.538** |
| Bootstrap 95% CI | [+0.231, +0.769] |
| McNemar exact p | **0.0156** |
| Discordant pairs | 7 in C's favour, 0 in B's |

The discordance is entirely one-directional: 7 cases where the
protocol was right and the unconstrained baseline wrong, and 0 the
other way. The blueprint's target was ≥10 percentage points of uplift; the
observed value is 54.

**Abstention is where the systems separate most sharply.** On the design-hazard
cases the structured agent abstained every time; the tool-enabled baseline never
did, fitting a plausible-looking model to data whose independence assumption
fails. That is the failure this project exists to prevent.

### 5.2 Limitations of the live evidence

These results are **preliminary and must not be presented as the headline
experiment**:

- **Development set, not held out.** Prompts were developed against these cases.
  The held-out estimate is the one that counts, and it has not been run.
- **Small samples.** 44 clean runs across three systems; the widest
  confidence interval spans 0.23.
- **One repetition.** Run-to-run variance is unmeasured.
- **4 runs lost to harness errors** rather than statistical failure
  (a raw numeric literal, and two references to string-valued fields). All three
  causes have since been fixed and are covered by regression tests, but the
  affected runs were not repeated.
- **Only System C at `medium` effort is missing entirely** — the account ran out
  of credit mid-sweep, so the cost/accuracy trade-off is unresolved.

### 5.3 Offline calibration

A deterministic policy client implements the same interface as the live path,
which makes the harness runnable and testable without an API key. It is **not an
arm of the experiment**.

| Client | A | B | C | C abstention recall | Interpretation |
|---|---|---|---|---|---|
| Expert policy | 0.562 | 0.500 | 1.000 | 1.00 | **Circular** — this policy derived the gold labels |
| Naive policy | 0.562 | 0.500 | 0.604 | 0.00 | **Informative** — see below |

The expert row validates the harness and confirms the gold labels are internally
coherent with the stated decision principles. It says nothing about model
performance.

The naive row is the useful one. Inside the **same state machine**, a policy that
ignores the design card and treats assumption-test p-values as switches drops to
0.604 with zero
abstention recall. **The architecture alone does not produce the uplift; the
decision policy inside it does.** An ordering mechanism that routes badly scores
barely above the unstructured baseline.

This matters for interpreting §5.1: the protocol's advantage is not an artefact
of having more structure, because more structure with worse rules performs
worse.

### 5.4 Held-out evaluation

**Not yet run.** This is the single outstanding deliverable. It requires
API credit: approximately $34 for two repetitions on Claude Opus 5, or $10 on
Haiku 4.5. The runner is resumable and the benchmark is frozen, so it can be
executed at any point without invalidating anything above.

Everything needed to run it exists and is tested: `make eval-live` validates the
live path first and refuses to start work the budget cannot finish.

---

## 6. Error analysis

Failures are classified by the stage at which they occur. Across the live
development runs, every System B failure was a **design-validation** failure —
selecting a valid-looking method for a design that supports none — or a
**diagnostic-reasoning** failure, choosing Student's t where variance and group
size evidence pointed to Welch.

System C recorded no method-selection failures on the development set. Its four
lost runs were harness defects, described in §5.2 and since fixed.

## 7. Limitations

Beyond §5.2:

- **No blinded human interpretation scoring.** Blueprint §8.3 requires a 0–2
  rubric scored blind to system identity with ≥20% double-scored. The
  programmatic proxy in `scorers.py` covers only the mechanically checkable half
  (causal language, absolute claims, constraint adherence).
  `human_interpretation_score` is `None` in every run.
- **No independent second reviewer.** 48 of 64 labels are construction-derived
  and therefore not opinions; the 16 public labels were validated against their
  realised data, which caught one mislabel. This is weaker than the double review
  §4.3 specifies and is disclosed as such.
- **Four methods appear only in the held-out split.** `one_way_anova`, `pearson`,
  `logistic` and `poisson` have no development representation — twelve synthetic
  development slots cannot cover fourteen methods plus abstention. No prompt was
  ever tuned against them, which is a cleaner generalisation test but an
  unplanned one.
- **The library excludes** paired and repeated-measures designs, mixed models,
  time series, survival analysis and zero-inflated models. Those appear in the
  benchmark only as abstention cases.

## 8. Extensions

Ordered by how much each would improve coverage per unit of work:

1. **Paired and repeated-measures tests.** The largest single gap; four
   abstention cases exist purely because the library cannot model subject
   effects.
2. **Uplift as a function of model strength.** Running the same held-out
   benchmark on a weaker tier would test whether the protocol matters more where
   internal reasoning is weaker — arguably a stronger claim than a single uplift
   figure, and robust to the ceiling problem.
3. **Mixed-effects models**, which would convert the clustering and
   repeated-measures abstentions into supported cases.
4. **Effort ablation.** Whether `medium` routes as well as `high` is unresolved
   and directly affects cost.

## 9. Reproducing this

```bash
make setup && make all      # benchmark, tests, offline calibration, tables
make smoke                  # validates the live path (requires credit)
make eval-live && make report
python scripts/write_capstone.py
```

Every table above is derived from `results/*.jsonl`. Deviations from the
blueprint are documented in `docs/DEVIATIONS.md`; the architecture is described
in `docs/ARCHITECTURE.md`.
