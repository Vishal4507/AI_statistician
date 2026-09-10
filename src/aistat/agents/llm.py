"""LLM client abstraction.

One protocol, two implementations:

``AnthropicClient``  the live path.
``RuleBasedClient``  a deterministic offline stand-in that implements the same
                     protocol by executing the decision policy in Python.

The offline client exists so the whole harness -- drivers, scorers, bootstrap,
demo -- is runnable and testable without an API key, and so the study has two
reference points: a policy ceiling (what perfect routing scores) and a naive
floor.  It is NOT a system under test; ``systems.py`` never lists it as an arm.

Determinism note (review finding F-A1): ``temperature`` is removed on current
Claude models and returns a 400 if sent.  Determinism is controlled by pinning
the model id, the effort level and the frozen prompt hash, and by measuring the
residual variance across repetitions.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "high"

# Model capability map.
#
# Not every model accepts the same request shape, and sending an unsupported
# parameter is a 400 rather than a silent ignore.  Pre-4.6 models reject
# `output_config.effort` and do not support adaptive thinking -- they use the
# older fixed `budget_tokens` form.  Getting this wrong fails every run for the
# model, which is exactly what happened to Haiku in the first pilot.
MODEL_CAPS: dict[str, dict] = {
    "claude-opus-5":     {"effort": True,  "adaptive_thinking": True},
    "claude-fable-5":    {"effort": True,  "adaptive_thinking": True},
    "claude-opus-4-8":   {"effort": True,  "adaptive_thinking": True},
    "claude-opus-4-7":   {"effort": True,  "adaptive_thinking": True},
    "claude-opus-4-6":   {"effort": True,  "adaptive_thinking": True},
    "claude-sonnet-5":   {"effort": True,  "adaptive_thinking": True},
    "claude-sonnet-4-6": {"effort": True,  "adaptive_thinking": True},
    # Pre-4.6: no effort parameter, no adaptive thinking.
    "claude-haiku-4-5":  {"effort": False, "adaptive_thinking": False,
                          "thinking_budget": 4000},
}


def capabilities(model: str) -> dict:
    """Capabilities for a model, defaulting to the conservative pre-4.6 shape.

    An unknown model id is assumed NOT to support the newer parameters, so a
    typo or a future id degrades to a request every model accepts rather than
    failing every run with a 400.
    """
    return MODEL_CAPS.get(model, {"effort": False, "adaptive_thinking": False,
                                  "thinking_budget": 4000})


@dataclass
class ToolUse:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    text: str = ""
    tool_uses: list[ToolUse] = field(default_factory=list)
    structured: dict | None = None
    thinking: str = ""
    stop_reason: str = "end_turn"
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    model: str = ""

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_uses)


class LLMClient(Protocol):
    name: str

    def complete(self, *, system: str, messages: list[dict],
                 tools: list[dict] | None = None,
                 output_schema: dict | None = None,
                 purpose: str = "", context: Any = None,
                 max_tokens: int = 8000) -> LLMResponse: ...


# ==========================================================================
# Live client
# ==========================================================================


class AnthropicClient:
    """Live Claude client.

    Caching (review section 05): one breakpoint after the tool definitions.
    Nothing volatile may precede it -- no case id, no timestamp -- or every
    request misses the cache.  Verify with ``cache_read_tokens``.
    """

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT,
                 thinking: bool = True, api_key: str | None = None) -> None:
        import anthropic

        self.model = model
        self.effort = effort
        self.use_thinking = thinking
        self.caps = capabilities(model)
        self.name = f"anthropic:{model}:{effort}:think={int(thinking)}"
        if not self.caps["effort"] and effort != DEFAULT_EFFORT:
            # Recorded rather than raised: the run manifest must show that the
            # requested effort was not applied, or a cross-model comparison
            # would silently compare unlike configurations.
            self.name += ":effort-unsupported"
        # Explicit timeout and retry budget, matching the OpenAI-compatible
        # client.  A held-out evaluation is 288 sequential-ish calls behind a
        # thread pool: one request that hangs on the SDK default holds a worker
        # for ten minutes, and a rate-limit burst with too few retries turns
        # recoverable 429s into permanent error rows in the results.
        self._client = anthropic.Anthropic(
            api_key=api_key, max_retries=8, timeout=300.0) if api_key \
            else anthropic.Anthropic(max_retries=8, timeout=300.0)
        self.total_input = self.total_output = self.total_cache_read = 0
        self.n_calls = self.n_refusals = self.n_parse_failures = 0

    def complete(self, *, system: str, messages: list[dict],
                 tools: list[dict] | None = None,
                 output_schema: dict | None = None,
                 purpose: str = "", context: Any = None,
                 max_tokens: int = 8000) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            # Cache breakpoint on the frozen system prompt.
            "system": [{"type": "text", "text": system,
                        "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
        }

        output_config: dict[str, Any] = {}
        if self.caps["effort"]:
            output_config["effort"] = self.effort
        if output_schema:
            output_config["format"] = {"type": "json_schema",
                                       "schema": output_schema}
        if output_config:
            kwargs["output_config"] = output_config

        if self.use_thinking:
            if self.caps["adaptive_thinking"]:
                kwargs["thinking"] = {"type": "adaptive", "display": "summarized"}
            else:
                budget = self.caps.get("thinking_budget", 4000)
                # budget_tokens must be below max_tokens on the older form.
                if budget < max_tokens:
                    kwargs["thinking"] = {"type": "enabled",
                                          "budget_tokens": budget}

        if tools:
            kwargs["tools"] = tools

        resp = self._client.messages.create(**kwargs)
        self.n_calls += 1

        # A safety decline arrives as HTTP 200 with stop_reason "refusal", so it
        # must be checked before the content is read.  Treated as a run-level
        # datum rather than an exception: a refused case is scored, not dropped.
        if resp.stop_reason == "refusal":
            details = getattr(resp, "stop_details", None)
            self.n_refusals += 1
            return LLMResponse(
                text="", structured=None, stop_reason="refusal",
                thinking=f"refused: {getattr(details, 'category', None)}",
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
                model=resp.model)

        text, thinking, tool_uses = "", "", []
        for block in resp.content:
            if block.type == "text":
                text += block.text
            elif block.type == "thinking":
                thinking += getattr(block, "thinking", "") or ""
            elif block.type == "tool_use":
                tool_uses.append(ToolUse(block.id, block.name, dict(block.input)))

        structured = None
        if output_schema and text.strip():
            structured = _parse_json(text)
            if structured is None:
                self.n_parse_failures += 1

        u = resp.usage
        self.total_input += u.input_tokens
        self.total_output += u.output_tokens
        self.total_cache_read += getattr(u, "cache_read_input_tokens", 0) or 0

        return LLMResponse(
            text=text, tool_uses=tool_uses, structured=structured,
            thinking=thinking, stop_reason=resp.stop_reason,
            input_tokens=u.input_tokens, output_tokens=u.output_tokens,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            model=resp.model,
        )

    def raw_messages(self) -> Any:
        return self._client.messages

    @property
    def cache_hit_rate(self) -> float:
        """Share of input tokens served from cache.

        Zero across repeated calls means something volatile leaked into the
        prefix and the run is costing roughly three times what it should.
        """
        total = self.total_input + self.total_cache_read
        return self.total_cache_read / total if total else 0.0


def _parse_json(text: str) -> dict | None:
    """Parse a structured response, tolerating a fenced or prefixed payload."""
    t = text.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    if "```" in t:                       # fenced block
        seg = t.split("```")[1]
        seg = seg[4:] if seg.startswith("json") else seg
        try:
            return json.loads(seg.strip())
        except json.JSONDecodeError:
            pass
    start, end = t.find("{"), t.rfind("}")
    if 0 <= start < end:                 # prose around a JSON object
        try:
            return json.loads(t[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def api_key_available() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    from pathlib import Path
    return (Path.home() / ".config" / "anthropic").exists()
