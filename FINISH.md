# Finishing this project

State as of the last verification: **13 of 15 blueprint requirements met, 0 failing,
2 blocked.** Both blocks are the same single thing — the live held-out evaluation.

Verify this yourself at any time:

```bash
make conformance      # asserts every section 12 requirement against the artefacts
```

---

## 1. What is already done

| | |
|---|---|
| System | 14 methods, 5 diagnostics, 3 system variants over one shared core |
| Benchmark | 64 validated cases, 52 supported + 12 abstention, 16 dev / 48 held out |
| Tests | 189 passing, including numerical checks against published values |
| Offline study | 432 runs at two policy-competence levels, fully powered |
| Live preliminary | 44 clean Claude runs on dev: uplift +0.538, McNemar p = 0.0156 |
| Figures | 4, generated from the logs |
| Site | <https://ai-statistician.netlify.app> |
| §8.3 | Blinded round run, failed reliability, reported with diagnosis |
| Report | `docs/CAPSTONE_REPORT.md`, regenerates from logs |

---

## 2. The one thing left

A held-out evaluation against a real model: 48 cases × 3 systems × N repetitions.
Everything around it exists — frozen prompts, resumable runner, budget guard,
credential pre-flight. Only inference capacity is missing.

### Four routes, all tested

| Route | Time | Cost | Command |
|---|---|---|---|
| **Ollama, local** | ~8 h (1 rep) | free | see 2a |
| **Groq free tier** | ~11 days | free | see 2b |
| **Claude Haiku 4.5** | ~1 h | ~$10 | see 2c |
| **Claude Opus 5** | ~1 h | ~$34 | see 2c |

Measured on the development machine: Intel i7-1068NG7, no GPU offload, 26 tokens/s
locally; Groq free tier caps at 200,000 tokens/day against ~2.2M needed for 432 runs.

### 2a. Ollama — free, unlimited, slow

Already installed at `~/.local/bin/ollama` with `qwen2.5:7b` pulled.

```bash
export PATH="$HOME/.local/bin:$PATH"
export DYLD_LIBRARY_PATH="$HOME/.local/bin:$DYLD_LIBRARY_PATH"
ollama serve &                                  # leave running

cd ~/ai-statistician
make check-provider PROVIDER=ollama             # confirm it responds
python3 scripts/run_evaluation.py --client ollama --split heldout --reps 1 --workers 1
```

Roughly 8 hours for 144 runs. Safe to interrupt — rerun the same command and it
resumes; only clean runs are skipped.

### 2b. Groq — free, but rationed

`GROQ_API_KEY` goes in `.env` (see `.env.example`). Free key from
<https://console.groq.com/keys>.

```bash
make check-provider PROVIDER=groq
make eval-free PROVIDER=groq        # run once a day until complete
```

The daily cap will stop it partway; rerun tomorrow and it continues.

### 2c. Claude — fastest

```bash
# ANTHROPIC_API_KEY in .env
make smoke                          # validates the live path, a few cents
make eval-live                      # 432 runs, ~$34 on Opus 5
# or, cheaper:
python3 scripts/run_evaluation.py --client anthropic --model claude-haiku-4-5 \
    --split heldout --reps 3 --workers 4
```

---

## 3. After the run completes

```bash
make analyze                        # rebuild every result table
make capstone                       # regenerate the report with the new results
make site && make artifact          # refresh the explorer
make conformance                    # should now read 15 / 15
```

---

## 4. Optional: close §8.3 properly

The blinded interpretation round failed its reliability check (inter-rater
κ = −0.044). That failure **is** reported honestly in report §5.5, and the project
is complete with it. A second round would let you report the metric *as well*.

The instrument has been rebuilt since: the rubric now states its scope, three
calibration anchors are scored first with the answer revealed, and only the three
judged sections are shown.

```bash
make blind RUN=heldout_<your run name>     # builds packet + score.html
open reports/blinded/score.html            # calibrate, then score in 3 sittings
# export the CSV over reports/blinded/scores_blank.csv
make blind-ingest
make reliability                           # states plainly whether it is usable
```

Budget ~45 minutes, not 20. Two raters, three sittings each. If κ clears 0.4 the
metric is reportable; if not, §5.5 stands.

---

## 5. What must be disclosed in the write-up

These are already in `docs/DEVIATIONS.md` and the report, but do not quietly drop them:

- **The model used.** The blueprint fixes *a* model version, not a vendor. Whatever
  you run lands in the manifest; the claim is always "on model X".
- **Repetition count.** Fewer than 3 means run-to-run variance is not measured.
- **`temperature`.** Removed on current Claude models; present on OpenAI-compatible
  providers, where it is pinned to 0. A genuine difference between arms.
- **§8.3 reliability failure**, and that the anchors are author-adjudicated.
- **Four methods appear only in the held-out split** — no prompt was tuned against
  `one_way_anova`, `pearson`, `logistic` or `poisson`.
- **The label audit is not independent review** — same author wrote the labelling
  logic and the audit.

---

## 6. Reproducing from scratch

```bash
pip install -r requirements.txt
make data          # download and freeze the four UCI datasets
make all           # benchmark, validate, test, offline eval, tables, report
./scripts/verify_all.sh    # nine-stage verification
```

`make help` lists every target.

---

## 7. Defects found during construction

Worth mentioning in a viva — each was found by a check that was then kept:

1. `fit_regression` dropped the exposure column before reading it.
2. Breusch-Pagan alone missed heteroscedasticity of the form sd ∝ |x|; White's test
   is now reported alongside.
3. No driver passed `output_schema`, so the live path would have billed calls that
   changed nothing.
4. System B paraphrased tool output as text, breaking `tool_use`/`tool_result` pairing.
5. A reference containing spaces could not match the pattern, so the template was
   emitted verbatim into a finished-looking report.
6. `normalise` silently emptied `rejected_alternatives`, costing the §12 demo its
   "clear rejection of ordinary ANOVA".
7. Errored runs were recorded as complete, so a retry after a bad credential would
   have skipped all 432.
8. A no-argument tool carrying `"required": []` failed Groq's entire tool list.
