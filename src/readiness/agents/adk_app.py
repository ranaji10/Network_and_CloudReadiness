"""Optional Google ADK wrapper so the assessor can be hosted on Vertex AI Agent Engine / Gemini Enterprise,
continuing the V1.1 path. The agent is thin: all logic lives in readiness.pipeline, so the same engine is
used whether it is called from the CLI, the API or a chat agent. Requires `readiness[adk]`.

Run locally:  adk web src/readiness/agents   (after `uv sync --extra adk --extra gcp`)"""

from __future__ import annotations

import json
import os
import tempfile
from functools import cached_property
from pathlib import Path

from readiness.agents.prompts import COORDINATOR
from readiness.config import get_settings


def _settings():
    settings = get_settings()
    if not os.environ.get("READINESS_WORKSPACE_DIR"):
        # Hosted runtimes (Agent Engine) may not allow writes next to the code; use the temp dir.
        settings = settings.model_copy(update={"workspace_dir": Path(tempfile.gettempdir()) / "readiness-workspace"})
    return settings


def run_readiness_assessment(source_uri: str, profile: str = "default", include_answers: bool = False) -> dict:
    """Assess all documents under `source_uri` and return scores, grades and prioritised recommendations.

    Args:
        source_uri: folder path, gs://bucket/prefix, s3://bucket/prefix or gdrive://<folder id or URL>.
        profile: scoring profile id (default, gcp_migration, security_only, healthcare, finance, public_sector).
        include_answers: also score the questionnaire answers stored earlier with
            `submit_questionnaire_answers` (the re-run after the client answered discovery questions).
    """
    from readiness.pipeline import run_assessment

    settings = _settings()
    report, _ = run_assessment(source_uri, settings, profile, include_answers=include_answers)
    summary = {
        "run_id": report.id,
        # Where report.json / report.md / audit.jsonl were written, so a client can fetch the full report.
        "report_dir": str(Path(settings.workspace_dir) / settings.tenant_id / report.id),
        "overall_score": report.overall_score,
        "evidence_coverage": report.overall_coverage,
        "answers_included": report.extra.get("answers_included", 0),
        "domains": [
            {"id": d.domain_id, "name": d.name, "score": d.score, "grade": d.grade, "coverage": d.coverage}
            for d in report.domains
        ],
        "top_actions": [
            {
                "title": r.title,
                "effort": r.effort,
                "impact": r.impact,
                "closes": r.closes_check_ids or [r.check_id],
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


def submit_questionnaire_answers(run_id: str, answers: list[dict[str, str]]) -> dict:
    """Store the client's answers to the discovery questions of an earlier run as a document in the tenant
    workspace. Then call `run_readiness_assessment` again on the same source with include_answers=true.

    Args:
        run_id: the run_id returned by run_readiness_assessment whose discovery items are being answered.
        answers: one entry per answered check: {"check_id": "<id from the discovery list>",
            "answer": "<the client's answer>"} and optionally "question" (the question as shown).

    Returns the stored document id and counts, never the answer text.
    """
    from readiness.questionnaire import parse_answer_file, store_answers

    stored = store_answers(parse_answer_file(answers, run_id), _settings())
    return json.loads(stored.model_dump_json(exclude={"path"}))


def build_root_agent():
    from google.adk.agents import LlmAgent
    from google.adk.models import Gemini
    from google.genai import Client

    settings = get_settings()

    class GlobalGemini(Gemini):
        """Pins Vertex calls to READINESS_GEMINI_LOCATION (default `global`), not the runtime's own region."""

        @cached_property
        def api_client(self) -> Client:
            return Client(vertexai=True, project=settings.gcp_project or None, location=settings.gemini_location)

    return LlmAgent(
        name="readiness_coordinator",
        model=GlobalGemini(model=settings.llm_model or "gemini-3.5-flash"),
        description="Assesses network security, cloud and agentic-AI readiness from a document source.",
        instruction=COORDINATOR,
        tools=[run_readiness_assessment, submit_questionnaire_answers],
    )


try:  # `adk web` discovers `root_agent` at import time; stay importable without ADK installed.
    root_agent = build_root_agent()
except Exception:  # noqa: BLE001
    root_agent = None
