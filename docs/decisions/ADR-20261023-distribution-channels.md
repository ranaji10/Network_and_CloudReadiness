# ADR-20261023: Three distribution channels from one repository

Status: accepted

## Context

The tool must run on any organisation's infrastructure. Prospects differ: some are Google Cloud shops
with Gemini Enterprise, some run AWS or on-prem, some only allow a laptop. The owner also wants pushes to
GitHub to reach the agent that already exists on the Google Cloud agent platform, using free credits that
expire in about 50 days.

## Decision

Keep one engine (`readiness.pipeline`) and ship it three ways, all built from the same commit:

| Channel | Artefact | Who it serves | Built by |
|---|---|---|---|
| Container image with the HTTP API and the web UI at `/` | `ghcr.io/<owner>/<repo>:<tag>` and Artifact Registry | any cloud, any VM, Docker Desktop; Cloud Run in our own project | `.github/workflows/release.yml` on `v*` tags; `cloudbuild.yaml` on main |
| Python package | wheel with bundled default config | analysts and integrators: `pip install "readiness[gcp] @ git+<repo url>@<tag>"` | hatch via `uv build`; config force-included |
| ADK agent on Vertex AI Agent Engine | reasoning engine updated in place | Gemini Enterprise users | `cloudbuild.yaml` step `deploy-agent-engine` |

The container is the primary channel because it carries the UI and works everywhere; Agent Engine is the
Google-native channel; the package is for embedding.

## Consequences

- Config must resolve from a checkout, a staged bundle or the wheel (`readiness.config.resolve_default_config_dir`).
- `src/readiness/agents/requirements.txt` mirrors `pyproject.toml`; a test enforces it.
- The flow-builder agent built at the event is retired once the Agent Engine agent is registered in
  Gemini Enterprise; it cannot consume code from GitHub.
- The web UI stays deliberately small (upload, scores, report); richer UI work is tracker API-03 follow-ups.
