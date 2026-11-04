# Runbook: support and incident process for customers

Written for the operator organisation (the consultancy, MSP or internal IT team) that runs the assessor for
clients. It can be attached to a client agreement as an annex: everything a client needs to know about how to
reach support, how fast we respond and how incidents are handled is on this page. Related:
`SECURITY.md`, `docs/runbooks/INCIDENT_DATA_LEAK.md`, `docs/runbooks/TENANT_OFFBOARDING.md`,
`docs/security/DATA_HANDLING_POLICY.md`, `docs/security/DEPLOYMENT_POSTURE.md`.

> **Status of the numbers.** Every value tagged `[proposed]` (response and mitigation targets, support hours,
> the post-incident report deadline, the deprecation notice) is a proposal pending sign-off by the product
> owner. Treat them as sensible defaults for a small operator, not as commitments, until the tag is removed.

<!-- DECISION: the product owner has not yet set the SLA numbers, the support hours, the out-of-hours rule,
     the contact alias, the post-incident report deadline or the deprecation notice period. Everything tagged
     [proposed] below is a placeholder. When they are decided: replace the values, remove the [proposed] tags,
     delete this comment and the status note above, and bump the "Last reviewed" line at the bottom. -->

## 1. Scope

### What is supported

| Component | Channel (per `README.md`) | What support covers |
|---|---|---|
| Hosted API and web UI | Cloud Run via Cloud Build (`docs/runbooks/DEPLOY_GCP.md`), or the container image on any Docker host | Availability, correctness of scores and reports for a given version, authentication and tenancy, export and purge of a tenant's data |
| CLI package (`readiness`) | `pip install` from a tagged release | Installation on a supported Python, documented commands, report output for a given version and config |
| MCP server (`readiness mcp`) | MCP clients such as Claude Code or Claude Desktop (`docs/runbooks/MCP_SERVER.md`) | The three tools (`run_readiness_assessment`, `list_profiles`, `list_checks`) behaving as documented |
| ADK agent | Vertex AI Agent Engine for Gemini Enterprise users (`docs/runbooks/DEPLOY_AGENT_ENGINE.md`) | The agent reaching the same engine and producing the same scores as the other channels |
| Bundled configuration | `config/profiles/`, `config/scoring/`, `config/recommendations/` | Documented profiles, checks and recommendation catalog at the released version |

All channels are built from the same commit and run the same engine, so a defect reproduced on one channel is
treated as one defect, not four.

### What is not supported

| Out of scope | Why | Who to ask instead |
|---|---|---|
| The content of the client's documents: what they say, whether a control actually exists, whether a score "should" be higher | The tool reports evidence found in documents; it does not audit systems (`docs/product/VISION.md`, non-goals) | The client's own security or IT team, or a consulting engagement |
| The client's cloud accounts, networks or systems | Nothing runs inside the client's environment and the tool holds no credential to it (`docs/security/DEPLOYMENT_POSTURE.md`) | The client's cloud provider or internal operations team |
| Availability, latency or output quality of a third-party model provider | The provider is chosen and contracted per deployment (`docs/security/LLM_PROVIDER_CHECKLIST.md`); the default is an offline mock | The provider's own support; support will confirm the deployment's egress setting and help switch back to `mock` |
| Forks, local modifications to the scoring YAML, or versions outside the supported list (section 7) | Scores depend on the config and version; unsupported combinations cannot be reproduced | Upgrade to a supported version, or re-run with the bundled config to reproduce |
| Interpretation of the report as a certification or audit opinion | Scores are planning inputs, never certifications | A formal audit |

## 2. Severity levels

| Severity | Definition | Examples |
|---|---|---|
| **Sev-1** | Confirmed or suspected exposure of client data, or the service unavailable for all tenants | A client document, extracted text, report, pseudonym map or secret found in git history, a public bucket, a ticket, a chat or an external model without approval; `/healthz` failing for every tenant; the API returning another tenant's report; a leaked `READINESS_API_TOKEN` or tenant token |
| **Sev-2** | One tenant blocked, a delivered report carries wrong scores, or model egress is misconfigured | A tenant's token rejected or its jobs stuck in `queued`; a scoring defect that changed the posture or coverage figure in a report already handed to a client; `READINESS_ALLOW_LLM_EGRESS=true` on a deployment whose provider checklist is not signed; redaction mode not applied as configured |
| **Sev-3** | Degraded behaviour with a workaround | PDF rendering returns 501 while Markdown and JSON work; one document format fails to extract and the client can convert it; a slow run on a large pack; a recommendation that lists a retired product name |
| **Sev-4** | Questions and feature requests | "How do I add a profile?"; a request for a new check or a new source adapter; wording improvements in the report |

