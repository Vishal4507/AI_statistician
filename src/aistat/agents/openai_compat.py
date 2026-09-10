"""OpenAI-compatible client, for running the evaluation on free inference.

The blueprint fixes *a* model version; it does not name one. Any provider works
scientifically, provided the model is pinned and disclosed -- and per review
finding F-A2 a weaker model is not a compromise but the more interesting arm,
since protocol uplift should be larger where internal reasoning is weaker.

One implementation covers every free option worth using, because they all speak
the OpenAI wire format:

    Groq        https://api.groq.com/openai/v1        free tier, fast
    OpenRouter  https://openrouter.ai/api/v1          has ":free" models
    Cerebras    https://api.cerebras.ai/v1            free tier
    Ollama      http://localhost:11434/v1             local, no key at all
    llama.cpp   http://localhost:8080/v1              local, no key at all

The drivers build Anthropic-shaped messages, so this client translates on the
way in. Provider differences belong here, not spread through the state machine.

Determinism note: unlike current Claude models, these accept `temperature`, so
it is pinned to 0. That is a genuine difference between the arms and belongs in
the write-up rather than being quietly ignored.
"""
from __future__ import annotations

import json
import os
from typing import Any

from aistat.agents.llm import LLMResponse, ToolUse

PRESETS: dict[str, dict[str, str]] = {
    "groq": {"base_url": "https://api.groq.com/openai/v1",
             "env": "GROQ_API_KEY", "model": "llama-3.3-70b-versatile"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",
                   "env": "OPENROUTER_API_KEY",
                   "model": "meta-llama/llama-3.3-70b-instruct:free"},
    "cerebras": {"base_url": "https://api.cerebras.ai/v1",
                 "env": "CEREBRAS_API_KEY", "model": "llama-3.3-70b"},
    "ollama": {"base_url": "http://localhost:11434/v1",
               "env": "OLLAMA_API_KEY", "model": "llama3.1:8b"},
    "llamacpp": {"base_url": "http://localhost:8080/v1",
                 "env": "LLAMACPP_API_KEY", "model": "local"},
}


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Anthropic tool definitions -> OpenAI function definitions."""
    out = []
    for t in tools:
        fn: dict[str, Any] = {"name": t["name"],
                              "description": t.get("description", ""),
                              "parameters": t["input_schema"]}
        if t.get("strict"):
            fn["strict"] = True
        out.append({"type": "function", "function": fn})
    return out


def _to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
    """Anthropic content blocks -> OpenAI messages.

    The drivers emit assistant turns carrying ``tool_use`` blocks and user turns
    carrying ``tool_result`` blocks. OpenAI puts tool calls on the assistant
    message and each result in its own ``tool`` message keyed by call id.
    """
    out: list[dict] = [{"role": "system", "content": system}]
    for m in messages:
        content = m.get("content")
        if isinstance(content, str):
            out.append({"role": m["role"], "content": content})
            continue

        if m["role"] == "assistant":
            text = "".join(b.get("text", "") for b in content
                           if b.get("type") == "text")
            calls = [{"id": b["id"], "type": "function",
                      "function": {"name": b["name"],
                                   "arguments": json.dumps(b.get("input", {}))}}
                     for b in content if b.get("type") == "tool_use"]
            msg: dict[str, Any] = {"role": "assistant",
                                   "content": text or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
        else:
            results = [b for b in content if b.get("type") == "tool_result"]
            if results:
                for b in results:
                    out.append({"role": "tool",
                                "tool_call_id": b["tool_use_id"],
                                "content": str(b.get("content", ""))})
            else:
                text = "".join(b.get("text", "") for b in content
                               if b.get("type") == "text")
                out.append({"role": "user", "content": text})
    return out


class OpenAICompatClient:
    """Implements the same protocol as AnthropicClient, over any OpenAI endpoint."""

    def __init__(self, provider: str = "groq", model: str | None = None,
                 base_url: str | None = None, api_key: str | None = None,
                 temperature: float = 0.0, json_strict: bool = True) -> None:
        from openai import OpenAI

        preset = PRESETS.get(provider, {})
        self.provider = provider
        self.base_url = base_url or preset.get("base_url")
        self.model = model or preset.get("model") or "unknown"
        self.temperature = temperature
        self.json_strict = json_strict
        if not self.base_url:
            raise ValueError(f"no base_url for provider {provider!r}; "
                             f"known: {sorted(PRESETS)}")

        key = (api_key or os.environ.get(preset.get("env", ""), "")
               or os.environ.get("OPENAI_API_KEY", "") or "not-needed")
        self._client = OpenAI(base_url=self.base_url, api_key=key,
                              max_retries=3, timeout=180.0)
        self.name = f"{provider}:{self.model}:temp={temperature}"
        self.total_input = self.total_output = self.total_cache_read = 0
        self.n_calls = self.n_refusals = self.n_parse_failures = 0

    # ----------------------------------------------------------------------

    def complete(self, *, system: str, messages: list[dict],
                 tools: list[dict] | None = None,
                 output_schema: dict | None = None,
                 purpose: str = "", context: Any = None,
                 max_tokens: int = 8000) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": _to_openai_messages(system, messages),
            "max_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if tools:
            kwargs["tools"] = _to_openai_tools(tools)
            kwargs["tool_choice"] = "auto"
        if output_schema:
            # Some free endpoints reject json_schema but accept json_object,
            # so fall back rather than failing the run.
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": purpose or "response",
                                "schema": output_schema, "strict": False},
            } if self.json_strict else {"type": "json_object"}

        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            if output_schema and self.json_strict and "json_schema" in str(exc):
                self.json_strict = False
                kwargs["response_format"] = {"type": "json_object"}
                resp = self._client.chat.completions.create(**kwargs)
            else:
                raise

        self.n_calls += 1
        choice = resp.choices[0]
        msg = choice.message
        text = msg.content or ""

        tool_uses = [
            ToolUse(tc.id, tc.function.name,
                    json.loads(tc.function.arguments or "{}"))
            for tc in (msg.tool_calls or [])
        ]

        structured = None
        if output_schema and text.strip():
            from aistat.agents.llm import _parse_json
            structured = _parse_json(text)
            if structured is None:
                self.n_parse_failures += 1

        u = getattr(resp, "usage", None)
        if u:
            self.total_input += getattr(u, "prompt_tokens", 0) or 0
            self.total_output += getattr(u, "completion_tokens", 0) or 0

        return LLMResponse(
            text=text, tool_uses=tool_uses, structured=structured,
            stop_reason="tool_use" if tool_uses else (choice.finish_reason or "end_turn"),
            input_tokens=getattr(u, "prompt_tokens", 0) if u else 0,
            output_tokens=getattr(u, "completion_tokens", 0) if u else 0,
            model=resp.model or self.model,
        )

    @property
    def cache_hit_rate(self) -> float:
        return 0.0     # these endpoints do not expose prompt caching


def available_providers() -> dict[str, bool]:
    """Which providers have a usable credential or a live local endpoint."""
    import urllib.request
    out = {}
    for name, cfg in PRESETS.items():
        if cfg["base_url"].startswith("http://localhost"):
            try:
                urllib.request.urlopen(cfg["base_url"].replace("/v1", ""), timeout=1.5)
                out[name] = True
            except Exception:
                out[name] = False
        else:
            out[name] = bool(os.environ.get(cfg["env"]))
    return out
