"""HTTP API. Designed to sit behind Cloud Run IAM / an API gateway; bearer tokens are a second layer that
also decide the tenant every report is stored under.

GET  /                       minimal web UI
GET  /healthz
GET  /profiles
POST /assessments            assess a source_uri synchronously -> report
POST /assessments/upload     assess uploaded files synchronously -> report
POST /jobs                   assess a source_uri in the background -> job record
POST /jobs/upload            upload files, assess in the background -> job record
GET  /jobs/{job_id}          job record (queued | running | done | failed)
GET  /assessments/{id}       report JSON        (tenant-scoped)
GET  /assessments/{id}/report.md               (tenant-scoped)

Tenancy: `READINESS_TENANT_TOKENS` (JSON map tenant -> token) gives each client its own token; a request's
tenant is derived from the token it presents and every key it can read or write is prefixed with that tenant.
`READINESS_API_TOKEN` remains as a single-tenant token mapped to `READINESS_TENANT_ID`."""

from __future__ import annotations

import json
import secrets
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from readiness import __version__
from readiness.adapters.registry import make_blob_store
from readiness.config import Settings, get_settings
from readiness.models import AssessmentReport
from readiness.ports import BlobStore
from readiness.scoring.profiles import list_profiles

app = FastAPI(title="Network & Cloud Readiness Assessor", version=__version__)
STATIC = Path(__file__).resolve().parent / "static"


def settings_dep() -> Settings:
    return get_settings()


@dataclass(frozen=True)
class Principal:
    tenant_id: str


def auth(
    authorization: Annotated[str | None, Header()] = None, settings: Settings = Depends(settings_dep)
) -> Principal:
    """Resolve the caller's tenant from its bearer token. Constant-time comparisons; no token is ever logged."""
    if settings.auth_disabled:
        return Principal(settings.tenant_id)
    if not settings.api_token and not settings.tenant_tokens:
        raise HTTPException(503, "API disabled: no READINESS_API_TOKEN or READINESS_TENANT_TOKENS configured")
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "invalid token")
    matched: str | None = None
    for tenant, expected in settings.tenant_tokens.items():  # compare against every token: no early exit
        if expected and secrets.compare_digest(token, expected):
            matched = tenant
    if settings.api_token and secrets.compare_digest(token, settings.api_token):
        matched = matched or settings.tenant_id
    if matched is None:
        raise HTTPException(401, "invalid token")
    return Principal(matched)


def _tenant_settings(settings: Settings, principal: Principal, **overrides: object) -> Settings:
    return settings.model_copy(update={"tenant_id": principal.tenant_id, **overrides})


class AssessRequest(BaseModel):
    source_uri: str
    profile: str = "default"
    include_evidence_snippets: bool = False


class JobRecord(BaseModel):
    id: str
    tenant_id: str
    status: str  # queued | running | done | failed
    profile: str
    created_at: datetime
    updated_at: datetime
    report_id: str | None = None
    error: str | None = None


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def ui() -> str:
    """Minimal single-page UI (upload documents, see scores and the report). No data is kept client-side
    except the API token in sessionStorage; the page calls the same authenticated endpoints as any client."""
    return (STATIC / "index.html").read_text()


@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": __version__}


@app.get("/profiles", dependencies=[Depends(auth)])
def profiles(settings: Settings = Depends(settings_dep)):
    return [p.model_dump() for p in list_profiles(settings.config_dir)]


# ---------------------------------------------------------------------------
# Assessment execution and storage (tenant-prefixed keys)
# ---------------------------------------------------------------------------
def _store_report(store: BlobStore, report: AssessmentReport, md: str) -> None:
    key = f"{report.tenant_id}/{report.id}"
    store.put(f"{key}/report.json", report.model_dump_json(indent=1).encode(), "application/json")
    store.put(f"{key}/report.md", md.encode(), "text/markdown")


def _run(source_uri: str, profile: str, snippets: bool, settings: Settings) -> AssessmentReport:
    from readiness.pipeline import run_assessment

    s = settings.model_copy(update={"include_evidence_snippets": snippets})
    report, md = run_assessment(source_uri, s, profile)
    _store_report(make_blob_store(s, "reports"), report, md)
    return report


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(403, str(exc))
    if isinstance(exc, FileNotFoundError):
        return HTTPException(404, str(exc))
    return HTTPException(500, f"{type(exc).__name__}: {exc}"[:300])


def _save_uploads(files: list[UploadFile], root: Path, settings: Settings) -> None:
    for f in files:
        name = Path(f.filename or "upload").name  # strip any path components
        data = f.file.read(settings.max_doc_bytes + 1)
        if len(data) > settings.max_doc_bytes:
            raise HTTPException(413, f"{name} exceeds READINESS_MAX_DOC_BYTES")
        (root / name).write_bytes(data)


