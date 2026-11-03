"""Provider adapters against fake SDK clients (never a live account): request shape and usage accounting.

The SDKs are optional extras and not installed in CI, so the adapters are built without `__init__` and
given a fake client."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from readiness.adapters.llm.anthropic_llm import AnthropicLLM
from readiness.adapters.llm.gemini import GeminiLLM
from readiness.scoring.engine import JudgeBatch


class _FakeMessages:
    def __init__(self, usage: SimpleNamespace, stop_reason: str = "end_turn"):
        self.kwargs: dict = {}
        self._usage, self._stop = usage, stop_reason

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(usage=self._usage, stop_reason=self._stop, parsed_output=JudgeBatch(verdicts=[]))


def _anthropic(prompt_caching: bool, usage: SimpleNamespace, stop_reason: str = "end_turn") -> AnthropicLLM:
    llm = AnthropicLLM.__new__(AnthropicLLM)
    llm._client = SimpleNamespace(messages=_FakeMessages(usage, stop_reason))
    llm.model, llm.max_tokens, llm.prompt_caching, llm.last_usage = "claude-test", 100, prompt_caching, None
    return llm


USAGE = SimpleNamespace(input_tokens=120, output_tokens=30, cache_creation_input_tokens=400, cache_read_input_tokens=0)


def test_anthropic_marks_system_block_cacheable_and_records_cache_usage():
    llm = _anthropic(True, USAGE)
    out = llm.generate_structured("SYSTEM", "prompt", JudgeBatch)
    assert isinstance(out, JudgeBatch)
    sent = llm._client.messages.kwargs
    assert sent["system"] == [{"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}]
    assert sent["messages"] == [{"role": "user", "content": "prompt"}] and sent["output_format"] is JudgeBatch
    assert sent["model"] == "claude-test" and sent["max_tokens"] == 100
    u = llm.last_usage
    assert u is not None and (u.input_tokens, u.output_tokens) == (120, 30)
    assert (u.cache_creation_input_tokens, u.cache_read_input_tokens) == (400, 0) and u.total_tokens == 550


def test_anthropic_caching_off_sends_plain_system_string():
    llm = _anthropic(False, SimpleNamespace(input_tokens=10, output_tokens=5))
    llm.generate_structured("SYSTEM", "prompt", JudgeBatch)
    assert llm._client.messages.kwargs["system"] == "SYSTEM"
    assert llm.last_usage is not None and llm.last_usage.cache_creation_input_tokens == 0


def test_anthropic_refusal_raises():
    with pytest.raises(RuntimeError, match="refusal"):
        _anthropic(True, USAGE, stop_reason="refusal").generate_structured("s", "p", JudgeBatch)


def test_gemini_records_cached_content_tokens():
    llm = GeminiLLM.__new__(GeminiLLM)
    meta = SimpleNamespace(prompt_token_count=200, candidates_token_count=20, total_token_count=220)
    meta.cached_content_token_count = 150
    resp = SimpleNamespace(usage_metadata=meta, parsed=JudgeBatch(verdicts=[]), text="{}")
    sent: dict = {}

    def generate_content(**kwargs):
        sent.update(kwargs)
        return resp

    llm._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    llm.model, llm.last_usage = "gemini-test", None
    assert isinstance(llm.generate_structured("SYSTEM", "prompt", JudgeBatch), JudgeBatch)
    assert sent["config"]["system_instruction"] == "SYSTEM" and sent["contents"] == "prompt"
    u = llm.last_usage
    assert u is not None and u.input_tokens == 200 and u.cache_read_input_tokens == 150 and u.total_tokens == 220
