# Runbook: offboard a tenant (export, then purge)

Use at the end of an engagement, or whenever a client asks for their data or its deletion.
Policy: `docs/security/DATA_HANDLING_POLICY.md`. Tracker story: MIG-05.

Prerequisites: the `.env` (or deployment variables) the assessments ran with, so `READINESS_PROVIDER`,
`READINESS_WORKSPACE_DIR` and the bucket names point at the right stores; for `gcp`, `gcloud auth
application-default login` as someone with object admin on the buckets.

1. **Export** (skip only if the client has confirmed in writing they do not want the data):
   ```bash
   uv run readiness tenant export <tenant_id> --out ./offboarding/<tenant_id>-reports.zip
   uv run readiness tenant export <tenant_id> --store uploads --out ./offboarding/<tenant_id>-uploads.zip
   ```
2. **Verify the manifest**: open `<zip>.manifest.json`, check `file_count` and `total_bytes` look right and that
   every `key` starts with `<tenant_id>/`. Spot-check one sha256 against the file inside the zip.
3. **Deliver** the zips to the client over the agreed channel. Do not attach them to tickets or e-mail.
4. **Dry-run the purge** and read the list:
   ```bash
   uv run readiness tenant purge <tenant_id>
   uv run readiness tenant purge <tenant_id> --store uploads
   ```
5. **Purge**:
   ```bash
   uv run readiness tenant purge <tenant_id> --yes
   uv run readiness tenant purge <tenant_id> --store uploads --yes
   gcloud storage rm -r --all-versions gs://<reports-bucket>/<tenant_id>/ gs://<uploads-bucket>/<tenant_id>/   # GCP hard delete
   ```
6. **Confirm**: both dry-run commands now report `0 object(s)`; `gcloud storage ls gs://<bucket>/<tenant_id>/`
   returns nothing. Delete `data/<client>/` and the local `offboarding/` zips once delivery is confirmed.
7. **Record** export date, deletion date and who confirmed, in the engagement log or CRM; if the engagement has a
   tracker story, close it with those dates in `notes`.

The tool keeps nothing else about a client: Agent Runtime does not persist sessions on our side, logs carry
metadata only, and model providers are governed by the terms recorded in `docs/security/LLM_PROVIDER_CHECKLIST.md`.
