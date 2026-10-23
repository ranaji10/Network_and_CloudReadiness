"""HTTP API. Designed to sit behind Cloud Run IAM / an API gateway; the bearer token is a second layer.

POST /assessments        multipart upload of documents (or JSON {"source_uri": ...}) -> report
GET  /assessments/{id}   report JSON
GET  /assessments/{id}/report.md
GET  /profiles, /healthz"""

from __future__ import annotations

import json
import secrets
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from readiness import __version__
from readiness.adapters.registry import make_blob_store
from readiness.config import Settings, get_settings
from readiness.scoring.profiles import list_profiles

app = FastAPI(title="Network & Cloud Readiness Assessor", version=__version__)


def settings_dep() -> Settings:
    return get_settings()


def auth(authorization: Annotated[str | None, Header()] = None, settings: Settings = Depends(settings_dep)) -> None:
    if settings.auth_disabled:
        return
    if not settings.api_token:
        raise HTTPException(503, "API disabled: READINESS_API_TOKEN is not configured")
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or not secrets.compare_digest(token, settings.api_token):
        raise HTTPException(401, "invalid token")


class AssessRequest(BaseModel):
    source_uri: str
    profile: str = "default"
    include_evidence_snippets: bool = False


@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": __version__}


@app.get("/profiles", dependencies=[Depends(auth)])
def profiles(settings: Settings = Depends(settings_dep)):
    return [p.model_dump() for p in list_profiles(settings.config_dir)]


def _run(source_uri: str, profile: str, snippets: bool, settings: Settings):
    from readiness.pipeline import run_assessment

    s = settings.model_copy(update={"include_evidence_snippets": snippets})
    report, md = run_assessment(source_uri, s, profile)
    store = make_blob_store(s, "reports")
    key = f"{s.tenant_id}/{report.id}"
    store.put(f"{key}/report.json", report.model_dump_json(indent=1).encode(), "application/json")
    store.put(f"{key}/report.md", md.encode(), "text/markdown")
    return report


@app.post("/assessments", dependencies=[Depends(auth)])
def create_from_uri(req: AssessRequest, settings: Settings = Depends(settings_dep)):
    try:
        report = _run(req.source_uri, req.profile, req.include_evidence_snippets, settings)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return report.model_dump(mode="json")


@app.post("/assessments/upload", dependencies=[Depends(auth)])
def create_from_upload(
    files: list[UploadFile] = File(...),
    profile: str = "default",
    settings: Settings = Depends(settings_dep),
):
    with tempfile.TemporaryDirectory(prefix="readiness-upload-") as tmp:
        root = Path(tmp)
        for f in files:
            name = Path(f.filename or "upload").name  # strip any path components
            data = f.file.read(settings.max_doc_bytes + 1)
            if len(data) > settings.max_doc_bytes:
                raise HTTPException(413, f"{name} exceeds READINESS_MAX_DOC_BYTES")
            (root / name).write_bytes(data)
        report = _run(f"file://{root}", profile, False, settings)
    return report.model_dump(mode="json")


@app.get("/assessments/{run_id}", dependencies=[Depends(auth)])
def get_report(run_id: str, settings: Settings = Depends(settings_dep)):
    store = make_blob_store(settings, "reports")
    key = f"{settings.tenant_id}/{run_id}/report.json"
    if not store.exists(key):
        raise HTTPException(404, "unknown assessment")
    return json.loads(store.get(key))


@app.get("/assessments/{run_id}/report.md", dependencies=[Depends(auth)], response_class=PlainTextResponse)
def get_report_md(run_id: str, settings: Settings = Depends(settings_dep)):
    store = make_blob_store(settings, "reports")
    key = f"{settings.tenant_id}/{run_id}/report.md"
    if not store.exists(key):
        raise HTTPException(404, "unknown assessment")
    return store.get(key).decode()
