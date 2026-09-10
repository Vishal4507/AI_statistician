# Deviations from the blueprint

Eight documented departures. Four come from the implementation review; two were
forced by facts discovered during construction; two were forced by what the
held-out run itself revealed. Everything else follows the blueprint as written.

---

## 1. `temperature: 0` is not sent (blueprint §8.3)

**Blueprint**: "temperature 0 or the provider's lowest deterministic setting."

**Problem**: `temperature`, `top_p` and `top_k` are removed on Claude Opus 5,
Sonnet 5 and the 4.6–4.8 family. Sending any of them returns HTTP 400. The
clause is not stale, it is unimplementable — it fails on the first API call.

**What we do instead**: determinism is controlled by four things that exist —
a pinned model id (no date suffix), a fixed `output_config.effort`, a frozen
prompt hash recorded in every run manifest, and the repetitions the blueprint
already specifies. The reps are reframed: they no longer confirm determinism we
controlled for, they *measure* the variance that remains.

**Where**: `agents/llm.py`, `evaluation/runner.py::run_manifest`.

---

## 2. Abstention cases raised from 8 to 12 (blueprint §1, §3.2, §8.2)

**Blueprint**: 8 abstention cases in 64, with the target "at most 1 abstention
case assigned an in-scope method".

**Problem**: roughly 6 of those land in the held-out set. A threshold on a
denominator of six is not a measurement — one case flips the headline safety
claim, and no interval computed on it is worth printing. Recognising invalid
designs is the most interesting thing the system does and was the least measured
property in the plan.

**What we do instead**: 12 abstention cases (8 synthetic, 4 Seoul Bike), leaving
52 supported cases — still at least two per method. Abstention recall is
reported with a Wilson interval rather than as a count threshold, and
**selective accuracy** is added: accuracy among the cases a system chose to
answer, against its coverage. The risk–coverage curve costs no extra runs and is
the most informative safety result this design can produce.

**Where**: `benchmark/registry.py`, `evaluation/analysis.py::risk_coverage`.

---

## 3. Numeric fidelity is prevented, not verified (blueprint §5.2, §6 step 10)

**Blueprint**: `verify_report` checks each number in the finished draft against
tool output.

**Problem**: that is detection. It runs after the model has already committed
the number, and a plausible rounding defeats it.

**What we do instead**: every tool return is registered in a run-scoped
`ResultStore`; the report schema rejects raw numeric literals in prose; the
model emits `{{r7.welch_t.p_value}}` templates that are substituted at render
time; an unknown reference raises. The model has no path to writing a number.

**How to report this honestly** — this matters for the write-up:

- For System C, numerical fidelity is an **architectural guarantee**, not an
  empirical finding. Do not present 100% as a result; present the mechanism.
- For Systems A and B, nothing is enforced, so fidelity stays an **empirical
  metric** and the comparison is still meaningful.
- The empirical number for C is the **provenance rejection rate**: how often the
  model reached for a reference that did not exist and was blocked.

The provenance contract covers **decision prose as well as results**. Routing
rationales cite the diagnostics that drove them (`{{r2.check_group_assumptions.variance_ratio}}`),
not formatted values.

**Where**: `provenance/store.py`, `schemas/core.py::ProseBlock`,
`agents/policy.py::route`.

---

## 4. The verifier moved from week 4 to week 2 (blueprint §6 step 10, §9)

The provenance layer determines the final-report schema, and the schema
determines what all 432 runs produce. Discovering in week 4 that the schema
cannot carry references means re-running everything with one week left. The
store, the renderer and a minimal verifier are built alongside the tools; the
semantic checks (causal linting, estimand consistency, unaddressed diagnostics)
are the genuine week-4 work.

**Where**: `provenance/store.py` and `tools/verify.py` ship together with
`tools/execution.py`.

---

## 5. Not every method appears in both partitions (blueprint §3.2)

**Blueprint**: 16 development cases (12 synthetic + 4 public) **and** "each
method appears in both partitions."

**Problem**: those are arithmetically incompatible. Twelve synthetic development
slots cannot cover fourteen methods plus abstention.

**What we do instead**: keep the split sizes, which protect the held-out
estimate, and cover all seven *families* plus the hardest within-family contrasts
in development. Four methods — `one_way_anova`, `pearson`, `logistic`,
`poisson` — are held-out only.

**Consequence to disclose**: no prompt was ever tuned against those four. That
is a limitation, and incidentally a cleaner generalisation test.

**Where**: `benchmark/registry.py::DEV_SYNTHETIC`, `HELDOUT_ONLY_METHODS`.

---

## 6. Synthetic gold is derived from the realised sample (blueprint §4.3)

**Blueprint**: "A label is determined from the study design, estimand, variable
types, and controlled data-generating conditions."

**Problem found in construction**: a case generated with a requested variance
ratio of 3.0 realised 1.45 in its actual sample. Gold said `welch_t`; the data
said `student_t`. Deriving labels purely from requested parameters produces
labels the data contradicts.

