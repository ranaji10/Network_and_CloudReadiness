# Roadmap

Phases are sequential in intent but stories inside a phase run in parallel. The tracker
(`docs/planning/TRACKER.md`) is the live state; this file explains the why and the exit criteria.

| Phase | Name | Goal | Status |
|---|---|---|---|
| 0 | Foundation | Engine, surfaces, infrastructure as code and guardrails exist and pass offline tests | done (v0.2.0) |
| 1 | MVP for one analyst | A single analyst assesses a local folder, optionally with a Gemini judge, and the GCP build is green | next |
| 2 | Cloud ingestion and multi-tenant | Drive and GCS sources work, API is protected, Cloud Run behind IAP, agent hosted on Agent Engine | |
| 3 | Recommendations depth and AWS | Bedrock adapter, AWS skeleton validated, catalog expanded, rough cost estimates | |
| 4 | Agentic-AI depth and product polish | Web UI, PDF export, evaluation set for the judge, questionnaire round trip | |
| 5 | Hardening and commercial | SOC2-style controls, SSO, billing, support process | |

## Phase 0: Foundation (done)

Goal: a product skeleton that someone new can run, read and extend in a day.

Delivered in this commit: hexagonal core (`src/readiness`), three scoring domains, recommendation
catalog, CSA CCM v4.1 catalog, redaction and egress guardrails, CLI and API, ADK wrapper,
Dockerfile, `cloudbuild.yaml`, Terraform for GCP plus an AWS skeleton, planning and security docs,
test suite that runs offline.

Exit criteria: `make check` green; `cloudbuild.yaml` passes without cloud resources; every check has
a recommendation; no secret or identifier from fixtures reaches a report or a log.

## Phase 1: MVP usable by one analyst

Goal: one analyst runs a real assessment end to end.

Epics: ING, SCR, LLM, INF, GRD.

| Story | Why |
|---|---|
| INF-02 first green Cloud Build run on the existing trigger | the build is red today |
| INF-03 Cloud Run deploy with `_DEPLOY=true` | prove the deploy path |
| LLM-01 Gemini judge verified end to end on Vertex | first real model call under the guardrails |
| SCR-04 tune signals against three real (anonymised) document packs | the rule engine was written against synthetic docs |
| GRD-04 review redaction output on a real pack before enabling egress | the policy gate before any model sees data |

Exit criteria: a report produced from a real folder is accepted by an analyst as a first-day draft;
Cloud Build green on `main`; egress enabled only after the GRD-04 review is recorded in an ADR.

## Phase 2: Cloud ingestion and multi-tenant

Goal: clients' folders are read where they already live, and more than one tenant can be served.

Epics: ING, API, INF, AGT, GRD.

| Story | Why |
|---|---|
| ING-04 Google Drive source verified on a live Drive | V1's primary input |
| ING-05 GCS source verified | the cloud-native path |
| INF-04 IAP in front of Cloud Run | no public endpoint |
| API-02 per-tenant tokens and report keys | isolation |
| AGT-02 deploy the ADK agent to Agent Engine | continue the V1.1 path |
| GRD-06 VPC Service Controls or equivalent egress perimeter | defence in depth |

Exit criteria: two tenants assessed from Drive in the same deployment with no cross-tenant access;
the chat agent returns the same scores as the CLI.

## Phase 3: Recommendations depth and AWS

Goal: recommendations are specific enough to estimate, and the tool is credible on AWS.

Epics: REC, LLM, INF, MIG.

| Story | Why |
|---|---|
| LLM-03 Amazon Bedrock adapter | model access on AWS |
| INF-06 validate the AWS skeleton and add App Runner | second deployment target |
| REC-03 catalog expansion with sizing hints and documentation links | actionable actions |
| REC-04 rough cost bands per option | the question every client asks |
| MIG-02 Terraform state move drill | prove the migration playbook |

Exit criteria: the same report renders with AWS-first options; an AWS deployment serves the API.

## Phase 4: Agentic-AI readiness depth and product polish

Goal: the tool is pleasant to use without a terminal and the judge is measurably good.

Epics: API, SCR, AGT, REC.

| Story | Why |
|---|---|
| API-03 web UI (upload, progress, report view) | non-technical users |
| API-04 PDF export | client deliverable |
| SCR-05 evaluation set of 20 synthetic packs with expected scores | regression safety for the judge and the rules |
| AGT-03 questionnaire round trip (answer discovery questions, re-score) | the V1 "assisted discovery" flow |
| SCR-06 agentic-AI domain reviewed with two external practitioners | the newest domain needs outside eyes |

Exit criteria: an analyst completes an assessment and a questionnaire round without the CLI; judge
accuracy on the evaluation set is tracked per release.

## Phase 5: Hardening and commercial

Goal: safe to sell and safe to run for others.

Epics: GRD, API, INF, DOC.

| Story | Why |
|---|---|
| GRD-07 SOC2-style control mapping of the tool itself using its own checks | eat the dog food |
| API-05 SSO for the UI and API | enterprise access |
| INF-07 staging and prod environments with separate projects | release safety |
| DOC-05 support and incident process | obligations to clients |

Exit criteria: the tool scores itself above grade B on `security_only`; a paying customer onboarded.

## How V1 and V1.1 map to this

| V1 / V1.1 piece | Where it lives now |
|---|---|
| Google Agent Platform workflow (`legacy/v1_agent_platform/`) | the pipeline in `src/readiness/pipeline.py`; nodes became stages |
| Drive folder id or URL parsing | `adapters/sources/gdrive.py` (`parse_folder_id`) |
| "Ingestion and Semantic Discovery" | `ingestion/extract.py` + `ingestion/classify.py` |
| "Footprint Sufficiency Evaluator", 5 pillars, 20 points each | `config/scoring/cloud_readiness.yaml` pillars; the confidence score is now **evidence coverage** |
| 70% sufficiency gate | `thresholds.high_confidence_coverage` in every profile |
| "CCM Network Controls Curator" (IS-03, 06, 07, 08, 09) | `ccm:` mappings on checks (CCM v4.1 uses the `I&S` prefix) and the discovery items with CAIQ questions |
| "Dynamic Discovery Questionnaire" | Phase 4, AGT-03 |
| "GCP Roadmap Generator" with waves | `gcp_migration` profile plus recommendation options; wave planning is REC-05 |
| V1.1 ADK agents (`legacy/v1.1_adk/`) | `agents/adk_app.py`, a thin wrapper over the same engine; the `global` location fix is kept |
