# Data handling policy

This tool is run by one organisation (the operator) against documents belonging to another (the client).
Both must be protected. This page says what data exists, where it may live, for how long, and who deletes it.

## Data classes

| Class | Examples | Owner |
|---|---|---|
| Public | this repository's code and docs, CSA CCM/CAIQ material | anyone |
| Internal | roadmap, tracker, unpublished scoring tuning, cost figures for the operator | operator |
| Client-confidential | every document the tool reads, extracted text, classifications, evidence snippets, reports, pseudonym mappings, audit logs that name documents, questionnaire answers the client submits | client (operator is custodian) |
| Secrets | API keys, API tokens, service-account keys, Terraform state, anything in `.env` or `*.tfvars` | whoever issued them |

## Where each class may live

| Location | Public | Internal | Client-confidential | Secrets |
|---|---|---|---|---|
| Git (this repo) | yes | yes | **never** | **never** |
| Developer machine `workspace/`, `data/` | yes | yes | yes, git-ignored, delete after engagement | only `.env`, git-ignored |
| Uploads / reports buckets (`infra/terraform/gcp`) | n/a | n/a | yes, tenant-prefixed, 90-day lifecycle, no public access | never |
| Platform secret store (Secret Manager, Secrets Manager) | n/a | n/a | n/a | yes, the only place |
| External LLM provider | n/a | n/a | only redacted, delimited text, only with `READINESS_ALLOW_LLM_EGRESS=true` after the provider checklist is signed | never (secret rules mask before send) |
| Application logs, audit log | yes | yes | **metadata only** (document ids, hashes, counts, classes, OCR page counts) | never |
| OCR engine (Tesseract, `ocr` extra) | n/a | n/a | yes, in-process only: page bitmaps are rendered in memory and read by the local `tesseract` binary; no external OCR service, nothing leaves the process (`READINESS_OCR_ENABLED=false` turns it off) | never |
| Tracker, ADRs, PRs, issues | yes | yes | never (describe clients as "a client", never by name or domain) | never |

## Retention defaults

| Store | Default | Set in |
|---|---|---|
| Uploads and reports buckets | per environment, then deleted: dev 90 days, staging 30 days (pilot data only), prod 180 days (a client may ask for its report up to six months after the engagement) | `report_retention_days` in `infra/terraform/gcp/envs/<env>.tfvars.example` |
| Artifact Registry images | last 10 versions, 30 days | Terraform cleanup policy |
| Local `workspace/` | until the analyst deletes it; delete at engagement end | analyst |
| Pseudonym mapping (`pseudonym_mapping.local.json`) | written only when provider is `local`; stays on the analyst machine; never uploaded | `pipeline.py` |
| Questionnaire answers (`<workspace>/<tenant>/answers/`, reports store `<tenant>/answers/`) | same as the run folders and the reports bucket; purged with the tenant | `questionnaire.py`, `api/app.py` |
| Audit log | same as the run folder or bucket | n/a |

## Tenant isolation

- Every run is written under `<workspace>/<tenant_id>/<run_id>/` and every bucket key under `<tenant_id>/<run_id>/`.
- Questionnaire answers (`readiness answer`, `POST /assessments/{id}/answers`) are written under
  `<workspace>/<tenant_id>/answers/` and, through the API, `<tenant_id>/answers/` in the reports store. They are
  redacted and scored like any other document, only counts reach the audit log, and the tenant export and
  purge below cover them because they sit under the same prefix.
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

## Sharing a report outside the tenant

A normal report is client-confidential: it lists the client's document names, and in `pseudonymize` mode
its identifiers can be reversed with `pseudonym_mapping.local.json`. Any report that leaves the tenant
(sent to a prospect's partner, a reviewer, another operator team, a vendor, or pasted into a ticket or
chat outside the engagement) must be rendered **share-safe** instead: `readiness assess --share-safe`, or
`share_safe=true` on `POST /assessments`, `/assessments/upload`, `/jobs` and `/jobs/upload`. A share-safe
run forces `mask` redaction (no reversible tokens, no mapping file), drops evidence snippets and refers to
every document by an opaque `doc-<hash>` label; the label-to-name map is written only to the run's
`audit.jsonl`, which stays in the tenant workspace. The report says so in its data-handling section, so a
reader can tell the two kinds apart. Re-run the assessment with the flag rather than editing a normal
report by hand. Scores and recommendations are identical; only names and snippets differ.

## What analysts must do when handling a client pack

Analysts are never on the client's network: the pack is pushed to the operator, or pulled read-only from a
folder the client shares (`docs/security/DEPLOYMENT_POSTURE.md`). The rules below apply wherever the run happens.

- Run with `READINESS_PROVIDER=local` and `READINESS_LLM_PROVIDER=mock` unless the client has approved model use in writing.
- Keep `READINESS_REDACTION_MODE=pseudonymize` (default). Use `--snippets` only for a report that stays with the client.
- Use `--share-safe` for any report that leaves the tenant (section above); never share a report that names documents.
- Keep `pseudonym_mapping.local.json` on the analyst machine. Do not attach it to e-mail, tickets or shared drives.
- Hand the client the report; do not keep extracted text longer than the engagement needs.
- Scanned pages are OCR'd by the local Tesseract binary inside the process. Never route a client pack through a
  hosted OCR or document-AI service to work around a missing `ocr` extra; install the extra and the binary instead.
