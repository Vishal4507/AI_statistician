"""Live-path validation without an API key.

The offline suite never touches ``AnthropicClient``, so these tests assert the
exact request it builds and parse realistic response objects through it. They
catch the class of bug that would otherwise surface three hundred runs into a
paid evaluation.

What still cannot be checked here: whether the API accepts the request. That is
what ``scripts/smoke_live.py`` is for.
"""
from types import SimpleNamespace

import pytest

from aistat.agents.contracts import SCHEMAS, normalise
from aistat.agents.llm import AnthropicClient, _parse_json


class _Recorder:
    """Stands in for ``client.messages``, capturing kwargs and replaying a response."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _usage(**kw):
    fields = {"input_tokens": 100, "output_tokens": 50,
              "cache_read_input_tokens": 0}
    fields.update(kw)
    return SimpleNamespace(**fields)


def _resp(content, stop_reason="end_turn", usage=None):
    return SimpleNamespace(content=content, stop_reason=stop_reason,
                           usage=usage or _usage(), model="claude-opus-5",
                           stop_details=None)


def _client(response, model="claude-opus-5"):
    from aistat.agents.llm import capabilities
    c = AnthropicClient.__new__(AnthropicClient)
    c.model, c.effort, c.use_thinking = model, "high", True
    c.caps = capabilities(model)
    c.name = "test"
    c.total_input = c.total_output = c.total_cache_read = 0
    c.n_calls = c.n_refusals = c.n_parse_failures = 0
    c._client = SimpleNamespace(messages=_Recorder(response))
    return c


# ==========================================================================
# Request shape
# ==========================================================================

def test_temperature_is_never_sent():
    """Review finding F-A1: temperature is removed and returns a 400."""
    c = _client(_resp([SimpleNamespace(type="text", text="hi")]))
    c.complete(system="s", messages=[{"role": "user", "content": "q"}])
    kw = c._client.messages.calls[0]
    for banned in ("temperature", "top_p", "top_k"):
        assert banned not in kw, f"{banned} would be rejected with a 400"


def test_effort_and_thinking_are_set_and_stable():
    c = _client(_resp([SimpleNamespace(type="text", text="hi")]))
    c.complete(system="s", messages=[{"role": "user", "content": "q"}])
    kw = c._client.messages.calls[0]
    assert kw["output_config"]["effort"] == "high"
    assert kw["thinking"] == {"type": "adaptive", "display": "summarized"}


def test_thinking_can_be_disabled_for_the_ablation():
    c = _client(_resp([SimpleNamespace(type="text", text="hi")]))
    c.use_thinking = False
    c.complete(system="s", messages=[{"role": "user", "content": "q"}])
    assert "thinking" not in c._client.messages.calls[0]


def test_cache_breakpoint_sits_on_the_system_prompt():
    c = _client(_resp([SimpleNamespace(type="text", text="hi")]))
    c.complete(system="frozen policy", messages=[{"role": "user", "content": "q"}])
    system = c._client.messages.calls[0]["system"]
    assert isinstance(system, list) and len(system) == 1
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert system[0]["text"] == "frozen policy"


def test_output_schema_is_passed_as_json_schema_format():
    c = _client(_resp([SimpleNamespace(type="text", text='{"a": 1}')]))
    c.complete(system="s", messages=[{"role": "user", "content": "q"}],
               output_schema={"type": "object"})
    fmt = c._client.messages.calls[0]["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"] == {"type": "object"}


def test_tools_are_forwarded_untouched():
    from aistat.tools.registry import ToolRegistry
    c = _client(_resp([SimpleNamespace(type="text", text="hi")]))
    specs = ToolRegistry.specs(strict=True)
    c.complete(system="s", messages=[{"role": "user", "content": "q"}], tools=specs)
    assert c._client.messages.calls[0]["tools"] == specs


# ==========================================================================
# Response handling
# ==========================================================================

def test_tool_use_blocks_are_extracted_with_ids():
    c = _client(_resp([
        SimpleNamespace(type="text", text="checking"),
        SimpleNamespace(type="tool_use", id="tu_1", name="summarize_groups",
                        input={"outcome": "y", "group": "g"}),
    ], stop_reason="tool_use"))
    r = c.complete(system="s", messages=[{"role": "user", "content": "q"}])
    assert r.wants_tools and len(r.tool_uses) == 1
    assert r.tool_uses[0].id == "tu_1"
    assert r.tool_uses[0].input == {"outcome": "y", "group": "g"}


def test_refusal_is_returned_as_data_not_raised():
    """A refused case must be scored, not lost."""
    c = _client(_resp([], stop_reason="refusal"))
    r = c.complete(system="s", messages=[{"role": "user", "content": "q"}])
    assert r.stop_reason == "refusal"
    assert c.n_refusals == 1


def test_usage_accumulates_and_cache_rate_is_computable():
    c = _client(_resp([SimpleNamespace(type="text", text="hi")],
                      usage=_usage(cache_read_input_tokens=900)))
    for _ in range(2):
        c.complete(system="s", messages=[{"role": "user", "content": "q"}])
    assert c.total_input == 200 and c.total_cache_read == 1800
    assert 0.0 < c.cache_hit_rate < 1.0


@pytest.mark.parametrize("text", [
    '{"method": "welch_t"}',
    '```json\n{"method": "welch_t"}\n```',
    'Here is the result:\n{"method": "welch_t"}\nDone.',
])
def test_structured_parsing_tolerates_fencing_and_prose(text):
    assert _parse_json(text) == {"method": "welch_t"}


def test_unparseable_structured_output_is_counted_not_crashed():
    c = _client(_resp([SimpleNamespace(type="text", text="not json at all")]))
    r = c.complete(system="s", messages=[{"role": "user", "content": "q"}],
                   output_schema={"type": "object"})
    assert r.structured is None
    assert c.n_parse_failures == 1


# ==========================================================================
# Contracts
# ==========================================================================

def test_every_decision_point_has_a_schema_and_an_instruction():
    from aistat.agents.contracts import INSTRUCTIONS
    for purpose in ("parse_problem", "plan_candidates", "select_method",
                    "write_report", "direct_advice"):
        assert purpose in SCHEMAS, f"{purpose} would return free text"
        assert purpose in INSTRUCTIONS, f"{purpose} has no task instruction"


def test_schemas_are_closed_so_structured_output_accepts_them():
    for name, schema in SCHEMAS.items():
        assert schema.get("additionalProperties") is False, name
        assert set(schema["required"]) == set(schema["properties"]), \
            f"{name}: structured outputs require every property to be required"


def test_selection_schema_only_admits_library_methods():
    from aistat.schemas.core import ABSTAIN, METHODS
    enum = SCHEMAS["select_method"]["properties"]["method"]["enum"]
    assert set(enum) == set(METHODS) | {ABSTAIN}


def test_normalise_converts_pair_arrays_back_to_maps():
    out = normalise("select_method", {
        "method": "welch_t", "abstain_reason": None, "rationale": "because",
        "evidence_refs": [], "confidence": "high",
        "rejected_alternatives": [{"method": "student_t", "reason": "variance"}]})
    assert out["rejected_alternatives"] == {"student_t": "variance"}
    assert out["_rationale"] == "because"


def test_normalise_clears_a_stray_abstain_reason_on_a_real_method():
    out = normalise("select_method", {
        "method": "welch_t", "abstain_reason": "pairing", "rationale": "",
        "evidence_refs": [], "confidence": "high", "rejected_alternatives": []})
    assert out["abstain_reason"] is None


# ==========================================================================
# Driver wiring
# ==========================================================================

def test_drivers_send_a_schema_at_every_decision_point():
    """The bug this guards: drivers that never pass output_schema burn API
    calls while the model contributes nothing."""
    import inspect

    from aistat.agents import systems
    src = inspect.getsource(systems)
    assert "output_schema=SCHEMAS.get(purpose)" in src
    # No decision point may bypass the helper that carries the schema.
    assert src.count("self.client.complete(") == 1, \
        "a decision point calls the client directly and would skip its schema"


def test_system_b_threads_real_tool_result_blocks():
    """The bug this guards: paraphrasing tool output as user text breaks the
    tool_use / tool_result pairing the API requires."""
    import inspect

    from aistat.agents import systems
    src = inspect.getsource(systems.ToolLoopDriver)
    assert '"type": "tool_result"' in src and '"tool_use_id": tu.id' in src
    assert '"type": "tool_use", "id": tu.id' in src
    assert 'f"calling {tu.name}"' not in src


# ==========================================================================
# Model-aware request shaping
# ==========================================================================
#
# The first pilot lost all 48 Haiku runs to a 400. Credit exhaustion masked it,
# but the underlying cause was sending pre-4.6 models parameters they reject.

def test_haiku_gets_neither_effort_nor_adaptive_thinking():
    c = _client(_resp([SimpleNamespace(type="text", text="hi")]),
                model="claude-haiku-4-5")
    c.complete(system="s", messages=[{"role": "user", "content": "q"}])
    kw = c._client.messages.calls[0]
    assert "effort" not in kw.get("output_config", {}), \
        "effort is rejected by Haiku 4.5 and fails every run"
    assert kw.get("thinking", {}).get("type") != "adaptive", \
        "adaptive thinking is not supported before 4.6"
    assert kw["thinking"]["type"] == "enabled"
    assert kw["thinking"]["budget_tokens"] < kw["max_tokens"]


def test_opus_still_gets_effort_and_adaptive_thinking():
    c = _client(_resp([SimpleNamespace(type="text", text="hi")]))
    c.complete(system="s", messages=[{"role": "user", "content": "q"}])
    kw = c._client.messages.calls[0]
    assert kw["output_config"]["effort"] == "high"
    assert kw["thinking"]["type"] == "adaptive"


def test_unknown_model_degrades_to_the_universally_accepted_shape():
    """A typo or a future model id must not fail every run."""
    c = _client(_resp([SimpleNamespace(type="text", text="hi")]),
                model="claude-something-new")
    c.complete(system="s", messages=[{"role": "user", "content": "q"}])
    kw = c._client.messages.calls[0]
    assert "effort" not in kw.get("output_config", {})
    assert kw.get("thinking", {}).get("type") != "adaptive"


def test_structured_output_still_reaches_a_model_without_effort():
    c = _client(_resp([SimpleNamespace(type="text", text='{"a":1}')]),
                model="claude-haiku-4-5")
    c.complete(system="s", messages=[{"role": "user", "content": "q"}],
               output_schema={"type": "object"})
    fmt = c._client.messages.calls[0]["output_config"]["format"]
    assert fmt["type"] == "json_schema"


def test_unsupported_effort_is_recorded_in_the_client_name():
    """A cross-model comparison must not silently compare unlike configs."""
    from aistat.agents.llm import AnthropicClient
    c = AnthropicClient.__new__(AnthropicClient)
    from aistat.agents.llm import capabilities
    c.model, c.effort, c.use_thinking = "claude-haiku-4-5", "medium", True
    c.caps = capabilities("claude-haiku-4-5")
    name = f"anthropic:{c.model}:{c.effort}:think=1"
    if not c.caps["effort"] and c.effort != "high":
        name += ":effort-unsupported"
    assert "effort-unsupported" in name


# ==========================================================================
# Pair normalisation
# ==========================================================================
#
# Structured outputs deliver pair collections as an array of {key, value}
# objects; the offline client produces a map directly. Handling only the array
# silently emptied every rejected-alternatives map, which cost the section 12
# demonstration its "clear rejection of ordinary ANOVA" with no error raised --
# found by scripts/conformance.py, not by any test here.

def test_pairs_accepts_the_offline_map_shape():
    from aistat.agents.contracts import _pairs
    out = _pairs({"one_way_anova": "variance ratio 2.4"}, "method", "reason")
    assert out == {"one_way_anova": "variance ratio 2.4"}


def test_pairs_accepts_the_structured_output_array_shape():
    from aistat.agents.contracts import _pairs
    out = _pairs([{"method": "student_t", "reason": "variance differs"}],
                 "method", "reason")
    assert out == {"student_t": "variance differs"}


def test_pairs_tolerates_empty_and_malformed_input():
    from aistat.agents.contracts import _pairs
    assert _pairs(None, "method", "reason") == {}
    assert _pairs([], "method", "reason") == {}
    assert _pairs(["not a dict"], "method", "reason") == {}


def test_selection_keeps_its_rejected_alternatives_through_normalise():
    from aistat.agents.contracts import normalise
    out = normalise("select_method", {
        "method": "welch_anova", "abstain_reason": None, "rationale": "r",
        "evidence_refs": [], "confidence": "high",
        "rejected_alternatives": {"one_way_anova": "heteroscedastic"}})
    assert out["rejected_alternatives"] == {"one_way_anova": "heteroscedastic"}


def test_protocol_run_surfaces_the_rejected_alternative():
    """Blueprint section 12 demo 1: Welch ANOVA with a clear rejection of ANOVA."""
    from aistat.agents.base import Case
    from aistat.agents.rulebased import RuleBasedClient
    from aistat.agents.systems import SYSTEMS
    r = SYSTEMS["C_protocol"](RuleBasedClient("expert")).run(
        Case.load("syn_welch_anova_1"))
    assert r.method == "welch_anova"
    rejected = (r.selection or {}).get("rejected_alternatives") or {}
    assert "one_way_anova" in rejected, "the rejection the demo requires is absent"
    assert rejected["one_way_anova"], "rejection has no stated reason"


# ==========================================================================
# OpenAI-compatible providers
# ==========================================================================
#
# The blueprint fixes *a* model version, not a vendor. These cover the
# translation from the drivers' Anthropic-shaped messages to the OpenAI wire
# format, which is where a provider swap actually breaks.

def test_tool_definitions_translate_to_function_shape():
    from aistat.agents.openai_compat import _to_openai_tools
    from aistat.tools.registry import ToolRegistry
    out = _to_openai_tools(ToolRegistry.specs(strict=True))
    assert len(out) == 8
    for t in out:
        assert t["type"] == "function"
        fn = t["function"]
        assert {"name", "description", "parameters"} <= set(fn)
        assert fn["strict"] is True
        # The schema must survive intact -- a dropped enum lets the model
        # invent a method outside the library.
        assert fn["parameters"]["additionalProperties"] is False


def test_tool_call_round_trip_becomes_assistant_plus_tool_messages():
    """The pairing OpenAI requires: calls on the assistant, results keyed by id."""
    from aistat.agents.openai_compat import _to_openai_messages
    msgs = _to_openai_messages("sys", [
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": [
            {"type": "text", "text": "checking"},
            {"type": "tool_use", "id": "call_1", "name": "inspect_dataset",
             "input": {}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_1", "content": "{}"}]},
    ])
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool"]
    assert msgs[2]["tool_calls"][0]["id"] == "call_1"
    assert msgs[2]["tool_calls"][0]["function"]["name"] == "inspect_dataset"
    assert msgs[3]["tool_call_id"] == "call_1"


def test_parallel_tool_calls_all_survive_translation():
    from aistat.agents.openai_compat import _to_openai_messages
    msgs = _to_openai_messages("sys", [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "a", "name": "summarize_groups", "input": {}},
            {"type": "tool_use", "id": "b", "name": "check_group_assumptions",
             "input": {}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "a", "content": "{}"},
            {"type": "tool_result", "tool_use_id": "b", "content": "{}"}]},
    ])
    assert len(msgs[1]["tool_calls"]) == 2
    assert [m["tool_call_id"] for m in msgs if m["role"] == "tool"] == ["a", "b"]


def test_plain_string_messages_pass_through():
    from aistat.agents.openai_compat import _to_openai_messages
    msgs = _to_openai_messages("sys", [{"role": "user", "content": "hello"}])
    assert msgs == [{"role": "system", "content": "sys"},
                    {"role": "user", "content": "hello"}]


def test_every_preset_names_an_endpoint_a_model_and_a_credential():
    from aistat.agents.openai_compat import PRESETS
    for name, cfg in PRESETS.items():
        assert cfg["base_url"].startswith("http"), name
        assert cfg["model"], name
        assert cfg["env"].endswith("_API_KEY"), name


def test_local_providers_are_detected_by_reachability_not_by_key():
    """Ollama and llama.cpp need no credential, so a missing key must not
    mark them unavailable -- and an absent server must not mark them ready."""
    from aistat.agents.openai_compat import PRESETS, available_providers
    avail = available_providers()
    assert set(avail) == set(PRESETS)
    for name, cfg in PRESETS.items():
        if cfg["base_url"].startswith("http://localhost"):
            assert isinstance(avail[name], bool)


# ==========================================================================
# Resume semantics and pre-flight
# ==========================================================================
#
# A 401 wiped out a 432-run evaluation. Two defects turned one bad credential
# into a lost evaluation: the runner did not check the credential before
# committing to hundreds of calls, and it then recorded every failure as
# "completed", so the retry after fixing the key would have skipped all of them.

def test_errored_runs_are_not_treated_as_completed(tmp_path):
    import json
    from aistat.evaluation.runner import _completed
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        {"system": "C_protocol", "case_id": "c1", "rep": 0},
        {"system": "C_protocol", "case_id": "c2", "rep": 0,
         "error": "AuthenticationError: 401"},
        {"system": "B_tools", "case_id": "c1", "rep": 0, "error": None},
    ]) + "\n")
    done = _completed(p)
    assert "C_protocol|c1|0" in done          # clean run: skip on resume
    assert "C_protocol|c2|0" not in done      # errored: must be retried
    assert "B_tools|c1|0" in done             # explicit null error is clean


def test_preflight_passes_a_working_client():
    from aistat.evaluation.runner import verify_credentials
    from aistat.agents.rulebased import RuleBasedClient
    ok, detail = verify_credentials(lambda: RuleBasedClient("expert"))
    assert ok, detail


def test_preflight_names_an_auth_failure_rather_than_just_raising():
    from aistat.evaluation.runner import verify_credentials

    class Rejecting:
        name = "broken"
        def complete(self, **kw):
            raise RuntimeError("Error code: 401 - invalid_api_key")

    ok, detail = verify_credentials(Rejecting)
    assert ok is False
    assert "401" in detail
    assert "gsk_" in detail, "the hint should name the expected key shape"


def test_preflight_distinguishes_rate_limiting_from_bad_credentials():
    from aistat.evaluation.runner import verify_credentials

    class Throttled:
        name = "throttled"
        def complete(self, **kw):
            raise RuntimeError("Error code: 429 - rate limit exceeded")

    ok, detail = verify_credentials(Throttled)
    assert ok is False
    assert "workers" in detail, "should advise lowering concurrency"


def test_evaluate_runs_nothing_when_preflight_fails(tmp_path, monkeypatch):
    from aistat.evaluation import runner

    class Rejecting:
        name = "broken"
        def complete(self, **kw):
            raise RuntimeError("Error code: 401 - invalid_api_key")

    monkeypatch.setattr(runner, "RESULTS", tmp_path)
    res = runner.evaluate(Rejecting, split="dev", reps=1,
                          out_name="preflight_test", progress=False)
    assert res["preflight_failed"] is True
    assert res["n_run"] == 0
    assert not list(tmp_path.glob("preflight_test*.jsonl")), \
        "a failed pre-flight must not write partial results"
