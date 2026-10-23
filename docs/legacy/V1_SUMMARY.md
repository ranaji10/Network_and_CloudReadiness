# What V1 and V1.1 did, and what carried forward

## V1: Google Agent Platform workflow (Build With Gemini event)

A no-code workflow agent, "Cloud Migration Discovery & GCP Roadmap Generator", built in the Gemini
Enterprise agent flow builder. Export and screenshots: `legacy/v1_agent_platform/`.

| Node | Behaviour |
|---|---|
| Manual trigger | input `folder_identifier`: a Google Drive folder URL or id |
| Ingestion and Semantic Discovery | walk the Drive folder recursively, keep architecture, network, database, contract, inventory, backup, compliance documents; discard minutes, marketing, invoices; emit `technical_inventory` and `retained_files` |
| Footprint Sufficiency Evaluator | score completeness across five pillars (compute, data/storage, networking/identity, security/compliance, cost/licensing), 20 points each, `confidence_score` 0 to 100 plus `pillar_breakdown` and `missing_information` |
| Sufficiency Logic Gate | 70 or above: direct roadmap; else: assisted discovery |
| High Confidence GCP Roadmap Generator | map workloads to GCP services, three migration waves, write `GCP_Cloud_Migration_Roadmap.md` back into the client's Drive folder |
| CCM Network Controls Curator | pick CCM v4.1 Infrastructure Security questions (network security, segmentation, migration, documentation, defence) and summarise missing items |
| Dynamic Discovery Questionnaire | interview the user for the gaps |
| Assisted Discovery Roadmap Generator | merge answers and produce the roadmap |

All nodes used `gemini-3.1-pro-preview` with structured outputs.

## V1.1: ADK code on Vertex AI Agent Engine (half built)

`legacy/v1.1_adk/agent_py_source.rtf` contains an `agent.py` that recreates the same pipeline as Google
ADK `LlmAgent`s (ingestion, evaluator, two roadmap generators, CCM curator, questionnaire) under a
coordinator `GCP_Roadmap_Agent`. Notable: a `GlobalGemini(Gemini)` subclass pinning the Vertex client to
the `global` location because gemini-3 models are only served there. No tools were wired, no tests, no
infrastructure, and the repository held only exports, which is why Cloud Build was failing.

## Carried forward into v0.2

| V1 concept | Now |
|---|---|
| Five migration pillars | `config/scoring/cloud_readiness.yaml` (plus network security and agentic AI domains) |
| Confidence score with a 70 gate | `coverage` per domain and overall; `high_confidence_coverage: 70` in `config/profiles/*.yaml`; the report says whether to act or to collect evidence first |
| CCM / CAIQ questionnaire for gaps | every check maps to CCM control ids; uncovered checks produce discovery recommendations with CAIQ questions from `src/readiness/data/ccm_v4.1.json` |
| Drive folder id parsing | `adapters/sources/gdrive.py::parse_folder_id`, plus GCS, S3 and local sources behind one port |
| Semantic classification | deterministic keyword classifier in `ingestion/classify.py`; LLM classifier is an optional flag |
| `GlobalGemini` | `adapters/llm/gemini.py` and `agents/adk_app.py` default to `GOOGLE_CLOUD_LOCATION=global` |
| Coordinator loop (score, ask, re-run) | `agents/prompts.py` coordinator with one tool over the same pipeline |
| GCP service mapping | `config/recommendations/catalog.yaml`, now with AWS and open-source options per check |

## Dropped, and why

| V1 behaviour | Reason |
|---|---|
| Writing the roadmap into the client's Drive folder by default | writes to client systems without an explicit, audited choice; reports now go to the operator's workspace or bucket, tenant-scoped |
| Sending whole documents to the model un-redacted | confidentiality guardrails: redaction, egress flag, untrusted delimiting |
| GCP-only prompts and service mapping | the product must recommend GCP, AWS or open source neutrally; provider preference is a profile setting |
| Scoring inside prompts | scores are now deterministic from YAML and reproducible; the model only refines verdicts when explicitly enabled |
| Platform-specific workflow definition as the source of truth | code, config and tests in git; the ADK agent is a thin optional wrapper |