Rules:

- When unsure between two levels, pick the higher one. Support may downgrade after triage and says why.
- Any Sev-1 that involves client data invokes `docs/runbooks/INCIDENT_DATA_LEAK.md` immediately, before anything else on this page.
- A Sev-2 wrong-score defect covers reports already delivered; the same defect found before delivery is Sev-3.

## 3. Service levels

| Severity | First response `[proposed]` | Mitigation or resolution target `[proposed]` | Status updates (section 6) |
|---|---|---|---|
| Sev-1 | 1 hour, any time | Mitigation within 4 hours; resolution and post-incident report follow | Every 2 hours until mitigated |
| Sev-2 | 4 support hours | Mitigation within 2 business days; fix in the next patch release | Daily |
| Sev-3 | 1 business day | Workaround confirmed in the first response; fix in the next scheduled release | On change of state |
| Sev-4 | 2 business days | Answered, or placed on the roadmap (`docs/product/ROADMAP.md`) with the tracker story id | None after the answer |

| Term | Meaning `[proposed]` |
|---|---|
| Support hours | Business days, 09:00 to 18:00 in the operator's time zone named in the client agreement; public holidays of that location excluded |
| Business day | A day inside support hours; a target of "1 business day" received at 17:00 on a Friday is due 17:00 the next business day |
| Out of hours | Only Sev-1 is worked out of hours. A report received out of hours at Sev-2 or below is acknowledged automatically and its clock starts at the next support-hours opening |
| First response | A human reply from the first responder confirming severity, the ticket reference and the next update time; the automatic acknowledgement does not count |
| Mitigation | The client can work again (service restored, data spread stopped, workaround in place), even if the root cause is still open |
| Resolution | The fix is released on a supported version, or the question is answered |

Targets are measured from the time the report reaches the intake channel (section 4), not from when it was written.
Time spent waiting for information only the client can give (for example a tenant id or a run id) pauses the clock.

## 4. Channels and intake

### How a client reports

