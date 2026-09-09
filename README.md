# AI Statistician

LLM-guided selection, validation, execution and interpretation of statistical
methods. The system receives a dataset, an analytical question and a design
card; selects a method from a closed library of 14; executes it through
validated SciPy and statsmodels tools; checks diagnostics; and produces a
traceable interpretation — or abstains when no supported method is valid.

Implements the capstone blueprint with four amendments recorded in
[`docs/DEVIATIONS.md`](docs/DEVIATIONS.md).

## The claim this codebase defends

**The model cannot write a number.** Every tool return is registered in a
run-scoped store; the report schema rejects raw numeric literals in prose; the
model emits `{{r7.welch_t.p_value}}` templates that are substituted at render
time; an unknown reference fails the run. Numerical fidelity is therefore an
architectural guarantee for the structured agent rather than an observed rate —
see [`docs/DEVIATIONS.md`](docs/DEVIATIONS.md) for how to report that honestly.

## Quick start

```bash
make setup && make all
```

That downloads the four UCI datasets, builds all 64 case packages, validates
them, runs 113 tests, executes a 432-run offline evaluation, and rebuilds every
result table. It needs no API key and takes about three minutes.

For the live experiment, in this order:

```bash
export ANTHROPIC_API_KEY=...
make smoke      # a few cents; validates the live path end to end
make pilot      # chooses the model tier from development-set headroom
make eval-live  # the held-out experiment
make report
```

`make smoke` exists because the offline suite cannot reach the live client. It
exercises the request shape, structured outputs, tool_use/tool_result threading,
prompt caching and the provenance contract against a real model, for a few
cents. A failure there is cheap; the same failure three hundred runs into a paid
evaluation is not. `make eval-live` runs it first and will not proceed if it
fails.

`make pilot` must run **before** the prompts are frozen and before any held-out
contact. It reads only the development set and records its decision in
`reports/pilot_decision.json`, which is what makes the tier choice legitimate
rather than post-hoc.

For the demo:

```bash
make demo
```

## What is here

| Path | Contents |
|---|---|
| `src/aistat/schemas/` | Typed state objects; the provenance-enforcing report schema |
| `src/aistat/provenance/` | `ResultStore` — registration, substitution, audit |
| `src/aistat/tools/` | 5 diagnostics, 14 methods, effect sizes with intervals, verifier |
| `src/aistat/benchmark/` | Declarative registry, generators, builder, validator, public cases |
| `src/aistat/agents/` | Decision policy, trace log, and the three system drivers |
| `src/aistat/evaluation/` | Resumable runner, scorers, bootstrap and McNemar analysis |
| `benchmark/` | 64 case packages; gold and oracles in a separate tree |
| `src/aistat/evaluation/blinded.py` | Blinded human interpretation scoring |
| `app/` | Streamlit demo |
| `docs/CAPSTONE_REPORT.md` | Generated capstone report |

## The three systems

The experimental design is expressed in the file layout, not asserted in prose.
All three drivers import the same `ToolRegistry`, the same `ResultStore` and the
same `FinalReport` schema; only control flow differs.

| System | Driver | What it isolates |
|---|---|---|
| A. Direct LLM | `DirectDriver` | Baseline advice. Receives the *same* step-1 evidence C gets, not a hand-picked digest. |
| B. LLM with tools | `ToolLoopDriver` | The value of computation. Identical tool definitions and report schema; an unconstrained loop. |
| C. Structured agent | `ProtocolDriver` | The value of explicit reasoning. State machine, routing policy, one revision, verifier. |

## Method library

| Task | Methods |
|---|---|
| Two independent groups | `student_t`, `welch_t`, `mann_whitney` |
| Three or more groups | `one_way_anova`, `welch_anova`, `kruskal_wallis` |
| Two categorical | `chi_square`, `fisher_exact` |
| Two continuous or ordinal | `pearson`, `spearman` |
| Regression | `ols`, `logistic`, `poisson`, `negative_binomial` |

`abstain` is a decision, not a member of the library. There is deliberately no
`run_python` tool: unrestricted execution would let the model bypass the method
policy and make traces incomparable across systems.

## Benchmark

64 cases — 52 supported, 12 abstention; 48 synthetic and 16 from public data;
16 development and 48 held out.

Cases are never hand-authored. One declarative registry entry (about fifteen
lines of generator parameters) produces the whole six-file package. For
synthetic cases the gold label is **derived from the realised sample**: design
facts come from the generator parameters because they are properties of the
design, and distributional facts come from the data because that is what a
correct method choice must respond to.

