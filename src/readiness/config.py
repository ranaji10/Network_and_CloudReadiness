"""Runtime configuration. Everything comes from environment variables (or .env) so that switching
cloud provider, account or model never requires a code change. See docs/architecture/PROVIDER_PORTABILITY.md."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]


def resolve_default_config_dir() -> Path:
    """Where the YAML configuration lives, in order of preference:

    1. `<repo>/config` when running from a checkout (development, Docker image, Cloud Run);
    2. `<package parent>/config` when the package was staged next to a `config` folder
       (`adk deploy agent_engine --extra_packages src/readiness --extra_packages config`);
    3. the copy bundled into the wheel (`readiness/_bundled_config`) for `pip install` users.
    `READINESS_CONFIG_DIR` overrides all of them."""
    for candidate in (REPO_ROOT / "config", PACKAGE_DIR.parent / "config", PACKAGE_DIR / "_bundled_config"):
        if (candidate / "profiles").is_dir():
            return candidate
    return REPO_ROOT / "config"


DEFAULT_CONFIG_DIR = resolve_default_config_dir()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="READINESS_", env_file=".env", extra="ignore")

    # --- portability switches ---
    provider: Literal["local", "gcp", "aws"] = "local"
    llm_provider: Literal["mock", "gemini", "anthropic"] = "mock"
    llm_model: str = ""
    allow_llm_egress: bool = False
    use_llm_judge: bool = False  # refine rule-based verdicts with the LLM (needs egress allowed)
    use_llm_classifier: bool = False

    # --- GCP (read only when provider == gcp or llm_provider == gemini via Vertex) ---
    gcp_project: str = Field(default="", validation_alias="GOOGLE_CLOUD_PROJECT")
    gcp_location: str = Field(default="global", validation_alias="GOOGLE_CLOUD_LOCATION")
    gcs_bucket_uploads: str = ""
    gcs_bucket_reports: str = ""

    # --- AWS ---
    aws_region: str = Field(default="", validation_alias="AWS_REGION")
    s3_bucket_uploads: str = ""
    s3_bucket_reports: str = ""

    # --- secrets (local dev only; production uses the SecretStore port) ---
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    api_token: str = ""
    auth_disabled: bool = False

    # --- guardrails ---
    redaction_mode: Literal["off", "mask", "pseudonymize"] = "pseudonymize"
    include_evidence_snippets: bool = False
    tenant_id: str = "local"
    max_doc_bytes: int = 25 * 1024 * 1024
    max_text_chars: int = 400_000
    allowed_source_schemes: list[str] = ["file", "gs", "s3", "gdrive"]

    # --- paths ---
    workspace_dir: Path = Path("./workspace")
    config_dir: Path = Field(default_factory=resolve_default_config_dir)
    default_profile: str = "default"

    def require_llm_egress(self) -> None:
        if self.llm_provider != "mock" and not self.allow_llm_egress:
            raise PermissionError(
                "LLM egress is disabled (READINESS_ALLOW_LLM_EGRESS=false) but a real LLM provider "
                f"'{self.llm_provider}' was requested. This is a deliberate guardrail: enable egress "
                "explicitly once you have confirmed the redaction mode and the data-handling policy."
            )


def get_settings(**overrides) -> Settings:
    return Settings(**overrides)
