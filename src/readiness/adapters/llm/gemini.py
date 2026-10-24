"""Gemini via the google-genai SDK. Works with Vertex AI (ADC, project + location) or an API key.

Model requests for the gemini-3 family must go to the `global` location (lesson carried over from the
V1.1 ADK code, see legacy/v1.1_adk)."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

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
        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        return schema.model_validate_json(resp.text)
