"""AGT-04: the MCP server exposes the assessment tools to Claude Code and other MCP clients.
Exercised through the SDK's in-memory transport, offline, with the mock LLM."""

import asyncio
import json

import pytest
from typer.testing import CliRunner

from readiness.agents import mcp_server
from readiness.cli import app

pytest.importorskip("mcp")

TOOLS = {"run_readiness_assessment", "submit_questionnaire_answers", "list_profiles", "list_checks"}


def _payload(result) -> object:
    """The tool's return value: the SDK's structured content (lists are wrapped under `result`), else the text."""
    assert not result.is_error, result.content
    structured = result.structured_content
    if structured is not None:
        return structured["result"] if set(structured) == {"result"} else structured
    return json.loads(result.content[0].text)


def _with_client(fn):
    from mcp import Client

    async def go():
        async with Client(mcp_server.build_server(), raise_exceptions=True) as c:
            return await fn(c)

    return asyncio.run(go())


def test_server_lists_the_three_tools():
    async def go(client):
        return await client.list_tools()

    listed = _with_client(go)
    assert {t.name for t in listed.tools} == TOOLS
    run_tool = next(t for t in listed.tools if t.name == "run_readiness_assessment")
    assert set(run_tool.input_schema["properties"]) == {"source_uri", "profile", "include_answers"}
    assert run_tool.input_schema["required"] == ["source_uri"]


@pytest.fixture
def stderr_logging():
    """Apply the stdio logging setup for one test, then restore structlog's defaults for the rest of the suite."""
    import structlog

    mcp_server.route_logs_to_stderr()
    yield
    structlog.reset_defaults()


def test_run_readiness_assessment_offline(monkeypatch, fixtures_dir, tmp_path, capsys, stderr_logging):
    monkeypatch.setenv("READINESS_LLM_PROVIDER", "mock")
    monkeypatch.setenv("READINESS_WORKSPACE_DIR", str(tmp_path))

    async def go(client):
        return await client.call_tool(
            "run_readiness_assessment",
            {"source_uri": str(fixtures_dir / "synthetic_acme"), "profile": "security_only"},
        )

    result = _with_client(go)
    captured = capsys.readouterr()
    assert captured.out == "", "stdout is the stdio protocol channel; pipeline logs must go to stderr"
    assert "run.end" in captured.err or "score=" in captured.err
    summary = _payload(result)
    assert result.structured_content is not None  # clients get a typed object, not only text
    assert summary["run_id"] and 0 <= summary["overall_score"] <= 100
    assert [d["id"] for d in summary["domains"]] == ["network_security"]
    # Compact: summaries only, but the client is told where the full report lives.
    assert set(summary) >= {"run_id", "report_dir", "overall_score", "evidence_coverage", "top_actions", "discovery"}
    assert summary["report_dir"].startswith(str(tmp_path))
    assert (tmp_path / "local" / summary["run_id"] / "report.md").exists()
    assert len(summary["top_actions"]) <= 10 and len(summary["discovery"]) <= 15
    # REC-04: every listed option carries its indicative monthly cost band (this strong synthetic policy may
    # leave no action with options; the shape is what matters here, the catalog test covers completeness)
    listed = [o for a in summary["top_actions"] for o in a["options"]]
    assert all(o["cost_band"] in ("none", "low", "medium", "high") for o in listed)


def test_list_profiles_and_checks_tools():
    async def go(client):
        profiles = await client.call_tool("list_profiles", {})
        checks = await client.call_tool("list_checks", {"domain": "network_security"})
        all_checks = await client.call_tool("list_checks", {})
        return profiles, checks, all_checks

    profiles, checks, all_checks = _with_client(go)
    assert {p["id"] for p in _payload(profiles)} >= {"default", "gcp_migration", "security_only"}
    ids = {c["id"] for c in _payload(checks)}
    assert "NS-PER-01" in ids and all(i.startswith("NS-") for i in ids)
    assert {c["domain"] for c in _payload(all_checks)} > {"network_security"}


def test_tool_delegates_to_the_adk_function(monkeypatch):
    """One function, many wrappers (ADR-20261023-adk-wrapper-kept-thin): no second pipeline call."""
    calls: list[tuple[str, str, bool]] = []

    def fake(source_uri: str, profile: str = "default", include_answers: bool = False) -> dict:
        calls.append((source_uri, profile, include_answers))
        return {"run_id": "x"}

    monkeypatch.setattr("readiness.agents.adk_app.run_readiness_assessment", fake)
    assert mcp_server.run_readiness_assessment("src", "gcp_migration") == {"run_id": "x"}
    assert calls == [("src", "gcp_migration", False)]


def test_cli_reports_install_hint_when_sdk_missing(monkeypatch):
    def boom():
        raise ImportError("No module named 'mcp'")

    monkeypatch.setattr(mcp_server, "build_server", boom)
    r = CliRunner().invoke(app, ["mcp"])
    assert r.exit_code == 1
    assert "uv sync --extra mcp" in r.output


def test_cli_runs_server_on_stdio(monkeypatch):
    seen: dict[str, str] = {}

    class FakeServer:
        def run(self, transport: str) -> None:
            seen["transport"] = transport

    monkeypatch.setattr(mcp_server, "build_server", lambda: FakeServer())
    assert CliRunner().invoke(app, ["mcp"]).exit_code == 0
    assert seen == {"transport": "stdio"}


def test_questionnaire_round_trip_over_mcp(monkeypatch, fixtures_dir, tmp_path, stderr_logging):
    """AGT-03 over MCP: run, submit answers (metadata only comes back), re-run with include_answers."""
    monkeypatch.setenv("READINESS_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setenv("READINESS_LLM_PROVIDER", "mock")
    src = str(fixtures_dir / "synthetic_acme")

    async def go(client):
        first = _payload(
            await client.call_tool("run_readiness_assessment", {"source_uri": src, "profile": "security_only"})
        )
        stored = await client.call_tool(
            "submit_questionnaire_answers",
            {
                "run_id": first["run_id"],
                "answers": [{"check_id": "NS-PER-02", "answer": "Public apps sit behind a WAF with DDoS protection."}],
            },
        )
        again = _payload(
            await client.call_tool(
                "run_readiness_assessment", {"source_uri": src, "profile": "security_only", "include_answers": True}
            )
        )
        return first, stored, again

    first, stored, again = _with_client(go)
    assert _payload(stored)["answers"] == 1 and "WAF" not in str(stored.content)
    assert again["evidence_coverage"] > first["evidence_coverage"] and again["answers_included"] == 1
