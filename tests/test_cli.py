from typer.testing import CliRunner

from readiness.cli import app

runner = CliRunner()


def test_assess_flags_do_not_clobber_env(monkeypatch, fixtures_dir, tmp_path):
    """READINESS_USE_LLM_JUDGE=true must survive when --llm-judge is not given (LLM-01 finding)."""
    monkeypatch.setenv("READINESS_USE_LLM_JUDGE", "true")
    monkeypatch.setenv("READINESS_LLM_PROVIDER", "mock")
    monkeypatch.setenv("READINESS_WORKSPACE_DIR", str(tmp_path))
    r = runner.invoke(app, ["assess", str(fixtures_dir / "synthetic_acme"), "--profile", "security_only", "--no-print"])
    assert r.exit_code == 0, r.output
    assert "llm=mock" in r.output
    r = runner.invoke(
        app,
        ["assess", str(fixtures_dir / "synthetic_acme"), "--profile", "security_only", "--no-print", "--no-llm-judge"],
    )
    assert r.exit_code == 0 and "llm=none" in r.output


def test_profiles_and_checks_commands():
    assert "gcp_migration" in runner.invoke(app, ["profiles"]).output
    assert "NS-PER-01" in runner.invoke(app, ["checks", "network_security"]).output
