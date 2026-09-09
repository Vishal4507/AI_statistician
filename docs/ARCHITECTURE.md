# Architecture

## Shared core, three drivers

Everything except control flow is shared. This is what makes baseline fairness
*provable* rather than asserted: there is no code path on which System A or B
could have been disadvantaged, because they import the same objects.

```
driver_direct        driver_toolloop        driver_protocol
(System A)           (System B)             (System C)
     |                     |                       |
     +---------------------+-----------------------+
                           |
        ToolRegistry  .  ResultStore  .  FinalReport  .  TraceLog
        8 typed tools    provenance      no raw floats   JSONL, seq
```

## The state machine (System C)

```
 question + data + design card
            |
            v
   1  parse problem            -> AnalysisSpec
            |
            v
   2  validate design          -- hazards gate everything downstream
            |
            v
   3  enumerate candidates     -> CandidatePlan
            |
            v
   4  targeted diagnostics     -- only checks that could change the decision
            |
            v
   5  select or abstain        -> Selection
            |
            v
   6  execute                  -> AnalysisResult (registered in the store)
            |
            v
   7  revise at most once      -- e.g. Poisson -> negative binomial
            |
            v
   8  verify                   -- provenance, causal language, estimand
            |
            v
   9  render                   -- {{refs}} substituted; unknown ref fails
```

The model supplies semantic judgement at steps 1, 3, 4, 5 and 9. It can never
bypass step 2 or invent a value at step 9.

## Provenance

```python
store.register("r7.welch_t", payload)     # flattens to dotted scalar keys
# model writes:  "p = {{r7.welch_t.p_value}}"
store.render(text)                        # substitutes, or raises
```

`ProseBlock` rejects decimals, three-or-more-digit integers and scientific
notation in report prose, allowing only conventional constants (95, 0.05, 1.96,
2x2). The rejection is a schema error, so a run that tries to fabricate fails
loudly rather than producing a plausible report.

`store.unused_from(call_id)` surfaces values a tool computed that the report
never cited — how the verifier catches a diagnostic that was raised and ignored.

## Traces

Every state transition and tool call is appended with a monotonic sequence
number. Two payoffs beyond debugging:

- A run replays without touching the API, so changing the scorer costs nothing.
- `divergence_point(a, b)` finds where two repetitions of the same case first
  differ. The distribution of divergence points across the state machine says
  whether instability comes from problem parsing or from method selection — a
  sharper error analysis than the stage taxonomy alone.

## Tool surface

Five diagnostics (`inspect_dataset`, `summarize_groups`,
`check_group_assumptions`, `check_contingency`, `check_association`) and three
execution dispatchers covering the 14 methods, plus `verify_report`.

All definitions carry `strict: true`, which guarantees `tool_use.input`
validates and removes a class of harness parse failures that would otherwise be
misattributed to the "execution" stage of the error taxonomy.

There is no `run_python`. Unrestricted execution would let the model bypass the
method policy and make traces incomparable across systems.

## Live-path settings

| Setting | Value | Why |
|---|---|---|
| `temperature` | not sent | Removed on current models; 400 if sent |
| `thinking` | `{type: "adaptive", display: "summarized"}` | Identical across A/B/C or the comparison is confounded; `summarized` puts reasoning in the trace |
| `output_config.effort` | fixed, identical across arms | Another live confound if it varies |
| tool `strict` | `true` | Guarantees input validation |
| cache breakpoint | after the system prompt | All 48 cases share the prefix; nothing volatile may precede it |

Verify caching with `usage.cache_read_input_tokens` before the real run. If it
reads zero across repeated calls, something volatile leaked into the prefix and
you are paying roughly three times the expected cost.
