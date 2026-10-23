"""Claude via the official Anthropic SDK, using structured outputs (`messages.parse`)."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-opus-5-5"


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None, max_tokens: int = 16000):
        import anthropic  # lazy: optional dependency

        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens

    def generate_structured(self, system: str, prompt: str, schema: type[T]) -> T:
        response = self._client.messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Model declined the request (stop_reason=refusal)")
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError("Model returned no parseable structured output")
        return parsed
