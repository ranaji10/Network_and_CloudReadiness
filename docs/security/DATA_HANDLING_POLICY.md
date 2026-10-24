# Data handling policy

This tool is run by one organisation (the operator) against documents belonging to another (the client).
Both must be protected. This page says what data exists, where it may live, for how long, and who deletes it.

## Data classes

| Class | Examples | Owner |
|---|---|---|
| Public | this repository's code and docs, CSA CCM/CAIQ material | anyone |
| Internal | roadmap, tracker, unpublished scoring tuning, cost figures for the operator | operator |
| Client-confidential | every document the tool reads, extracted text, classifications, evidence snippets, reports, pseudonym mappings, audit logs that name documents | client (operator is custodian) |
| Secrets | API keys, API tokens, service-account keys, Terraform state, anything in `.env` or `*.tfvars` | whoever issued them |

## Where each class may live

| Location | Public | Internal | Client-confidential | Secrets |
|---|---|---|---|---|
| Git (this repo) | yes | yes | **never** | **never** |
| Developer machine `workspace/`, `data/` | yes | yes | yes, git-ignored, delete after engagement | only `.env`, git-ignored |
| Uploads / reports buckets (`infra/terraform/gcp`) | n/a | n/a | yes, tenant-prefixed, 90-day lifecycle, no public access | never |
| Platform secret store (Secret Manager, Secrets Manager) | n/a | n/a | n/a | yes, the only place |
| External LLM provider | n/a | n/a | only redacted, delimited text, only with `READINESS_ALLOW_LLM_EGRESS=true` after the provider checklist is signed | never (secret rules mask before send) |
| Application logs, audit log | yes | yes | **metadata only** (document ids, hashes, counts, classes) | never |
| Tracker, ADRs, PRs, issues | yes | yes | never (describe clients as "a client", never by name or domain) | never |

## Retention defaults

| Store | Default | Set in |
|---|---|---|
| Uploads and reports buckets | 90 days, then deleted | `report_retention_days` in Terraform |
| Artifact Registry images | last 10 versions, 30 days | Terraform cleanup policy |
| Local `workspace/` | until the analyst deletes it; delete at engagement end | analyst |
| Pseudonym mapping (`pseudonym_mapping.local.json`) | written only when provider is `local`; stays on the analyst machine; never uploaded | `pipeline.py` |
| Audit log | same as the run folder or bucket | n/a |

## Tenant isolation

- Every run is written under `<workspace>/<tenant_id>/<run_id>/` and every bucket key under `<tenant_id>/<run_id>/`.
- `READINESS_TENANT_ID` is set per deployment or per request path; the API never lets a caller pick another tenant's id.
- Recommended: one GCP project (or AWS account) per client for anything beyond a one-off assessment. Terraform
  makes this a `project_id` change in a tfvars file.
- Multi-tenant hardening (per-tenant keys, per-tenant service accounts) is tracked as a story in the `GRD` epic.

## Export procedure (before deletion, when the client wants their data back)

Everything stored for a client sits under a `<tenant_id>/` prefix, so one command collects it:

```bash
uv run readiness tenant export <tenant_id> --out ./<tenant_id>-export.zip            # workspace + reports store
uv run readiness tenant export <tenant_id> --store uploads --out ./<tenant_id>-uploads.zip
```

The zip holds one top-level folder per store (`workspace/`, `reports/`, `uploads/`) and a `manifest.json`
(keys, sizes, sha256); the same manifest is written next to the zip. Hand the zip to the client over the
agreed channel, keep the manifest as the record of what was returned, and never commit either.
`READINESS_PROVIDER` and the bucket variables decide which stores are reached; run it with the same `.env`
the assessments used. Hosted agent sessions (Agent Runtime) are not stored by this tool.

## Deletion procedure

1. Export first if the engagement requires it (above).
2. Dry run, then delete, the tenant's objects in the local workspace and the reports store:
   ```bash
   uv run readiness tenant purge <tenant_id>              # lists what would be deleted
   uv run readiness tenant purge <tenant_id> --yes
   uv run readiness tenant purge <tenant_id> --store uploads --yes
   ```
   Uploads must therefore be placed under `<tenant_id>/` in the uploads bucket (for example
   `gs://<uploads-bucket>/<tenant_id>/<pack>/`) so the same purge covers them.
3. Buckets are versioned: the purge deletes the live objects; non-current versions expire through the
   lifecycle rule (`report_retention_days`). For an immediate hard delete run
   `gcloud storage rm -r --all-versions gs://<bucket>/<tenant_id>/` (or the S3 equivalent) as well.
4. Local: also delete `data/<client>/` and empty the trash. `pseudonym_mapping.local.json` lives inside the
   run folder and goes with the purge.
5. Audit lines (`audit.jsonl`) are deleted with their run folder; they contain hashes and counts only, so a
   copy kept for compliance leaks nothing.
6. Record the export and deletion dates against the engagement in the operator's engagement log (outside
   this repo) and confirm with `uv run readiness tenant purge <tenant_id>` showing 0 objects.
7. If an external model was used, the provider's retention applies; the checklist records which provider and terms.

## What analysts must do on site

- Run with `READINESS_PROVIDER=local` and `READINESS_LLM_PROVIDER=mock` unless the client has approved model use in writing.
- Keep `READINESS_REDACTION_MODE=pseudonymize` (default). Use `--snippets` only for a report that stays with the client.
- Keep `pseudonym_mapping.local.json` on the analyst machine. Do not attach it to e-mail, tickets or shared drives.
- Hand the client the report; do not keep extracted text longer than the engagement needs.
