"""Claude via the official Anthropic SDK, using structured outputs (`messages.parse`).

Prompt caching (LLM-06): with `prompt_caching` on (the default, `READINESS_LLM_PROMPT_CACHING`), the system
prompt is sent as one text block marked `cache_control: {"type": "ephemeral"}`. The system prompt is the static
part of every judge request (instructions, untrusted-data preamble, check list; never document text), so the
provider can serve it from its cache on later calls that share it. The cache entry lives in Anthropic's
infrastructure for about five minutes after its last use (the default TTL), which the provider checklist must
take into account; document text sits in the user turn, after the cache breakpoint, and is never cached. The
API reports cache writes and reads separately from `input_tokens`; both are kept in `LLMUsage`."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from readiness.models import LLMUsage

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-opus-5-5"


class AnthropicLLM:
    name = "anthropic"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        max_tokens: int = 16000,
        prompt_caching: bool = True,
    ):
        import anthropic  # lazy: optional dependency

        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.prompt_caching = prompt_caching
        self.last_usage: LLMUsage | None = None

    def _system_param(self, system: str) -> str | list[dict[str, Any]]:
        if not self.prompt_caching:
            return system
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    def generate_structured(self, system: str, prompt: str, schema: type[T]) -> T:
        response = self._client.messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._system_param(system),
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            in_tok = int(getattr(usage, "input_tokens", 0) or 0)
            out_tok = int(getattr(usage, "output_tokens", 0) or 0)
            cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
            cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
            self.last_usage = LLMUsage(
                provider=self.name,
                model=self.model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                total_tokens=in_tok + out_tok + cache_write + cache_read,
                cache_creation_input_tokens=cache_write,
                cache_read_input_tokens=cache_read,
            )
        if response.stop_reason == "refusal":
            raise RuntimeError("Model declined the request (stop_reason=refusal)")
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError("Model returned no parseable structured output")
        return parsed
