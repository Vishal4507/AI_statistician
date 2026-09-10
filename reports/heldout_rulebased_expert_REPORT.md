# AI Statistician — results

Generated 2026-09-10 14:35 UTC from
`results/heldout_rulebased_expert_scores.jsonl`. Regenerate with `make analyze`.

> **This is a calibration run, not an experiment.**
> The client is the deterministic offline policy, not an LLM. The
> `expert` policy is the same policy that derived the gold labels,
> so System C's score here is **circular by construction** — it is a
> label-coherence check and a harness validation, and it says nothing
> about LLM performance. Run `make eval-live` for the real experiment.

> The informative offline number is the naive-policy floor: inside the
> *same* state machine, a policy that ignores the design card scores
> far lower with zero abstention recall. The architecture alone is not
> what produces the uplift; the decision policy inside it is.

## Run configuration

| | |
|---|---|
| Client | `rulebased:expert` |
| Split | heldout (48 cases) |
| Repetitions | 3 |
| Total runs | 432 |
| Prompt hash | `7ba9f7108937e6f9` |
| Git commit | `907dabe24f57` |
| Determinism controls | pinned model id, fixed effort, frozen prompt hash, n repetitions |
| Library versions | numpy 1.26.3, pandas 2.1.4, scipy 1.13.1, statsmodels 0.14.2 |

`temperature` is not among the controls because it is removed on current Claude
models and returns a 400 if sent. See `docs/DEVIATIONS.md` §1.

## Success targets (blueprint §1)

| Measure | Target | Observed | Verdict |
|---|---|---|---|
| Method-selection accuracy | ≥ 85% | 100.0% | met |
| Unsafe-selection rate | ≈ 0 | 0.0% | met |
| Numerical fidelity | ≥ 98% | guaranteed by construction | see below |
| Unsupported inference rate | ≤ 5% | 0.0% | met |
| Protocol uplift over B | ≥ 10 pts | +50.0% [+35.4%, +64.6%] | met |

**On numerical fidelity.** For System C this is an architectural guarantee, not
an observation: the report schema rejects raw numeric literals and every value
is substituted from a recorded tool result, so there is no path to fabrication.
The empirical counterpart is the provenance rejection count —
0 across
144 runs. Fidelity remains an empirical
metric for Systems A and B, where nothing is enforced.

## System summary

| System | Runs | Selection accuracy | CI low | CI high | Abstention recall | Unsafe rate | Assumption coverage | Tool calls | LLM calls |
|---|---|---|---|---|---|---|---|---|---|
| A. Direct LLM | 144 | 0.562 | 0.481 | 0.641 | 0.000 | 0.188 | 0.607 | 2.17 | 1.00 |
| B. LLM with tools | 144 | 0.500 | 0.419 | 0.581 | 0.000 | 0.188 | 0.693 | 2.71 | 3.71 |
| C. Structured agent | 144 | 1.000 | 0.974 | 1.000 | 1.000 | 0.000 | 0.807 | 2.71 | 4.00 |

Accuracy intervals are Wilson intervals on the run-level counts.

## Risk–coverage

Coverage is the share of cases a system chose to answer; selective accuracy is
accuracy among those. This is the addition from review finding F-A3 — it
separates a system that abstains *correctly* from one that simply answers less.

| System | Coverage | Selective accuracy | Accuracy on supported | Abstention recall | Unsafe rate | Over-abstention |
|---|---|---|---|---|---|---|
| A. Direct LLM | 1.000 | 0.562 | 0.692 | 0.000 | 0.188 | 0.000 |
| B. LLM with tools | 1.000 | 0.500 | 0.615 | 0.000 | 0.188 | 0.000 |
| C. Structured agent | 0.812 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 |

Abstention recall for System C is 100.0% over 27 abstention runs
(Wilson interval 0.875 to
1.000).

## Paired comparisons

Per-case majority decision across 3 repetitions, then a case-level
bootstrap on the paired difference and an exact McNemar test.

| A | B | Cases | Acc A | Acc B | Uplift (B−A) | CI low | CI high | McNemar p |
|---|---|---|---|---|---|---|---|---|
| A_direct | B_tools | 48 | 0.562 | 0.500 | -0.062 | -0.146 | 0.021 | 0.3750 |
| A_direct | C_protocol | 48 | 0.562 | 1.000 | 0.438 | 0.292 | 0.583 | 0.0000 |
| B_tools | C_protocol | 48 | 0.500 | 1.000 | 0.500 | 0.354 | 0.646 | 0.0000 |

The comparison that answers the research question is **B vs C**: both have the
same tools and the same report schema, and differ only in whether an ordered
decision protocol governs their use. Observed uplift +50.0%
[+35.4%, +64.6%], McNemar p = 0.0000.

## Failure taxonomy (blueprint §8.4)

| System | Stage | Runs |
|---|---|---|
| A. Direct LLM | diagnostic_reasoning | 36 |
| A. Direct LLM | design_validation | 27 |
| B. LLM with tools | diagnostic_reasoning | 45 |
| B. LLM with tools | design_validation | 27 |

## Run-to-run stability

Mean repetition agreement 1.000;
unanimous on 100.0% of cases. Because
`temperature` no longer exists as a control, this is a *measurement* of residual
provider variance rather than a confirmation of determinism.

## Reproducing this

```bash
make benchmark && make validate && make test
make eval && make analyze
python scripts/write_report.py --name heldout_rulebased_expert
```

Every table above is derived from `results/heldout_rulebased_expert_scores.jsonl`. Deviations
from the blueprint are documented in `docs/DEVIATIONS.md`.
