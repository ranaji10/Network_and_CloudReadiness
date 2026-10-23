# Documentation map

Start with the three files in bold if you are new.

| Folder | Read it for |
|---|---|
| `product/` | **VISION.md**, PRD.md, **ROADMAP.md**: why the product exists, what v1.0 must do, phases |
| `planning/` | **TRACKER.md** (rendered from `tracker/*.yaml`), README.md on how to claim work, RELEASE_PLAN.md |
| `decisions/` | Architecture decision records, one file per decision, date-based ids |
| `architecture/` | OVERVIEW.md, DATA_FLOW.md, PROVIDER_PORTABILITY.md, MIGRATION_PLAYBOOK.md |
| `security/` | DATA_HANDLING_POLICY.md, THREAT_MODEL.md, GUARDRAILS.md, LLM_PROVIDER_CHECKLIST.md |
| `collaboration/` | WORKING_AGREEMENT.md (humans + agents in parallel), BRANCHING.md, OWNERSHIP.md |
| `runbooks/` | LOCAL_DEV.md, DEPLOY_GCP.md, ONBOARDING.md, INCIDENT_DATA_LEAK.md |
| `legacy/` | V1_SUMMARY.md: what the event-built V1 and the V1.1 ADK agent did and what carried over |

Conventions: Markdown, plain English, tables over prose for reference material, no client names or
account identifiers anywhere (CI enforces it). Agents and people edit docs through the same pull
request flow as code; the tracker is the single place to see who is doing what.
