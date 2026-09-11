# Project status: complete

**All 15 blueprint requirements met, 0 failing, 0 blocked.**

`make conformance` reports 16 checks: the 15 the blueprint specifies, plus one
this project imposed on itself — that the counts quoted in these documents match
the artefacts they describe.

Verify that claim yourself, from the artefacts, in one command:

```bash
make conformance
```

It re-derives every §12 requirement and every definition-of-done item from the
files in this repository and prints PASS / FAIL / BLOCK per requirement. Nothing
in this document is asserted anywhere it is not also checked.

---

## 1. What exists

| | |
|---|---|
| System | 14 methods, 5 diagnostics, 3 system variants over one shared core |
| Benchmark | 64 validated cases — 52 supported, 12 abstention; 16 dev / 48 held out |
| Tests | 241 passing, including numerical checks against published values |
| Offline study | 432 runs at two policy-competence levels, fully powered |
| Live, development | 80 runs on Claude Opus 5 |
| **Live, held out** | **288 runs on Claude Haiku 4.5 — 48 cases × 3 systems × 2 reps** |
| Figures | 7, all generated from the logs |
| Site | <https://ai-statistician.netlify.app> |
| §8.3 | Blinded round run, failed its reliability check, reported with diagnosis |
| Report | `docs/CAPSTONE_REPORT.md`, regenerates from logs |

---

## 2. The held-out result

Every number below regenerates from `results/heldout_claude-haiku-4-5*.jsonl`.

### Method selection

| System | n | Accuracy | 95% CI (Wilson) | Abstention recall | Unsafe rate |
|---|---|---|---|---|---|
| A · Direct LLM | 96 | 0.750 | [0.655, 0.826] | 0.28 | 0.135 |
| B · LLM with tools | 96 | 0.667 | [0.568, 0.753] | 0.00 | 0.188 |
| C · Structured agent | 96 | 0.885 | [0.806, 0.935] | 0.78 | 0.042 |

### Paired comparisons, per-case majority over 48 cases

| Comparison | Uplift | Bootstrap 95% CI | McNemar p | Reading |
|---|---|---|---|---|
| **C over B** | **+0.250** | [+0.125, +0.396] | **0.0018** | the research question, answered |
| C over A | +0.125 | [+0.021, +0.250] | 0.0703 | direction only — not significant |
| B over A | −0.125 | [−0.250, +0.000] | 0.1094 | tools alone did not help |

**The claim the project set out to test holds.** An ordered protocol over the
same tools and the same report schema beats unstructured tool use by 25
percentage points, p = 0.0018. The blueprint's target was ≥10.

**Two things it does not establish**, both stated in the report rather than
left for a reader to notice. C over A does not clear 0.05 on 48 cases. And the
A-versus-B deficit, while pointing the wrong way for tool access, is not
significant either.

### Whether the report could be grounded

Selecting a method is half the task; the other half is saying what was found
without inventing any of it.

| System | Reports rejected | Valid-report rate | 95% CI |
|---|---|---|---|
| A · Direct LLM | 43 / 96 | 0.552 | [0.453, 0.648] |
| B · LLM with tools | 0 / 96 | 1.000 | [0.962, 1.000] |
| C · Structured agent | 8 / 96 | 0.917 | [0.844, 0.957] |

System A wrote an ungrounded number, or cited a diagnostic it never ran, in
nearly half its analyses. The provenance contract caught every one.

---

## 3. Two decisions that changed the numbers

Both are recorded in `docs/DEVIATIONS.md` (§7, §8) and pinned by tests. They are
here because they are the two places this project could most easily have
reported something false.

**A rejected report is a run, not a lost run.** 51 of 288 runs ended in an
error, and not one was infrastructure. Each had already chosen a method and
executed it; the write-up failed. 37 of the 51 had chosen *correctly*. Dropping
them — the obvious thing to do with a row marked `run_error` — moves System A
from 75.0% to 81.1% and deletes the baseline's worst behaviour from the headline.
Runs that never reached a decision, such as the Groq attempt's 432
authentication failures, are still excluded, because those carry no evidence.

**Repetition ties are broken deterministically.** With two repetitions a
disagreement has no majority. The tie was being resolved through `set` iteration
order, which depends on `PYTHONHASHSEED` — so McNemar's p for A-versus-C moved
between 0.016 and 0.125 across interpreter runs *on identical data*. Ties now go
to the earliest repetition. `tests/test_analysis_determinism.py` re-runs the
analysis in fresh interpreters under three hash seeds and requires identical
output.

---

## 4. Reproducing everything

```bash
make setup          # dependencies
make data           # fetch and checksum the four UCI datasets
make benchmark      # regenerate all 64 cases from the registry
make validate       # schema and leakage checks
make test           # 241 tests
make eval           # 432-run offline study, no API key needed
make analyze        # rebuild every table from the raw logs
make capstone       # regenerate the report and figures
make conformance    # assert all 15 requirements
```

Nothing above needs a network connection except `make data`.

To repeat the held-out evaluation against a live model:

```bash
cp .env.example .env        # add ANTHROPIC_API_KEY
make eval-live              # validates the live path before starting work
```

The runner is resumable and flushes every 25 runs, so an interruption costs one
batch rather than the whole evaluation. Re-running skips work already recorded.

Alternatives that need no hosted model:

```bash
make eval-free PROVIDER=ollama     # runs locally, no key required
make eval-free PROVIDER=groq       # free tier key
```

---

## 5. Packaging

```bash
make package        # builds the handoff zip
```

The packager reads every file it is about to add and refuses to build an archive
containing anything key-shaped, rather than relying on a deny-list to be
complete. `.env` is excluded by name as well.

---

## 6. Known limitations

These are in the report too; they are repeated here so that nothing in this
document reads as a stronger claim than the evidence supports.

- **The model is Claude Haiku 4.5**, not Opus 5. Every held-out claim is about
  that model. The runner accepts any model id; nothing here generalises to
  frontier models without re-running it.
- **Two repetitions, not three.** Run-to-run variance is estimated across two
  runs per cell — enough to expose gross instability, not enough to
  characterise the distribution.
- **No usable interpretation score.** The blinded round failed its reliability
  check (κ = −0.044). The instrument has been rebuilt and the diagnosis is in
  report §5.5; a second round needs two human raters and has not been run. The
  metric is withheld rather than reported unreliably.
- **No independent second reviewer** for the 16 public-data labels.
- **C over A is unresolved** at this sample size, as above.