The sixteen public cases are the ones that genuinely need adjudication. Each
label is proposed from design reasoning and then checked against its realised
data by `validate_label`, which caught and corrected one mislabel during
construction.

## Data sources

| Dataset | UCI | Rows | DOI |
|---|---|---|---|
| Bank Marketing | 222 | 45,211 | 10.24432/C5K306 |
| Online Shoppers Purchasing Intention | 468 | 12,330 | 10.24432/C5F88Q |
| Student Performance | 320 | 649 | 10.24432/C5TG7T |
| Seoul Bike Sharing Demand | 560 | 8,760 | 10.24432/C5F62R |

All CC BY 4.0. Raw files are written once and never overwritten; row counts and
SHA-256 hashes are recorded in `data/raw/MANIFEST.json`.

Seoul Bike supplies four deliberate design-hazard cases: the table looks
perfectly suitable for Poisson, correlation or ANOVA, but hourly ordering
violates independence. Recognising that is the point.

## Reproducibility

Every run records the model id, effort level, prompt hash, git commit, library
versions and platform. Results append to JSONL keyed on
`(system, case_id, rep)`, so an interrupted evaluation resumes rather than
restarts. Every table regenerates from the raw logs with `make analyze`.

**On determinism**: `temperature` is removed on current Claude models and
returns a 400 if sent. Determinism is controlled by pinning the model id and
effort, freezing the prompt hash, and *measuring* residual variance across
repetitions rather than pretending to eliminate it.

## Offline engine

`RuleBasedClient` implements the same client protocol as the live path by
executing the decision policy in Python. It has two settings — `expert` and
`naive` — and exists so the harness, scorers and demo are runnable and testable
without an API key.

It is **not** an arm of the experiment. The `expert` policy is what derived the
gold labels, so its score is circular: 100% is a label-coherence check and a
harness validation, not a result. The `naive` policy is informative in a way the
expert one is not — it scores 60% with zero abstention recall *even inside the
state machine*, which shows the architecture alone is not what produces the
uplift. The decision policy inside it is.

## The two things that need a human, not a key

**Blinded interpretation scoring** (§8.2 metric 5, §8.3). The blueprint requires a
0-2 rubric applied by a scorer blind to system identity, with ≥20% double-scored
and agreement reported. No API key substitutes for that judgement. The instrument
is built:

```bash
make blind RUN=heldout_claude-opus-5   # prepares packet, sheet, sealed key
# a human scores reports/blinded/scores_blank.csv
make blind-ingest                      # joins to the key, reports kappa
```

Reports are shuffled, system identity is stripped (and the seams tidied, so
edited reports are not identifiable), and repeats are shuffled in so inter-rater
agreement can be computed.

**Label audit** (§4.3). A solo build cannot supply a second reviewer. `make audit`
re-derives every label from the case package alone, without reading gold, and
reports disagreements. It currently agrees on 64/64 with all 12 abstention
reasons matched — but it is **not independent review**: the same author wrote the
labelling logic and the audit, so it catches internal inconsistency, not shared
misconception. That caveat ships inside `reports/label_audit.json`.

It has already earned its place, finding two real defects: a policy ordering bug
where extreme skew was checked after the variance branch, and a brittle
single-method label on a case where two methods were defensible.

## Testing

```bash
make test     # 160 tests
```

At least two numerical tests per method, checked against values that are
analytically derivable by hand or published — never against values this codebase
generated. That separation matters: the oracle files are a regression fixture
that catches numeric drift, and they cannot validate the library that produced
them.

The suite found four real defects during construction:

- `fit_regression` dropped the exposure column before reading it, so every count
  model with an offset was fitted without one.
- Breusch-Pagan alone missed heteroscedasticity of the form sd ∝ |x|; White's
  test is now reported alongside it.
- No driver passed `output_schema`, so on the live path every structured field
  would have come back empty while the API was billed.
- System B paraphrased tool output as user text, which breaks the
  `tool_use`/`tool_result` pairing the API requires.

The last two were invisible to the offline suite because the offline client
ignores both `messages` and `output_schema`. `tests/test_live_path.py` now
asserts the exact request the live client builds and guards both regressions.

## Licence and provenance

Code is original to this project. Datasets are CC BY 4.0 from the UCI Machine
Learning Repository and are cited above with their DOIs.
