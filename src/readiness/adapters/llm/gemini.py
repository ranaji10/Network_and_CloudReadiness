"""Gemini via the google-genai SDK. Works with Vertex AI (ADC, project + location) or an API key.

Model requests for the gemini-3 family must go to the `global` location (lesson carried over from the
V1.1 ADK code, see legacy/v1.1_adk).

Prompt caching (LLM-06): Gemini's explicit context caching needs a `cached_content` object created up front
with its own TTL and a model-dependent minimum size, and the judge's static prefix (instructions plus one
pillar's check list) is normally below that minimum, so it is not wired here; `READINESS_LLM_PROMPT_CACHING`
has no effect on this adapter. Implicit caching, where the model offers it, needs nothing from the caller and
shows up as `cached_content_token_count`, which is recorded as `cache_read_input_tokens`.
TODO(LLM): add explicit context caching once a prefix large enough to qualify exists (e.g. a shared control
catalogue in the system instruction)."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from readiness.models import LLMUsage

T = TypeVar("T", bound=BaseModel)

# Vertex AI retired the Gemini 2.5 family on 2026-10-20; pick a current id and override via READINESS_LLM_MODEL.
DEFAULT_MODEL = "gemini-3.5-flash"


class GeminiLLM:
    name = "gemini"

    def __init__(
        self,
        model: str | None = None,
        project: str | None = None,
        location: str = "global",
        api_key: str | None = None,
    ):
        from google import genai  # lazy: optional dependency

        if api_key:
            self._client = genai.Client(api_key=api_key)
        else:
            self._client = genai.Client(vertexai=True, project=project, location=location)
        self.model = model or DEFAULT_MODEL
        self.last_usage: LLMUsage | None = None

    def generate_structured(self, system: str, prompt: str, schema: type[T]) -> T:
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "system_instruction": system,
                "response_mime_type": "application/json",
                "response_schema": schema,
                "temperature": 0,
            },
        )
        meta = getattr(resp, "usage_metadata", None)
        if meta is not None:
            in_tok = int(getattr(meta, "prompt_token_count", 0) or 0)
            out_tok = int(getattr(meta, "candidates_token_count", 0) or 0)
            total = int(getattr(meta, "total_token_count", 0) or (in_tok + out_tok))
            cached = int(getattr(meta, "cached_content_token_count", 0) or 0)
            self.last_usage = LLMUsage(
                provider=self.name,
                model=self.model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                total_tokens=total,
                cache_read_input_tokens=cached,
            )
        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        return schema.model_validate_json(resp.text)
