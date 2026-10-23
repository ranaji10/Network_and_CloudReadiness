"""Factory that turns Settings into concrete adapters. This is the ONLY place that knows which
adapter backs which provider name. Migration to another account/cloud = env change, not code change."""

from __future__ import annotations

from pathlib import Path

from readiness.config import Settings
from readiness.ports import BlobStore, DocumentSource, LLMProvider, SecretStore


def make_source(uri: str, settings: Settings) -> DocumentSource:
    scheme, _, rest = uri.partition("://")
    if not rest:  # bare path
        scheme, rest = "file", uri
    if scheme not in settings.allowed_source_schemes:
        raise PermissionError(f"Source scheme '{scheme}' is not allowed by READINESS_ALLOWED_SOURCE_SCHEMES")
    if scheme == "file":
        from readiness.adapters.sources.local_fs import LocalFolderSource

        return LocalFolderSource(Path(rest), max_bytes=settings.max_doc_bytes)
    if scheme == "gs":
        from readiness.adapters.sources.gcs import GCSSource

        bucket, _, prefix = rest.partition("/")
        return GCSSource(bucket, prefix, project=settings.gcp_project or None, max_bytes=settings.max_doc_bytes)
    if scheme == "s3":
        from readiness.adapters.sources.s3 import S3Source

        bucket, _, prefix = rest.partition("/")
        return S3Source(bucket, prefix, region=settings.aws_region or None, max_bytes=settings.max_doc_bytes)
    if scheme == "gdrive":
        from readiness.adapters.sources.gdrive import GoogleDriveSource

        return GoogleDriveSource(rest, max_bytes=settings.max_doc_bytes)
    raise ValueError(f"Unsupported source uri: {uri}")


def make_llm(settings: Settings, secrets: SecretStore | None = None) -> LLMProvider:
    if settings.llm_provider == "mock":
        from readiness.adapters.llm.mock import MockLLM

        return MockLLM()
    settings.require_llm_egress()
    secrets = secrets or make_secret_store(settings)
    if settings.llm_provider == "gemini":
        from readiness.adapters.llm.gemini import GeminiLLM

        return GeminiLLM(
            model=settings.llm_model or None,
            project=settings.gcp_project or None,
            location=settings.gemini_location,
            api_key=secrets.get("GEMINI_API_KEY"),
        )
    if settings.llm_provider == "anthropic":
        from readiness.adapters.llm.anthropic_llm import AnthropicLLM

        return AnthropicLLM(model=settings.llm_model or None, api_key=secrets.get("ANTHROPIC_API_KEY"))
    raise ValueError(f"Unknown llm provider {settings.llm_provider}")


def make_blob_store(settings: Settings, kind: str = "reports") -> BlobStore:
    if settings.provider == "gcp":
        from readiness.adapters.storage.gcs import GCSBlobStore

        bucket = settings.gcs_bucket_reports if kind == "reports" else settings.gcs_bucket_uploads
        if not bucket:
            raise ValueError(f"READINESS_GCS_BUCKET_{kind.upper()} is not set")
        return GCSBlobStore(bucket, project=settings.gcp_project or None)
    if settings.provider == "aws":
        from readiness.adapters.storage.s3 import S3BlobStore

        bucket = settings.s3_bucket_reports if kind == "reports" else settings.s3_bucket_uploads
        if not bucket:
            raise ValueError(f"READINESS_S3_BUCKET_{kind.upper()} is not set")
        return S3BlobStore(bucket, region=settings.aws_region or None)
    from readiness.adapters.storage.local import LocalBlobStore

    return LocalBlobStore(Path(settings.workspace_dir) / kind)


def make_secret_store(settings: Settings) -> SecretStore:
    if settings.provider == "gcp" and settings.gcp_project:
        from readiness.adapters.secrets.gcp_secret_manager import GCPSecretManagerStore

        return GCPSecretManagerStore(settings.gcp_project)
    if settings.provider == "aws":
        from readiness.adapters.secrets.aws_secrets_manager import AWSSecretsManagerStore

        return AWSSecretsManagerStore(region=settings.aws_region or None)
    from readiness.adapters.secrets.env import EnvSecretStore

    return EnvSecretStore()
