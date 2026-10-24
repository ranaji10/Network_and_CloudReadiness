"""Claude via the official Anthropic SDK, using structured outputs (`messages.parse`)."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from readiness.models import LLMUsage

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-opus-5-5"


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None, max_tokens: int = 16000):
        import anthropic  # lazy: optional dependency

        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.last_usage: LLMUsage | None = None

    def generate_structured(self, system: str, prompt: str, schema: type[T]) -> T:
        response = self._client.messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            in_tok = int(getattr(usage, "input_tokens", 0) or 0)
            out_tok = int(getattr(usage, "output_tokens", 0) or 0)
            self.last_usage = LLMUsage(
                provider=self.name,
                model=self.model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                total_tokens=in_tok + out_tok,
            )
        if response.stop_reason == "refusal":
            raise RuntimeError("Model declined the request (stop_reason=refusal)")
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError("Model returned no parseable structured output")
        return parsed
