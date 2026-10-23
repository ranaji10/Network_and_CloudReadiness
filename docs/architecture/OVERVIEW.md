# Architecture overview

## Components

```
                 ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  surfaces       │  CLI         │   │  HTTP API    │   │  ADK agent   │
                 │  cli.py      │   │  api/app.py  │   │  agents/     │
                 └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
                        └──────────────────┼──────────────────┘
                                           ▼
                                ┌─────────────────────┐
  orchestration                 │  pipeline.run_assessment │
                                └──────────┬──────────┘
          ┌──────────────┬─────────────────┼─────────────────┬──────────────┐
          ▼              ▼                 ▼                 ▼              ▼
   ┌────────────┐ ┌────────────┐   ┌──────────────┐   ┌────────────┐ ┌────────────┐
   │ ingestion  │ │ guardrails │   │ scoring      │   │ recommend  │ │ report     │
   │ extract    │ │ redaction  │   │ profiles     │   │ engine     │ │ markdown   │
   │ classify   │ │ policy     │   │ engine       │   │ + catalog  │ │            │
   └─────┬──────┘ │ audit      │   │ catalog(CCM) │   └────────────┘ └────────────┘
         │        └─────┬──────┘   └──────┬───────┘
         ▼              ▼                 ▼
   ┌──────────────────────────────────────────────────────────┐
   │ ports: DocumentSource · LLMProvider · BlobStore · SecretStore │
   └──────────────────────────┬───────────────────────────────┘
                              ▼
   ┌──────────────────────────────────────────────────────────┐
   │ adapters (lazy cloud SDK imports)                         │
   │ sources: local_fs gcs s3 gdrive · llm: mock gemini anthropic │
   │ storage: local gcs s3 · secrets: env gcp aws              │
   └──────────────────────────────────────────────────────────┘
          config/ (YAML): profiles · scoring · recommendations · redaction
```

| Component | Responsibility | Key files |
|---|---|---|
| Surfaces | Accept a source and a profile, return a report | `cli.py`, `api/app.py`, `agents/adk_app.py` |
| Pipeline | The only orchestration; identical for all surfaces | `pipeline.py` |
| Ingestion | bytes to text (pdf, docx, xlsx, text/structured), heuristic classification | `ingestion/extract.py`, `ingestion/classify.py` |
| Guardrails | redaction, egress policy, prompt wrapping, audit | `guardrails/` |
| Scoring | load profile and domains, evaluate checks by signals, optional LLM judge, grades, composite | `scoring/` |
| Recommend | failed/partial checks to actions with provider options; unknown checks to CAIQ discovery questions | `recommend/engine.py` |
| Report | Markdown deliverable; JSON is the pydantic model | `report/markdown.py`, `models.py` |
| Ports/adapters | the cloud-neutral boundary | `ports/__init__.py`, `adapters/` |
| Config | all tunables | `config/` |

## Request flow

**CLI**: `readiness assess <source> --profile <id>` builds `Settings` from env, calls `run_assessment`,
prints Markdown, writes `workspace/<tenant>/<run>/`.

**API**: `POST /assessments` (JSON `source_uri`) or `POST /assessments/upload` (multipart, written to a
temporary folder, assessed as a local source). Result stored through `BlobStore` under
`<tenant>/<run>/report.{json,md}`; `GET /assessments/{run}` reads it back. Bearer token required.

**ADK agent**: `agents/adk_app.py` exposes one tool, `run_readiness_assessment`, that calls the same
pipeline and returns a compact summary. The coordinator prompt handles the "coverage below threshold,
ask discovery questions, re-run" loop from V1.

## Inside `run_assessment`

1. load profile and its domains (pydantic-validated YAML)
2. open the source through the registry (scheme allow-list)
3. extract, classify, record metadata in the audit log
4. **redact every document** (secrets always; identifiers per mode)
5. score each domain with rules; if `use_llm_judge`, pass each pillar through `GuardedLLM`
6. composite score and coverage per profile weights
7. recommendations from the catalog, sorted by lost points x weights x impact / effort
8. render Markdown; write outputs; audit `run.end`

## Where configuration lives

| Concern | Where | Changed by |
|---|---|---|
| Runtime environment (provider, model, buckets, flags) | environment variables, `.env` locally, Cloud Run env from Terraform | operator |
| Scoring behaviour | `config/profiles/`, `config/scoring/` | product owner, via PR |
| Recommendations | `config/recommendations/catalog.yaml` | product owner, via PR |
| Redaction rules | `config/redaction.yaml` | security owner, via PR |
| Control catalog | `src/readiness/data/ccm_v4.1.json` generated from `reference/` | `make catalog` when CSA publishes a new version |
