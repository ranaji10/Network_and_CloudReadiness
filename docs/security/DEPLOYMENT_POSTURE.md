# Deployment posture: how the assessor reaches your documents

This page is written for a client's security or IT team. It answers the question "what does this
tool need from our environment?" The short answer: **nothing inside it**. The assessor runs outside
your network and never connects to your systems. It reads the documents you choose to share.

Decision record: `docs/decisions/ADR-20261103-outside-the-client-network.md`. Enforced by CI.

## What the tool is, and is not

| It is | It is not |
|---|---|
| A document reader and scorer: it extracts text from PDFs, Word, Excel, Markdown and similar files, looks for evidence of controls, and writes a report with scores, actions and open questions | A vulnerability scanner, a network mapper, a configuration auditor or a monitoring agent |
| Hosted by the operator (the consultancy or the internal team running the assessment) on their own laptop, container or cloud project, or on a cloud project you own | Software installed on your servers, workstations or network equipment |
| Reached by the analyst over HTTPS with a bearer token | Something your users or systems connect to |

## The only two ways your documents reach it

| Path | What you do | What the tool holds | How you stop it |
|---|---|---|---|
| **Push** (default) | Hand the document pack to the analyst (upload in the tool's web page, or a shared folder the operator controls) | The files for the duration of the run, then only the report and an audit log with file hashes and counts | Stop sharing; ask for the tenant export and purge (`docs/security/DATA_HANDLING_POLICY.md`) |
| **Pull, read-only** (optional) | Share a Google Drive folder, a Google Cloud Storage prefix or an Amazon S3 prefix with one identity the operator names | A read-only grant you issued; nothing is written back | Revoke the share or the IAM grant. The tool has no other credential to your environment |

Both paths are outbound from you to the operator. There is no inbound connection from the tool into
your network and no connection from your network into the tool is required.

## Questions security teams ask

| Question | Answer |
|---|---|
| Does anything run on our hosts or network? | No. No agent, no collector, no scheduled job, no container. |
| Does it need VPN, a site-to-site tunnel, firewall rules or an allow-listed IP? | No. |
| Does it scan ports, enumerate hosts, or log in to systems (SSH, WinRM, SNMP, LDAP, SMB, RDP)? | No. The dependencies and the source code are checked in CI to make sure no such capability exists: `scripts/check_no_system_access.py`. |
| Does it read our cloud account configuration (IAM, VPCs, security groups)? | No. Only objects under the storage prefix or Drive folder you share. |
| Which credentials do we issue? | None for push. For pull: one read-only grant (Drive `drive.readonly` scope, GCS `objectViewer`, S3 `GetObject`/`ListBucket`) scoped to the shared folder or prefix, revocable at any time. |
| Is our data sent to an AI model? | Not unless agreed in writing. The default is an offline mock model. If a model is enabled, it receives only redacted text (secrets masked, identifiers replaced by pseudonyms) inside delimiters that mark it as untrusted. See `docs/security/LLM_PROVIDER_CHECKLIST.md`. |
| What is stored, where, for how long? | Reports and an audit log under your tenant prefix, on the operator's storage, 90-day lifecycle by default. Raw uploads are deleted after the run. See `docs/architecture/DATA_FLOW.md`. |
| Can we get everything back and have it deleted? | Yes: `readiness tenant export` then `readiness tenant purge`, documented in `docs/security/DATA_HANDLING_POLICY.md`. |
| Can it run entirely on infrastructure we own? | Yes. The same container deploys to a cloud project or a VM you control (`docs/runbooks/DEPLOY_GCP.md`, Docker image). The operator then needs an account on your deployment, nothing else. |
| What about gaps the documents do not cover? | The report lists them as discovery questions (CSA CAIQ wording) for you to answer. The tool never goes looking for the answer on your systems. |

## Reference deployment

```
   your side                                operator side
   ──────────                               ─────────────
   document pack ──(upload over HTTPS)──►  assessor API / web UI
                                                │
   Drive folder / GCS or S3 prefix              │  reads documents, redacts, scores
   shared read-only  ◄──(pull, read-only)──     │
                                                ▼
                                         report + audit log (tenant-prefixed storage)
                                                │
   you  ◄──────── report delivered ─────────────┘
```

No arrow crosses into your network.

## How the boundary is kept

| Control | Where |
|---|---|
| Source schemes allow-listed to document stores: `file`, `gs`, `s3`, `gdrive` | `Settings.allowed_source_schemes`, `adapters/registry.py` |
| No scanning, remote-access or protocol-client library can be added to the project; no raw sockets or shell-outs under `src/readiness`; no network tooling in the container image | `scripts/check_no_system_access.py` in `make check`, Cloud Build and GitHub Actions |
| Drive adapter requests the read-only scope only | `adapters/sources/gdrive.py` |
| Offline by default; model egress needs an explicit operator flag and a signed checklist | `READINESS_ALLOW_LLM_EGRESS`, `guardrails/policy.py` |
| Everything stored is tenant-prefixed, exportable and purgeable | `tenancy.py`, data handling policy |