| Channel | Use for | Notes |
|---|---|---|
| Named support contact | Everything, during support hours | A person named in the client agreement; a deputy is named for absences |
| Support e-mail alias | Everything except security reports | `<support-alias>` at the operator's domain, set in the client agreement, never in this repository. Creates the ticket and sends the automatic acknowledgement |
| Private vulnerability or exposure report | Suspected vulnerabilities and suspected data exposure | The private channel in `SECURITY.md` (the organisation's private channel, or GitHub private vulnerability reporting if enabled). Never a public issue, never the shared e-mail alias, never a chat with other tenants |
| Out-of-hours line | Sev-1 only | Set in the client agreement if the operator offers one; otherwise the support alias with `SEV-1` in the subject, which pages the first responder |

### What to include

| Include | Never include |
|---|---|
| Tenant id and, if known, run id (`report_id` or job id from the API, the run folder name from the CLI or MCP server) | Document content, extracted text, evidence snippets, report sections that name documents |
| Time of the event in UTC, and the channel (API, web UI, CLI, MCP server, ADK agent) | Pseudonym mapping files (`pseudonym_mapping.local.json`) |
| Tool version (`tool_version` in the report, or `readiness --version`) | API tokens, tenant tokens, model API keys |
| What was expected and what happened, in one paragraph | Other tenants' names or ids |
| For a scoring question: the check id (`NS-`, `CR-`, `AI-`) and the profile id | Screenshots of a report that shows document names (use the share-safe report, section 9) |

Security reports follow `.github/ISSUE_TEMPLATE/security.md`: affected version or commit, the component, steps to
reproduce with synthetic data, and impact.

### Acknowledgement

| Step | Who | When |
|---|---|---|
| Automatic acknowledgement with a ticket reference | Intake system | Immediately |
| Severity confirmed, next update time given | First responder | Within the first-response target |
| Severity change explained to the client | First responder | At the next update |

## 5. Escalation path

Roles only, never people; the current holder of each role is recorded in the operator's on-call rota, not in this
repository. Reviewer roles are described in `docs/collaboration/OWNERSHIP.md`.

| Level | Role | Takes over when | What they own |
|---|---|---|---|
| 1 | First responder | Every ticket | Acknowledge, confirm severity, reproduce with synthetic data, apply a documented workaround or rollback (`docs/planning/RELEASE_PLAN.md`), keep the client updated |
| 2 | Service owner | Any Sev-1 at once; a Sev-2 not mitigated inside its target; any ticket needing a release, a config change or a Terraform change | Decide mitigation versus fix, approve a hotfix release, coordinate with the infra owner for deployments, sign off the post-incident report |
| 3 | Security owner | Any Sev-1 involving client data at once; any suspected vulnerability; any question about redaction, egress or tenancy | Run `docs/runbooks/INCIDENT_DATA_LEAK.md`, decide client and legal notification, review guardrail changes (`docs/security/GUARDRAILS.md`) |

Immediate escalations, no waiting for a target to lapse:

| Trigger | Action |
|---|---|
| Suspected client-data exposure (Sev-1) | Security owner paged; `docs/runbooks/INCIDENT_DATA_LEAK.md` section 0 ("stop the spread") executed within 15 minutes, before triage is complete |
| Request to export or delete a tenant's data | Service owner; follow `docs/runbooks/TENANT_OFFBOARDING.md` (export, verify manifest, deliver, dry-run purge, purge, confirm, record) |
| Model egress found enabled without a signed provider checklist | Service owner; set `READINESS_ALLOW_LLM_EGRESS=false` and redeploy, then treat as Sev-2 and review what was sent |
| Leaked API or tenant token | Service owner; rotate per the table in `docs/runbooks/INCIDENT_DATA_LEAK.md` section 1 |

A client may ask for escalation at any time by replying to the ticket with "escalate"; the next level responds within
the first-response target for the ticket's severity.

## 6. Communication

### Status updates

| Severity | Cadence | Content of each update |
|---|---|---|
| Sev-1 | Every 2 hours until mitigated, then daily until resolved `[proposed]` | What is known, what has been done, what is next, next update time |
| Sev-2 | Daily `[proposed]` | Same |
| Sev-3 | On change of state (workaround confirmed, fix scheduled, fix released) | What changed |
| Sev-4 | None after the answer | n/a |

Updates go to the reporter and the named client contact, through the ticket. A client-wide notice (all tenants of a
deployment) is sent only for a Sev-1 affecting all tenants, by the service owner, and never names another tenant.

### Post-incident report

Delivered to each affected client within 5 business days of resolution for Sev-1 and Sev-2 `[proposed]`,
reviewed by the service owner, and by the security owner when client data was involved.

| Section | Content |
|---|---|
| Summary | One paragraph: what happened, who was affected, current state |
| Timeline | UTC timestamps: detection, acknowledgement, escalations, mitigation, resolution, client notifications |
| Impact per tenant | For the receiving tenant only: which runs, reports or data were affected and how; what was exposed and for how long, if anything |
| Root cause | The technical and process cause, in plain English |
| Actions | Fixes released (version), guardrails or checks added (`docs/security/GUARDRAILS.md`, `.gitleaks.toml`, `config/redaction.yaml`), process changes, each with an owner role and a date |
| Open items | Anything still outstanding and when the client will hear about it |

Internally, every Sev-1 and Sev-2 gets a tracker story in the `GRD` or the owning epic with the root cause and the fix,
per `docs/runbooks/INCIDENT_DATA_LEAK.md` section 4.

### What is never shared

| Never shared with a client | Reason |
|---|---|
| Another tenant's identity, tenant id, runs, reports, impact or existence | Tenant isolation (`docs/security/DATA_HANDLING_POLICY.md`) |
| Document content, extracted text, evidence snippets, pseudonym mappings, in any ticket, update or report | Client-confidential data stays in the tenant workspace; logs and audit records carry metadata only |
| Secrets, tokens or key material, even rotated ones | Treat as compromised, rotate, never quote |
| Details of a vulnerability before the fix is released on a supported version | Protects other tenants; the post-incident report follows the release |

## 7. Maintenance and releases

| Topic | Rule |
|---|---|
| Planned maintenance | Notice to all client contacts at least 2 business days ahead `[proposed]`, with the window in UTC and the expected effect (read-only, unavailable, none). Maintenance that may interrupt a running job is scheduled outside support hours where possible. Jobs are re-run free of charge if interrupted |
| Release announcements | Every tagged release (`vX.Y.Z`) gets release notes with the deployed image digest and the revision name (`docs/planning/RELEASE_PLAN.md`); scoring changes name the domain or profile version that moved and why, so a client can tell a score change caused by a release from one caused by their documents |
| Supported versions | Only the `main` branch and the latest tagged release receive fixes (`SECURITY.md`). A hosted deployment always runs the latest tagged release or a hotfix of it |
| Rollback | Cloud Run traffic split to the previous revision; a rolled-back release never changes an already produced report, which is re-run if a client needs a corrected one |
| Deprecation | A route, CLI command, MCP tool, profile or check is marked deprecated in the release notes at least one minor release and at least 30 days `[proposed]` before removal; the replacement is named in the same note |
| Scoring changes | A change to weights, points or thresholds bumps the domain or profile version; a client comparing quarter-on-quarter runs is told which version each run used (`tool_version` and profile `version` in the report) |

## 8. Data requests

Policy: `docs/security/DATA_HANDLING_POLICY.md`. Procedure: `docs/runbooks/TENANT_OFFBOARDING.md`. Both are
tenant-scoped: everything stored for a client sits under its `<tenant_id>/` prefix, so one command covers it.

| Request | How it is handled | Target `[proposed]` |
|---|---|---|
| Export ("give us everything you hold") | `readiness tenant export <tenant_id>` for the workspace and reports store, and again with `--store uploads`; the manifest (keys, sizes, sha256) is verified and kept as the record; the zips are delivered over the channel in the client agreement, never attached to a ticket or e-mail | Delivered within 5 business days |
| Deletion ("delete everything") | Export first unless the client declines in writing; dry-run purge; purge with `--yes` for both stores; hard delete of all object versions; confirmation that the dry run reports 0 objects; dates recorded in the engagement log | Confirmed within 5 business days of the export being accepted (or of the written decline) |
| Deletion of one run | Same purge scoped to the run folder, on request; the rest of the tenant is untouched | 2 business days |
| Retention question | Default 90-day lifecycle on uploads and reports buckets; raw uploads deleted after the run; local workspaces deleted at engagement end; pseudonym mappings never leave the analyst machine; audit logs hold hashes and counts only | Answered in the first response |
| "Was our data sent to a model?" | The deployment's `READINESS_LLM_PROVIDER` and `READINESS_ALLOW_LLM_EGRESS` values, and the signed provider checklist if any, are quoted; the run's `audit.jsonl` shows whether any model call happened | Answered in the first response |
| Personal-data request from an individual (subject access) | Forwarded to the client, who is the data controller; the operator as custodian exports or purges on the client's instruction | Forwarded within 1 business day |

The tool keeps nothing else about a client: hosted agent sessions are not stored by this tool, and model
providers are governed by the terms recorded in `docs/security/LLM_PROVIDER_CHECKLIST.md`.

## 9. What the client can check themselves

| Check | How | What it tells you |
|---|---|---|
| Is the service up? | `GET /healthz` on the deployment URL (unauthenticated) | Liveness. A failure here for every tenant is Sev-1; report it with the time in UTC |
| What happened in my run? | `audit.jsonl` in the run folder (CLI, MCP server) or on request from support for a hosted run | Every event with run id, tenant, document ids, hashes, counts and classes; no content. Shows which documents were read, how they were classified, and whether any model was called |
| Can I share this report outside my organisation? | Re-run with `readiness assess --share-safe` or `share_safe=true` on the API | A share-safe report masks identifiers, drops snippets and labels documents `doc-<hash>`; its data-handling section says so. Never hand-edit a normal report instead |
| Which version produced this report? | `tool_version` and the profile `version` in the report | Lets you trace a score change to a release (section 7) rather than to your documents |
| What does the tool need from our network? | `docs/security/DEPLOYMENT_POSTURE.md` | Nothing inside it. The page answers the questions security teams usually ask |
| Which profiles and checks apply? | `GET /profiles`, `readiness profiles`, `readiness checks <domain>`, or the MCP `list_profiles` and `list_checks` tools | The scoring frame used, so a question about a score can name the check id |
| Is my token scoped to my tenant? | Request a report id that is not yours: the API returns 404 | Tenancy isolation in action; a 200 for another tenant's id is Sev-1 |

Last reviewed: 2026-11-03. Owner role: service owner, with the security owner for sections 2, 5, 6 and 8.
