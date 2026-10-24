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
| `GET /assessments/{id}` | Report as JSON |
| `GET /assessments/{id}/report.md` | Report as Markdown |

All routes except `/` and `/healthz` require `Authorization: Bearer <READINESS_API_TOKEN>` unless
`READINESS_AUTH_DISABLED=true` (local use only).
