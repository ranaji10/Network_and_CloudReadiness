# Product requirements: v1.0 of the rebuilt assessor

Status of this document: baseline for Phases 1 and 2 of `ROADMAP.md`. The repository at v0.2.0 is
the "foundation" release: the engine, surfaces and infrastructure exist and are tested offline, but
nothing has yet been run against a live cloud account or a real model.

## 1. Users and jobs

| User | Job to be done |
|---|---|
| Analyst at a consultancy or MSP | Assess a new client from their document folder and produce a report with actions and discovery questions |
| Internal IT lead | Run a quarterly readiness check and track whether the score improves |
| Engineer maintaining the tool | Add or tune a check, a product option or a provider adapter without reading the whole codebase |

## 2. Functional requirements

### 2.1 Ingestion (`src/readiness/adapters/sources/`, `src/readiness/ingestion/`)

| Id | Requirement | v0.2.0 state |
|---|---|---|
| F-ING-1 | Read a local folder recursively; refuse to follow links outside the root | done (`local_fs.py`) |
| F-ING-2 | Read a Google Cloud Storage prefix | written, untested live (`gcs.py`) |
| F-ING-3 | Read an S3 prefix | written, untested live (`s3.py`) |
| F-ING-4 | Read a Google Drive folder by id or URL, including Google-native docs | written, untested live (`gdrive.py`) |
| F-ING-5 | Extract text from PDF, DOCX, XLSX, Markdown, text, CSV, JSON, YAML | done (`extract.py`) |
| F-ING-6 | Classify each document into a coarse class and skip noise | done, keyword based (`classify.py`); LLM refinement optional |
| F-ING-7 | Enforce per-document size and text limits | done (`Settings.max_doc_bytes`, `max_text_chars`) |

### 2.2 Scoring (`config/scoring/`, `config/profiles/`, `src/readiness/scoring/`)

| Id | Requirement | v0.2.0 state |
|---|---|---|
| F-SCR-1 | Three scoring domains: `network_security`, `cloud_readiness`, `agentic_ai_readiness` | done, 59 checks |
| F-SCR-2 | Each check maps to CSA CCM v4.1 control ids; catalog shipped in the package | done (`src/readiness/data/ccm_v4.1.json`) |
| F-SCR-3 | Rule engine: signals, strong signals, negative signals, four statuses | done (`engine.py`) |
| F-SCR-4 | Posture score and evidence coverage reported separately per pillar, domain and overall | done |
| F-SCR-5 | Profiles select domains, weights, thresholds and provider preference | done (`default`, `gcp_migration`, `security_only`) |
| F-SCR-6 | Optional LLM judge refines rule verdicts when confident | hook done, tested with mock only |
| F-SCR-7 | A new check or pillar is a YAML edit; a config typo fails fast | done (pydantic validation) |

### 2.3 Recommendations (`config/recommendations/catalog.yaml`, `src/readiness/recommend/`)

| Id | Requirement | v0.2.0 state |
|---|---|---|
| F-REC-1 | Every failed or partial check yields an action with GCP, AWS, open-source and/or process options | done, catalog covers all 59 checks |
| F-REC-2 | Every check without evidence yields a discovery item with CAIQ questions | done |
| F-REC-3 | Options are ordered by the profile's provider preference | done |
| F-REC-4 | Priority reflects points lost, pillar weight, impact and effort | done |

### 2.4 Report and surfaces

| Id | Requirement | v0.2.0 state |
|---|---|---|
| F-RPT-1 | Markdown and JSON report with scores, method, documents, findings, actions, discovery, data handling | done (`report/markdown.py`) |
| F-RPT-2 | Evidence snippets only when explicitly requested | done |
| F-CLI-1 | `readiness assess|profiles|checks|controls|redact|serve` | done (`cli.py`) |
| F-API-1 | `POST /assessments` (URI or upload), `GET /assessments/{id}`, `/report.md`, `/profiles`, `/healthz` | done (`api/app.py`) |
| F-API-2 | Bearer token auth, designed to sit behind Cloud Run IAM or IAP | done |
| F-AGT-1 | ADK agent exposing the assessment as a tool, hostable on Agent Engine | wrapper done (`agents/adk_app.py`), not deployed |

## 3. Non-functional requirements

| Id | Requirement | How it is met |
|---|---|---|
| N-1 | Offline by default; no network call unless `READINESS_ALLOW_LLM_EGRESS=true` | `Settings.require_llm_egress`, mock provider default |
| N-2 | Secrets always masked; identifiers pseudonymised before any model call | `guardrails/redaction.py`, `config/redaction.yaml`, `GuardedLLM` |
| N-3 | Document text treated as untrusted in prompts | `guardrails/policy.py` preamble and delimiters |
| N-4 | Audit log carries hashes and counts, never content | `guardrails/audit.py` refuses long string fields |
| N-5 | Tenant isolation of outputs | workspace and blob keys prefixed by `tenant_id` |
| N-6 | Provider portability: no project ids, bucket names or accounts in code or IaC | ports/adapters, Terraform variables, `scripts/check_portability.py` |
| N-7 | Reproducible builds and a CI gate that runs locally | `uv.lock`, `make check`, `cloudbuild.yaml` |
| N-8 | Assessment of ~50 documents completes in under two minutes offline | rule engine is linear in text size |

## 4. Out of scope for v1.0

- Live scanning of networks or cloud accounts.
- Multi-language documents beyond English.
- Fine-grained per-user permissions inside the API (one token per tenant deployment is enough).
- A full web UI (Phase 4).
- Automatic cost estimates for recommendations (Phase 3).

## 5. Open questions

| Question | Owner | Needed by |
|---|---|---|
| Which model provider do we default to once egress is allowed: Gemini on Vertex (same account) or Claude? | product owner | Phase 1 |
| Do clients accept pseudonymised text being sent to a model, or do some need full offline mode only? | product owner | Phase 2 |
| Where do reports live long term: tenant bucket only, or also a database for trend lines? | engineering | Phase 2 |
| Is the CSA CCM licence compatible with commercial redistribution of the catalog JSON? | legal | Phase 5 |
| Should the discovery questionnaire be answered in-chat (V1 behaviour) or via a form upload? | product owner | Phase 4 |
