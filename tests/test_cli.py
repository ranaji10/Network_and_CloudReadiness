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


def test_assess_share_safe_flag(monkeypatch, fixtures_dir, tmp_path):
    monkeypatch.setenv("READINESS_WORKSPACE_DIR", str(tmp_path))
    args = ["assess", str(fixtures_dir / "synthetic_acme"), "--profile", "security_only"]
    r = runner.invoke(app, [*args, "--share-safe"])
    assert r.exit_code == 0, r.output
    assert "Rendered share-safe" in r.output and "security_policy.md" not in r.output
    r = runner.invoke(app, args)
    assert r.exit_code == 0 and "Rendered share-safe" not in r.output and "security_policy.md" in r.output


def test_profiles_and_checks_commands():
    out = runner.invoke(app, ["profiles"]).output
    assert "gcp_migration" in out
    for industry in ("healthcare", "finance", "public_sector"):
        assert industry in out
    assert "NS-PER-01" in runner.invoke(app, ["checks", "network_security"]).output


def test_assess_pdf_flag_and_export_pdf(monkeypatch, fixtures_dir, tmp_path):
    monkeypatch.setenv("READINESS_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setenv("READINESS_LLM_PROVIDER", "mock")
    r = runner.invoke(
        app, ["assess", str(fixtures_dir / "synthetic_acme"), "--profile", "security_only", "--no-print", "--pdf"]
    )
    assert r.exit_code == 0, r.output
    run_dirs = [d for d in (tmp_path / "local").iterdir() if d.is_dir()]
    assert len(run_dirs) == 1 and (run_dirs[0] / "report.pdf").read_bytes().startswith(b"%PDF")
    out = tmp_path / "again.pdf"
    r = runner.invoke(app, ["export-pdf", str(run_dirs[0] / "report.json"), "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert out.read_bytes().startswith(b"%PDF")


def test_export_pdf_without_extra_fails_with_hint(monkeypatch, fixtures_dir, tmp_path):
    import sys

    monkeypatch.setenv("READINESS_WORKSPACE_DIR", str(tmp_path))
    r = runner.invoke(app, ["assess", str(fixtures_dir / "synthetic_acme"), "--profile", "security_only", "--no-print"])
    assert r.exit_code == 0, r.output
    report_json = next((tmp_path / "local").glob("*/report.json"))
    monkeypatch.setitem(sys.modules, "fpdf", None)
    r = runner.invoke(app, ["export-pdf", str(report_json)])
    assert r.exit_code == 2 and "uv sync --extra pdf" in r.output


def test_answer_command_and_include_answers(monkeypatch, fixtures_dir, tmp_path):
    """AGT-03: `readiness answer` stores a document under the tenant; `assess --include-answers` scores it."""
    import re

    monkeypatch.setenv("READINESS_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setenv("READINESS_LLM_PROVIDER", "mock")
    src = str(fixtures_dir / "synthetic_acme")
    r = runner.invoke(app, ["assess", src, "--profile", "security_only", "--no-print"])
    assert r.exit_code == 0, r.output
    run_id = re.search(r"run=(\w+)", r.output).group(1)
    coverage = float(re.search(r"coverage=([\d.]+)", r.output).group(1))
    assert "answers=" not in r.output

    answers_yaml = tmp_path / "answers.yaml"
    answers_yaml.write_text(
        "answers:\n  - check_id: NS-PER-02\n    answer: Public apps sit behind a WAF with DDoS protection.\n"
    )
    r = runner.invoke(
        app,
        [
            "answer",
            run_id,
            "--from",
            str(answers_yaml),
            "--check",
            "NS-DET-02",
            "--answer",
            "An IDS and IPS inspect traffic.",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "stored 2 answer(s) for 2 check(s)" in r.output
    stored = list((tmp_path / "local" / "answers").glob(f"{run_id}-*.md"))  # default tenant id is `local`
    assert len(stored) == 1

    r = runner.invoke(app, ["assess", src, "--profile", "security_only", "--no-print", "--include-answers"])
    assert r.exit_code == 0, r.output
    assert "answers=2" in r.output
    assert float(re.search(r"coverage=([\d.]+)", r.output).group(1)) > coverage

    r = runner.invoke(app, ["answer", run_id, "--check", "NS-PER-02"])
    assert r.exit_code != 0 and "same number" in r.output
    r = runner.invoke(app, ["answer", run_id, "--check", "NS-NOPE-99", "--answer", "x"])
    assert r.exit_code != 0 and "unknown check" in r.output
    r = runner.invoke(app, ["answer", run_id])
    assert r.exit_code != 0
