"""Runtime configuration. Everything comes from environment variables (or .env) so that switching
cloud provider, account or model never requires a code change. See docs/architecture/PROVIDER_PORTABILITY.md."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from readiness.ingestion.extract import OcrOptions

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
    # --- LLM judge cost controls (LLM-06); see scoring/engine.py ---
    # Documents sent to the judge per pillar: the best-ranked by signal hits for that pillar's checks,
    # documents with no hit are never sent. 0 = every relevant document (no pre-selection).
    judge_max_docs_per_pillar: int = 8
    # Evidence characters per judge call; the selected documents share this budget (2,000 minimum each)
    # and are split into several calls only when they still do not fit.
    judge_batch_chars: int = 60_000
    # Mark the static prompt prefix (system prompt, untrusted-data preamble, check list; never document
    # text) as cacheable where the provider SDK supports it (Anthropic `cache_control`). No effect on the mock.
    llm_prompt_caching: bool = True

    # --- GCP (read only when provider == gcp or llm_provider == gemini via Vertex) ---
    gcp_project: str = Field(default="", validation_alias="GOOGLE_CLOUD_PROJECT")
    gcp_location: str = Field(default="global", validation_alias="GOOGLE_CLOUD_LOCATION")
    # Vertex location for Gemini calls. Kept separate from GOOGLE_CLOUD_LOCATION on purpose: hosted runtimes
    # (Agent Runtime, Cloud Run) set that variable to their own region, while recent Gemini models are only
    # served from `global` (the V1.1 lesson). Override with READINESS_GEMINI_LOCATION if a region is required.
    gemini_location: str = "global"
    gcs_bucket_uploads: str = ""
    gcs_bucket_reports: str = ""

    # --- AWS ---
    aws_region: str = Field(default="", validation_alias="AWS_REGION")
    s3_bucket_uploads: str = ""
    s3_bucket_reports: str = ""

    # --- secrets (local dev only; production uses the SecretStore port) ---
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    api_token: str = ""  # single-tenant token; maps to `tenant_id`
    tenant_tokens: dict[str, str] = {}  # JSON map tenant_id -> bearer token (READINESS_TENANT_TOKENS or a secret)
    auth_disabled: bool = False

    # --- guardrails ---
    redaction_mode: Literal["off", "mask", "pseudonymize"] = "pseudonymize"
    include_evidence_snippets: bool = False
    # Share-safe rendering (GRD-09): for a report that leaves the tenant. Forces `mask` redaction (no reversible
    # pseudonyms), drops evidence snippets and replaces every document name in the report with an opaque label
    # derived from the document hash. Per run, not a deployment default: `--share-safe` / `share_safe=true`.
    share_safe: bool = False
    # Also ingest the tenant's stored questionnaire answers (<workspace>/<tenant>/answers/, AGT-03).
    include_answers: bool = False
    tenant_id: str = "local"
    max_doc_bytes: int = 25 * 1024 * 1024
    max_text_chars: int = 400_000
    allowed_source_schemes: list[str] = ["file", "gs", "s3", "gdrive"]
    # --- OCR for scanned PDFs and images (ING-08; `ocr` extra + the tesseract-ocr binary) ---
    # Runs in-process with the local Tesseract binary; nothing is sent to an OCR service. When the extra or the
    # binary is missing the scanned pages are reported as an extraction error (a report warning) and the run
    # continues, so `true` is a safe default. A PDF page is OCR'd only when pypdf finds fewer than
    # `ocr_min_chars_per_page` characters on it; at most `ocr_max_pages` pages per document are OCR'd.
    ocr_enabled: bool = True
    ocr_min_chars_per_page: int = 20
    ocr_max_pages: int = 50
    ocr_dpi: int = 200
    ocr_languages: str = "eng"  # Tesseract language codes joined with `+`; each needs its traineddata installed

    def ocr_options(self) -> OcrOptions:
        return OcrOptions(
            enabled=self.ocr_enabled,
            min_chars_per_page=self.ocr_min_chars_per_page,
            max_pages=self.ocr_max_pages,
            dpi=self.ocr_dpi,
            languages=self.ocr_languages,
        )

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
