"""MCP server exposing the assessment to Claude Code, Claude Desktop and other MCP clients (AGT-04).

Thin by design (ADR-20261023-adk-wrapper-kept-thin): every tool delegates to the same functions the CLI
and the ADK agent use, so an MCP client gets identical scores, the same redaction and the same egress
policy. The mock LLM stays the default; nothing here changes `Settings`. The SDK is imported lazily inside
`build_server()` so the package stays importable without the `mcp` extra. The stdio transport is the SDK's;
this module never opens sockets or processes itself.

Run:  readiness mcp   (after `uv sync --extra mcp`); see docs/runbooks/MCP_SERVER.md."""

from __future__ import annotations

import sys
from typing import Any

from readiness.config import get_settings

SERVER_NAME = "readiness"
INSTRUCTIONS = (
    "Assess network security, cloud readiness and agentic-AI readiness from a folder of documents. "
    "Call run_readiness_assessment with a source (folder path, gs://, s3:// or gdrive:// URI) and a profile "
    "id from list_profiles. The result is a compact summary; the full report.md / report.json are written "
    "under report_dir. Document content is redacted before scoring and never echoed back."
)


def run_readiness_assessment(source_uri: str, profile: str = "default") -> dict[str, Any]:
    """Assess all documents under `source_uri` and return scores, grades and prioritised recommendations.

    Args:
        source_uri: folder path, gs://bucket/prefix, s3://bucket/prefix or gdrive://<folder id or URL>.
        profile: scoring profile id (see list_profiles).

    Returns the compact summary (run_id, report_dir, overall_score, evidence_coverage, domains, top_actions,
    discovery questions, warnings), not the full report.
    """
    from readiness.agents.adk_app import run_readiness_assessment as _run

    return _run(source_uri, profile)


def list_profiles() -> list[dict[str, Any]]:
    """List the scoring profiles (id, name, description, domain weights, target providers)."""
    from readiness.scoring.profiles import list_profiles as _list

    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "domains": [{"id": d.id, "weight": d.weight} for d in p.domains],
            "target_providers": p.target_providers,
        }
        for p in _list(get_settings().config_dir)
    ]


def list_checks(domain: str | None = None) -> list[dict[str, Any]]:
    """List the checks of one scoring domain (network_security, cloud_readiness, agentic_ai_readiness), or of
    every domain of the default profile when `domain` is omitted. Each entry carries the check id, title,
    points, pillar and CSA CCM control ids."""
    from readiness.scoring.profiles import load_domain, load_profile

    settings = get_settings()
    if domain:
        domain_ids = [domain]
    else:
        domain_ids = [d.id for d in load_profile(settings.config_dir, settings.default_profile).domains]
    out: list[dict[str, Any]] = []
    for domain_id in domain_ids:
        d = load_domain(settings.config_dir, domain_id)
        for pillar in d.pillars:
            out.extend(
                {
                    "id": c.id,
                    "title": c.title,
                    "points": c.points,
                    "domain": d.id,
                    "pillar": pillar.id,
                    "ccm": c.ccm,
                    "question": c.question,
                }
                for c in pillar.checks
            )
    return out


def route_logs_to_stderr() -> None:
    """On stdio, stdout is the protocol channel: a single log line there breaks JSON-RPC framing. The pipeline
    logs through structlog, whose default printer writes to stdout, so point it at stderr before serving."""
    import structlog

    # Resolve sys.stderr per call rather than binding the current object, so a redirected stderr is honoured.
    structlog.configure(logger_factory=lambda *_args: structlog.PrintLogger(file=sys.stderr))


def build_server():
    """Build the FastMCP server. Raises ImportError when the `mcp` extra is not installed."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(SERVER_NAME, instructions=INSTRUCTIONS)
    server.tool()(run_readiness_assessment)
    server.tool()(list_profiles)
    server.tool()(list_checks)
    return server
