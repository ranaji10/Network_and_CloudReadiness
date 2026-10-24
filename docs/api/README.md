# HTTP API

`openapi.json` is generated from the FastAPI app by `make openapi` and checked in CI (`scripts/export_openapi.py --check`),
so every change to a route or model shows up in review as a diff of this file. A running instance serves the same
schema at `/openapi.json` and interactive docs at `/docs`.

Versioning: the schema `info.version` equals the package version in `pyproject.toml`. Breaking changes to a route
bump the minor version before 1.0 and the major version after; see `docs/planning/RELEASE_PLAN.md`.

| Route | Purpose |
|---|---|
| `GET /` | Minimal web UI |
| `GET /healthz` | Liveness, unauthenticated |
| `GET /profiles` | Scoring profiles available on this deployment |
| `POST /assessments` | Assess a `source_uri` (`file://`, `gs://`, `s3://`, `gdrive://`) |
| `POST /assessments/upload` | Assess uploaded files |
| `POST /jobs`, `POST /jobs/upload` | Same, but in the background; returns a job record (202) |
| `GET /jobs/{id}` | Job status: queued, running, done (with `report_id`) or failed (with `error`) |
| `GET /assessments/{id}` | Report as JSON |
| `GET /assessments/{id}/report.md` | Report as Markdown |

All routes except `/` and `/healthz` require a bearer token unless `READINESS_AUTH_DISABLED=true` (local use only).

Tenancy: `READINESS_TENANT_TOKENS` is a JSON map `{"<tenant-id>": "<token>"}`; the token a caller presents decides
its tenant, and every report, job and workspace folder is stored under `<tenant-id>/`, so one tenant can never read
another's report (a wrong-tenant id returns 404). `READINESS_API_TOKEN` is the single-tenant form and maps to
`READINESS_TENANT_ID`. Generate tokens with `openssl rand -hex 32` and store the map as a secret
(`READINESS_TENANT_TOKENS` in Secret Manager; set `tenant_tokens_secret = true` in tfvars to mount it).

Async jobs run inside the API process; on Cloud Run the service is deployed with CPU always allocated so a job
finishes after the response. A queue-backed worker for very large packs is a later story.
