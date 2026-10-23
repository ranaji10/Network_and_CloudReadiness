# Runbook: deploy to Google Cloud

Prerequisites: `gcloud` authenticated as a project owner, Terraform >= 1.6, the GitHub repository already
connected to Cloud Build (it is, with a trigger that currently builds every push).

## 1. Bootstrap the project (once per project)

```bash
PROJECT_ID=<project-id> REGION=asia-south1 ENV=dev ./infra/scripts/bootstrap_gcp.sh
```

Creates the Terraform state bucket, enables APIs, writes `infra/terraform/backend.dev.hcl` and
`infra/terraform/gcp/envs/dev.tfvars` (both git-ignored). Edit the tfvars if needed.

## 2. Apply the infrastructure

```bash
make tf-init ENV=dev
make tf-plan ENV=dev
make tf-apply ENV=dev
terraform -chdir=infra/terraform/gcp output
```

Creates: Artifact Registry repo, runtime and build service accounts, uploads and reports buckets,
secret shells, a Cloud Run service with a placeholder image (not public, internal + LB ingress), and
optionally a budget. With `deploy_cloud_run=false` only the supporting resources are created.

## 3. Add secret values (never via Terraform or files in the repo)

```bash
openssl rand -hex 32 | tr -d '\n' | gcloud secrets versions add READINESS_API_TOKEN --data-file=-
# only if the provider checklist is signed:
printf '%s' "$GEMINI_KEY" | gcloud secrets versions add GEMINI_API_KEY --data-file=-
```

## 4. Configure the Cloud Build trigger

On the existing trigger (Cloud Build > Triggers > edit): set the service account to the build SA from
`terraform output build_service_account` and add the substitutions from
`terraform output cloudbuild_substitutions`. Keep `_DEPLOY=false` for the all-branches trigger.
Create a second trigger on `^main$` with `_DEPLOY=true`, or set `create_build_trigger=true` in tfvars with
`github_connection` and `github_repo_uri` and re-apply.

Every push now runs: quality gate, gitleaks, container build; on `main` also push and `gcloud run deploy`.
To also update the ADK agent on Vertex AI Agent Engine on every main build, follow
`docs/runbooks/DEPLOY_AGENT_ENGINE.md` (`_DEPLOY_AGENT=true`, `_AGENT_ENGINE_ID`, `_AGENT_SA`).

## 5. Verify

```bash
gcloud run services describe readiness-api --region asia-south1 --format 'value(status.url)'
gcloud run services proxy readiness-api --region asia-south1 --port 8081 &
curl -s localhost:8081/healthz
TOKEN=$(gcloud secrets versions access latest --secret READINESS_API_TOKEN)
curl -s -H "Authorization: Bearer $TOKEN" localhost:8081/profiles | head -c 300
```

For a client-facing endpoint put IAP or an API gateway in front; do not set `allow_unauthenticated=true`.

## 6. Enable a real model (optional)

Complete `docs/security/LLM_PROVIDER_CHECKLIST.md`. Then in tfvars set `llm_provider = "gemini"` and
`allow_llm_egress = true`, apply, and add the key secret version. The runtime SA already has
`roles/aiplatform.user`; with Vertex you can leave `GEMINI_API_KEY` empty and use ADC.

## 7. Rollback

```bash
gcloud run revisions list --service readiness-api --region asia-south1
gcloud run services update-traffic readiness-api --region asia-south1 --to-revisions <previous>=100
```

Infrastructure rollback: `git revert` the Terraform change and `make tf-apply`.

## 8. Decommission

Set `_DEPLOY=false`, `terraform destroy -var-file=envs/dev.tfvars` (buckets have `force_destroy=false`;
empty them first, all versions), delete secrets, disable the trigger.
