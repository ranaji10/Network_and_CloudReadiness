"""Optional Google ADK wrapper so the assessor can be hosted on Vertex AI Agent Engine / Gemini Enterprise,
continuing the V1.1 path. The agent is thin: all logic lives in readiness.pipeline, so the same engine is
used whether it is called from the CLI, the API or a chat agent. Requires `readiness[adk]`.

Run locally:  adk web src/readiness/agents   (after `uv sync --extra adk --extra gcp`)"""

from __future__ import annotations

import json
from functools import cached_property

from readiness.agents.prompts import COORDINATOR
from readiness.config import get_settings


def run_readiness_assessment(source_uri: str, profile: str = "default") -> dict:
    """Assess all documents under `source_uri` and return scores, grades and prioritised recommendations.

    Args:
        source_uri: folder path, gs://bucket/prefix, s3://bucket/prefix or gdrive://<folder id or URL>.
        profile: scoring profile id (default, gcp_migration, security_only).
    """
    from readiness.pipeline import run_assessment

    report, _ = run_assessment(source_uri, get_settings(), profile)
    summary = {
        "run_id": report.id,
        "overall_score": report.overall_score,
        "evidence_coverage": report.overall_coverage,
        "domains": [
            {"id": d.domain_id, "name": d.name, "score": d.score, "grade": d.grade, "coverage": d.coverage}
            for d in report.domains
        ],
        "top_actions": [
            {
                "title": r.title,
                "effort": r.effort,
                "impact": r.impact,
                "options": [o.model_dump() for o in r.options[:3]],
            }
            for r in report.recommendations
            if r.kind == "action"
        ][:10],
        "discovery": [
            {"check": r.check_id, "title": r.title, "questions": r.caiq_questions[:3]}
            for r in report.recommendations
            if r.kind == "discovery"
        ][:15],
        "warnings": report.warnings,
    }
    return json.loads(json.dumps(summary))


def build_root_agent():
    from google.adk.agents import LlmAgent
    from google.adk.models import Gemini
    from google.genai import Client

    settings = get_settings()

    class GlobalGemini(Gemini):
        """Pins Vertex calls to the `global` location (gemini-3 family is only served there)."""

        @cached_property
        def api_client(self) -> Client:
            return Client(vertexai=True, project=settings.gcp_project or None, location=settings.gcp_location)

    return LlmAgent(
        name="readiness_coordinator",
        model=GlobalGemini(model=settings.llm_model or "gemini-2.5-flash"),
        description="Assesses network security, cloud and agentic-AI readiness from a document source.",
        instruction=COORDINATOR,
        tools=[run_readiness_assessment],
    )


try:  # `adk web` discovers `root_agent` at import time; stay importable without ADK installed.
    root_agent = build_root_agent()
except Exception:  # noqa: BLE001
    root_agent = None
