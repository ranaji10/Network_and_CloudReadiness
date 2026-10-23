from pathlib import Path

from readiness import config as cfg


def test_checkout_config_wins():
    assert cfg.resolve_default_config_dir() == cfg.REPO_ROOT / "config"


def test_agent_engine_layout(monkeypatch, tmp_path: Path):
    # Simulate `adk deploy --extra_packages src/readiness --extra_packages config`: /app/readiness + /app/config
    (tmp_path / "config" / "profiles").mkdir(parents=True)
    monkeypatch.setattr(cfg, "REPO_ROOT", tmp_path / "nowhere")
    monkeypatch.setattr(cfg, "PACKAGE_DIR", tmp_path / "readiness")
    assert cfg.resolve_default_config_dir() == tmp_path / "config"


def test_bundled_fallback(monkeypatch, tmp_path: Path):
    (tmp_path / "readiness" / "_bundled_config" / "profiles").mkdir(parents=True)
    monkeypatch.setattr(cfg, "REPO_ROOT", tmp_path / "nowhere")
    monkeypatch.setattr(cfg, "PACKAGE_DIR", tmp_path / "readiness")
    assert cfg.resolve_default_config_dir() == tmp_path / "readiness" / "_bundled_config"


def test_agent_requirements_mirror_pyproject():
    import tomllib

    py = tomllib.loads((cfg.REPO_ROOT / "pyproject.toml").read_text())
    wanted = {d.split(">=")[0].split("[")[0] for d in py["project"]["dependencies"]}
    wanted |= {d.split(">=")[0] for d in py["project"]["optional-dependencies"]["gcp"]}
    wanted |= {d.split(">=")[0] for d in py["project"]["optional-dependencies"]["adk"]}
    wanted -= {"typer", "fastapi", "uvicorn", "python-multipart", "httpx"}  # API/CLI only, not needed by the agent
    req = cfg.REPO_ROOT / "src" / "readiness" / "agents" / "requirements.txt"
    have = {line.split(">=")[0] for line in req.read_text().splitlines() if line and not line.startswith("#")}
    assert wanted == have


def test_agent_tool_uses_temp_workspace_when_unset(monkeypatch, fixtures_dir):
    import tempfile

    from readiness.agents.adk_app import run_readiness_assessment

    monkeypatch.delenv("READINESS_WORKSPACE_DIR", raising=False)
    out = run_readiness_assessment(str(fixtures_dir / "synthetic_acme"), "security_only")
    assert out["domains"][0]["id"] == "network_security"
    assert (Path(tempfile.gettempdir()) / "readiness-workspace").exists()
