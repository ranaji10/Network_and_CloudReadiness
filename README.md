# Network & Cloud Readiness Assessor

> **Status: v0.2.0 foundation.** The engine, guardrails, infrastructure-as-code and planning docs are in
> place. Cloud Build should now be green on every push with `_DEPLOY=false` (quality gate + container
> build only). Nothing is deployed until `_DEPLOY=true` is set on the trigger. See
> [docs/planning/README.md](docs/planning/README.md) for the roadmap and tracker.

An externally deployable tool that reads a business's existing documents (local folder, Google Cloud
Storage, Amazon S3 or Google Drive), scores them against configurable control frameworks and produces:

- a **Network Security** score,
- a **Cloud Readiness** score (the five V1 pillars: compute, data, networking/identity, security/compliance, cost/licensing),
- an **Agentic AI Readiness** score,
- an **evidence coverage** figure per area (the V1 "confidence score": how much of the picture the documents actually cover),
- prioritised **actions** with product options for **GCP, AWS and open source**, and
- **discovery questions** (CSA CAIQ v4.1) for every control the documents do not cover.

Everything runs offline by default. A real model (Gemini or Claude) is only called when an operator
sets `READINESS_ALLOW_LLM_EGRESS=true`, and only after redaction.

## 5-minute quickstart

```bash
uv sync --group dev          # Python 3.12 venv with dev tools
make demo                    # assess the synthetic sample, print the Markdown report
make check                   # lint + tests + repo guardrails (what CI runs)
make serve                   # HTTP API on :8080 with auth disabled (local only)
docker compose up --build    # same API in a container; put documents in ./data
```

Assess your own folder:

```bash
uv run readiness assess /path/to/client-docs --profile default --snippets
uv run readiness assess gs://bucket/prefix --profile gcp_migration     # needs: uv sync --extra gcp
```

Reports land in `./workspace/<tenant>/<run-id>/` (git-ignored): `report.md`, `report.json`, `audit.jsonl`.

## Repository map

| Path | What it is |
|---|---|
| `src/readiness/` | The Python package: `pipeline.py` (orchestration), `scoring/`, `recommend/`, `guardrails/`, `ingestion/`, `ports/` + `adapters/` (cloud-neutral boundary), `api/`, `cli.py`, `agents/` (optional ADK wrapper) |
| `config/` | **All tunable product behaviour**: `profiles/` (which domains, weights, thresholds), `scoring/` (pillars, checks, signals, CCM mappings), `recommendations/catalog.yaml` (actions and GCP/AWS/OSS options), `redaction.yaml` |
| `tests/` | Pytest suite; `tests/fixtures/synthetic_acme/` is invented sample data |
| `infra/` | Terraform (`gcp/` primary, `aws/` skeleton), `scripts/bootstrap_gcp.sh` |
| `cloudbuild.yaml`, `Dockerfile`, `.github/workflows/ci.yml` | CI/CD. Cloud Build and GitHub Actions run the same quality gate |
| `docs/` | `product/` (vision, roadmap), `planning/` (tracker), `decisions/` (ADRs), `architecture/`, `security/`, `collaboration/`, `runbooks/`, `legacy/` |
| `reference/csa-ccm-caiq-v4.1/` | Cloud Security Alliance CCM/CAIQ source material |
| `legacy/` | V1 Agent Platform export and V1.1 ADK source, kept for reference (see [docs/legacy/V1_SUMMARY.md](docs/legacy/V1_SUMMARY.md)) |
| `scripts/` | Repo tooling: control catalog build, tracker render, portability and client-data checks |

## How scoring works

1. Documents are extracted to text, classified (network, policy, inventory, ...) and **redacted** before anything else happens.
2. Each **profile** (`config/profiles/*.yaml`) lists domains with weights; each **domain** (`config/scoring/*.yaml`) lists pillars with weights and checks with points, evidence signals and CSA CCM control ids.
3. A check is **PASS** on two distinct signals or one strong signal, **PARTIAL** on one signal, **FAIL** on an explicit negative statement, otherwise **NO EVIDENCE**.
4. Posture score = earned points / available points, weighted by pillar and domain. Coverage = share of checks with any evidence.
5. Optionally an LLM judge refines verdicts per pillar; it only ever sees redacted, delimited text and must answer in a fixed schema.
6. Failed or partial checks become prioritised actions from the catalog; uncovered checks become discovery questions from CAIQ.

Change weights, add checks or products by editing YAML. No code change is needed. See the recipes in [CLAUDE.md](CLAUDE.md).

## Where to start reading

1. [docs/planning/README.md](docs/planning/README.md) for the roadmap, tracker and how work is planned.
2. [docs/collaboration/WORKING_AGREEMENT.md](docs/collaboration/WORKING_AGREEMENT.md) for how people and agents work in parallel here.
3. [docs/runbooks/ONBOARDING.md](docs/runbooks/ONBOARDING.md) for a first-day checklist.
4. [docs/architecture/OVERVIEW.md](docs/architecture/OVERVIEW.md) and [docs/security/GUARDRAILS.md](docs/security/GUARDRAILS.md) before touching code.

## Attribution

The Cloud Controls Matrix (CCM) v4.1 and Consensus Assessments Initiative Questionnaire (CAIQ) v4.1 in
`reference/` are Cloud Security Alliance material, used under their licence terms. The generated
`src/readiness/data/ccm_v4.1.json` is derived from them and carries the same attribution.

## Running it in your organisation (distribution channels)

| You are | Use | How |
|---|---|---|
| Any cloud, VM or laptop with Docker | Container with API + web UI | `docker run -p 8080:8080 -e READINESS_AUTH_DISABLED=true ghcr.io/<owner>/<repo>:<tag>` then open http://localhost:8080 (published on `v*` tags by `.github/workflows/release.yml`) |
| Google Cloud | Cloud Run via Cloud Build | `docs/runbooks/DEPLOY_GCP.md` (`_DEPLOY=true`) |
| Gemini Enterprise users | ADK agent on Vertex AI Agent Engine | `docs/runbooks/DEPLOY_AGENT_ENGINE.md` (`_DEPLOY_AGENT=true`; registered once in Gemini Enterprise, updated on every main build) |
| Python integrators | Package with bundled default config | `pip install "readiness[gcp] @ git+https://github.com/<owner>/<repo>@<tag>"` then `readiness assess <folder>` |

All channels are built from the same commit and run the same engine, so scores never differ by channel.