**What we do instead**: split the derivation. **Design facts** (independence,
pairing, clustering, time order, randomisation) come from the generator
parameters, because they are properties of the design and are not subject to
sampling noise. **Distributional facts** (variance ratio, skew, dispersion) come
from the realised sample, because that is what a correct method choice must
respond to. Labels stay mechanically derived and stop disagreeing with their own
data.

**Where**: `benchmark/generators.py`.

---

## 7. A rejected report counts as a run, not a lost run (blueprint §8.3)

**Blueprint**: reports selection accuracy over completed runs, with failures
excluded as harness noise.

**Problem**: the held-out run made that distinction untenable. 51 of 288 runs
ended with an error, and none of them were harness noise. Every one had already
chosen a method and executed it; what failed was the write-up — prose carrying a
raw number no tool produced, or a `{{...}}` reference to a result the system
never computed. 43 of the 51 were System A, and 37 of the 51 had selected the
*correct* method.

Excluding them moves System A's apparent accuracy from 75.0% to 81.1%. That is
not a rounding difference: it deletes the baseline's worst behaviour from the
headline metric and flatters exactly the system whose ungrounded claims the
project exists to expose.

**What we do instead**: the population for selection metrics is every run that
reached a method decision. A run that never got that far — a 400 or a 401 —
carries no evidence about selection and is still excluded. The discriminator is
`chosen_method == "none"`, and it is not a guess: on the two development runs it
separates 16 `BadRequestError`s from 4 contract failures exactly. Report validity
is then promoted from a footnote to a reported metric in its own right, because
"chose correctly and could not say so without inventing a number" is a result.

**Where**: `evaluation/analysis.py::made_a_selection`, `::report_validity`,
`evaluation/liveness.py::produced_a_result`. Pinned by
`tests/test_conformance_guarantees.py`.

---

## 8. Repetition ties are broken by the earliest run (blueprint §8.3)

**Blueprint**: collapse repetitions to a per-case majority before the paired
test.

**Problem**: with two repetitions there is often no majority. The original
implementation resolved a 1–1 tie with `max(set(methods), key=methods.count)`,
and set iteration order depends on `PYTHONHASHSEED` — so the tie fell a
different way in every process. On the held-out run this alone moved McNemar's
p for A-versus-C between **0.016 and 0.125** across interpreter runs, on
identical data. The significance verdict changed with the seed.

**What we do instead**: repetitions are sorted by index and ties go to the
earliest repetition — deterministic, and it uses a real observation rather than
an arbitrary one. How often the rule was needed is reported rather than buried:
25 of 144 system-case cells on the held-out run, unevenly spread (System B 14,
System A 6, System C 5), which is itself a measure of run-to-run stability.

**Why it matters beyond this project**: a capstone whose conclusions change when
the reader re-runs the analysis has no conclusions. The regression is pinned by
`tests/test_analysis_determinism.py`, which runs the analysis in fresh
interpreters under three hash seeds and requires byte-identical output.

**Where**: `evaluation/analysis.py::majority_by_case`.

---

## Second-reviewer substitute (blueprint §4.3, §11)

The blueprint requires a second reviewer on all 64 labels, and defines the
week-1 gate as two reviewers agreeing on 14 of 16 development cases. A solo
build cannot meet that as written, and skipping it quietly would undermine every
accuracy number.

What is implemented instead:

1. **Most of the need is removed.** Construction-derived labels are not
   opinions — 48 of 64 follow mechanically from generator parameters and
   realised sample statistics.
2. **Labels are written once and not revisited.** Re-deriving a label after
   seeing model output is precisely the contamination the gate exists to prevent.
3. **The 16 public labels are checked against their data.** `validate_label`
   compares each proposed label to the realised diagnostics and reports
   contradictions. It caught one during construction: `pub_shoppers_3` was
   labelled `spearman`, but Pearson was 0.913 against Spearman 0.590 on a linear
   relationship. Corrected to `pearson`, with `spearman` in the accepted set
   because 232 high-leverage points make the choice genuinely arguable.

**Still required before the live run**: an independent labelling pass on the
held-out cases by a model that is not the system under test and not in the
harness, reporting the agreement rate and hand-adjudicating disagreements. This
is scheduled for week 2 and must be disclosed as a limitation — it is not human
double-review.

---

## Live path: what the offline suite cannot verify

The offline `RuleBasedClient` answers from `context` and ignores both `messages`
and `output_schema`. That makes the harness testable without a key, but it means
the offline suite cannot see two whole categories of defect. Both were present
and are now fixed:

1. **No driver passed `output_schema`.** On the live path every structured field
   would have parsed as `None`, so the state machine would have run to completion
   on fallbacks while the API was billed for calls that changed nothing.
2. **System B paraphrased tool output as user text.** The API pairs a
   `tool_result` with the `tool_use` that requested it, by id, in a single
   following user message. Splitting results across messages or rewriting them as
   prose breaks the pairing and silently trains the model out of parallel tool
   use.

`src/aistat/agents/contracts.py` now carries a closed JSON schema and a task
instruction for each of the five decision points, and `_ask()` in `systems.py` is
the single place either is assembled — `tests/test_live_path.py` asserts that no
decision point bypasses it.

**Still unverifiable offline**: whether the API accepts the request. That is what
`scripts/smoke_live.py` is for, and `make eval-live` runs it first.
