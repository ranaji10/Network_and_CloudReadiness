from pathlib import Path

import pytest

from readiness.config import DEFAULT_CONFIG_DIR, Settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # tests never read a developer's .env
        provider="local",
        llm_provider="mock",
        workspace_dir=tmp_path / "ws",
        config_dir=DEFAULT_CONFIG_DIR,
        tenant_id="test",
        auth_disabled=True,
    )