@app.post("/assessments", dependencies=[Depends(auth)])
def create_from_uri(
    req: AssessRequest, principal: Principal = Depends(auth), settings: Settings = Depends(settings_dep)
):
    try:
        report = _run(req.source_uri, req.profile, req.include_evidence_snippets, _tenant_settings(settings, principal))
    except Exception as exc:  # noqa: BLE001 - mapped to an HTTP status
        raise _http_error(exc) from exc
    return report.model_dump(mode="json")


@app.post("/assessments/upload")
def create_from_upload(
    files: list[UploadFile] = File(...),
    profile: str = "default",
    principal: Principal = Depends(auth),
    settings: Settings = Depends(settings_dep),
):
    with tempfile.TemporaryDirectory(prefix="readiness-upload-") as tmp:
        root = Path(tmp)
        _save_uploads(files, root, settings)
        try:
            report = _run(f"file://{root}", profile, False, _tenant_settings(settings, principal))
        except Exception as exc:  # noqa: BLE001
            raise _http_error(exc) from exc
    return report.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Async jobs. The job record lives in the reports store under <tenant>/jobs/<id>.json; the work runs in a
# background task of the same process. On Cloud Run this needs CPU allocated after the response
# (`--no-cpu-throttling`, set by the pipeline and Terraform); a queue-backed worker is tracker API-06 follow-up.
# ---------------------------------------------------------------------------
def _job_key(tenant_id: str, job_id: str) -> str:
    return f"{tenant_id}/jobs/{job_id}.json"


def _write_job(store: BlobStore, job: JobRecord) -> None:
    job.updated_at = datetime.now(UTC)
    store.put(_job_key(job.tenant_id, job.id), job.model_dump_json(indent=1).encode(), "application/json")


def _execute_job(job: JobRecord, source_uri: str, snippets: bool, settings: Settings, cleanup: Path | None) -> None:
    store = make_blob_store(settings, "reports")
    job.status = "running"
    _write_job(store, job)
    try:
        report = _run(source_uri, job.profile, snippets, settings)
        job.status, job.report_id = "done", report.id
    except Exception as exc:  # noqa: BLE001 - recorded on the job, never raised out of a background task
        job.status, job.error = "failed", f"{type(exc).__name__}: {exc}"[:300]
    finally:
        if cleanup is not None:
            for child in cleanup.glob("*"):
                child.unlink(missing_ok=True)
            cleanup.rmdir()
    _write_job(store, job)


def _new_job(settings: Settings, profile: str) -> JobRecord:
    now = datetime.now(UTC)
    return JobRecord(
        id=uuid.uuid4().hex[:12],
        tenant_id=settings.tenant_id,
        status="queued",
        profile=profile,
        created_at=now,
        updated_at=now,
    )


@app.post("/jobs", status_code=202)
def create_job(
    req: AssessRequest,
    background: BackgroundTasks,
    principal: Principal = Depends(auth),
    settings: Settings = Depends(settings_dep),
):
    s = _tenant_settings(settings, principal)
    job = _new_job(s, req.profile)
    _write_job(make_blob_store(s, "reports"), job)
    background.add_task(_execute_job, job, req.source_uri, req.include_evidence_snippets, s, None)
    return job.model_dump(mode="json")


@app.post("/jobs/upload", status_code=202)
def create_job_from_upload(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    profile: str = "default",
    principal: Principal = Depends(auth),
    settings: Settings = Depends(settings_dep),
):
    s = _tenant_settings(settings, principal)
    job = _new_job(s, profile)
    staging = Path(tempfile.mkdtemp(prefix=f"readiness-job-{job.id}-"))  # removed by the job when it finishes
    _save_uploads(files, staging, settings)
    _write_job(make_blob_store(s, "reports"), job)
    background.add_task(_execute_job, job, f"file://{staging}", False, s, staging)
    return job.model_dump(mode="json")


@app.get("/jobs/{job_id}")
def get_job(job_id: str, principal: Principal = Depends(auth), settings: Settings = Depends(settings_dep)):
    store = make_blob_store(_tenant_settings(settings, principal), "reports")
    key = _job_key(principal.tenant_id, job_id)
    if not store.exists(key):
        raise HTTPException(404, "unknown job")
    return json.loads(store.get(key))


# ---------------------------------------------------------------------------
# Reports (tenant-scoped)
# ---------------------------------------------------------------------------
@app.get("/assessments/{run_id}")
def get_report(run_id: str, principal: Principal = Depends(auth), settings: Settings = Depends(settings_dep)):
    store = make_blob_store(_tenant_settings(settings, principal), "reports")
    key = f"{principal.tenant_id}/{run_id}/report.json"
    if not store.exists(key):
        raise HTTPException(404, "unknown assessment")
    return json.loads(store.get(key))


@app.get("/assessments/{run_id}/report.md", response_class=PlainTextResponse)
def get_report_md(run_id: str, principal: Principal = Depends(auth), settings: Settings = Depends(settings_dep)):
    store = make_blob_store(_tenant_settings(settings, principal), "reports")
    key = f"{principal.tenant_id}/{run_id}/report.md"
    if not store.exists(key):
        raise HTTPException(404, "unknown assessment")
    return store.get(key).decode()
