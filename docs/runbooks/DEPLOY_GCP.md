# Runbook: deploy to Google Cloud

Prerequisites: `gcloud` authenticated as an owner of the project you are working on, Terraform >= 1.6,
and for staging and prod the GitHub repository connected to Cloud Build *in that project* (step 4).

## 0. Environments

One GCP project per environment (`docs/decisions/ADR-20261103-one-project-per-environment.md`). Every
step below is run once per project with `ENV=<env>`; the only files that differ are the git-ignored
`infra/terraform/backend.<env>.hcl` and `infra/terraform/gcp/envs/<env>.tfvars`, copied from the tracked
`.example` files, which hold the intended posture of each environment.

| ENV | Project | tfvars example | Trigger event | Approval | Deploys |
|---|---|---|---|---|---|
| `dev` | the developer's own | `envs/dev.tfvars.example` | push to `main` (optional) | none | when `_DEPLOY=true` on the trigger |
| `staging` | shared staging project | `envs/staging.tfvars.example` | push to `main` | none | automatically |
| `prod` | prod project, client data only here | `envs/prod.tfvars.example` | tag `vX.Y.Z` | required (Cloud Build approver) | after approval |

Promotion (`main` → staging → tag → prod) and rollback are in `docs/planning/RELEASE_PLAN.md`.
`make tf-validate` checks formatting and syntax of the module without any backend or credentials.

## 1. Bootstrap the project (once per project)

```bash
PROJECT_ID=<dev-project>     REGION=asia-south1 ENV=dev     ./infra/scripts/bootstrap_gcp.sh
PROJECT_ID=<staging-project> REGION=asia-south1 ENV=staging ./infra/scripts/bootstrap_gcp.sh
PROJECT_ID=<prod-project>    REGION=asia-south1 ENV=prod    ./infra/scripts/bootstrap_gcp.sh
```

Each run enables the APIs in that project, creates its Terraform state bucket (`<project>-tfstate`,
versioned, public access prevented), and writes `infra/terraform/backend.<env>.hcl` and
`infra/terraform/gcp/envs/<env>.tfvars` from the matching `.example` (both git-ignored, never
overwritten). Open the tfvars and replace every `REPLACE-...` value; prod also needs `billing_account`.

## 2. Add the API token secret (before the first apply)

The Cloud Run service mounts `READINESS_API_TOKEN:latest`, so a version must exist before the service
is created. The secret shell itself is created by Terraform, so create it here first, then add the version;
Terraform imports nothing and will not complain about an existing secret only if you let it create it, so
run the two commands in this order (`ENV` and `--project` name the same environment; secrets are never
copied between projects):

```bash
make tf-init ENV=<env>
make tf-apply ENV=<env> TF_ARGS='-target=google_secret_manager_secret.secrets'   # secret shells only
openssl rand -hex 32 | tr -d '\n' | gcloud secrets versions add READINESS_API_TOKEN --data-file=- --project <that project>
# only if the provider checklist is signed for this environment:
printf '%s' "$GEMINI_KEY" | gcloud secrets versions add GEMINI_API_KEY --data-file=- --project <that project>
```

## 3. Apply the infrastructure

```bash
make tf-plan ENV=<env>
make tf-apply ENV=<env>
terraform -chdir=infra/terraform/gcp output
make tf-plan-all        # optional: plan every environment that has a tfvars, to spot drift
```

Creates: Artifact Registry repo, runtime, build and agent service accounts, uploads and reports buckets
(CMEK in staging and prod), secret shells, a Cloud Run service with a placeholder image (IAM auth required;
dev and staging use ingress `INGRESS_TRAFFIC_ALL` so the proxy check in step 5 works, prod uses the internal
+ load balancer value and is reachable only once IAP is in front, tracker INF-04; deletion protection on in
staging and prod; `min_instances` / `max_instances` per environment), and a budget where `billing_account`
is set. Every resource carries the `environment` label. With `deploy_cloud_run=false` only the supporting
resources are created. `terraform plan` may show a no-op `scaling {}` diff on the service from the provider;
it is ignored via `lifecycle.ignore_changes`.

## 4. Configure the Cloud Build trigger (one per project)

Cloud Build needs a GitHub connection in each project (Cloud Build > Repositories > Connect repository,
2nd generation; interactive OAuth, once per project). Then create or edit the trigger for that
environment:

| ENV | Name | Event | Approval | Substitutions |
|---|---|---|---|---|
| `dev` | `readiness-dev` | push, branch `^main$` | no | `_ENV=dev`, `_DEPLOY` as you like |
| `staging` | `readiness-staging` | push, branch `^main$` | no | `_ENV=staging`, `_DEPLOY=true` |
| `prod` | `readiness-prod` | push, **tag** `^v[0-9]+\.[0-9]+\.[0-9]+$` | **yes** ("Require approval before build executes") | `_ENV=prod`, `_DEPLOY=true` |

For each trigger: configuration `cloudbuild.yaml`, service account from
`terraform output build_service_account`, event from `terraform output cloudbuild_trigger_event`, and all
substitutions from `terraform output cloudbuild_substitutions` (run in the matching environment; GitHub
Actions covers every other branch). A trigger that was created with an inline build config or a Developer
Connect link cannot be changed with `gcloud builds triggers update`; use
`gcloud builds triggers describe <id> --region <r> > t.yaml`, edit, then
`gcloud builds triggers import --region <r> --source t.yaml`. Alternatively set `create_build_trigger=true`
in the tfvars with `github_connection` and `github_repo_uri` and re-apply: `build_branch_regex`,
`build_tag_regex` and `build_approval_required` in the example files already encode the table above.

Prod approvers need `roles/cloudbuild.builds.approver` on the prod project:

```bash
gcloud projects add-iam-policy-binding <prod-project> --member user:<release-owner> --role roles/cloudbuild.builds.approver
```

Protect `v*` tags in GitHub (Settings > Rules) so only release owners can create them.

Every push to `main` now runs: quality gate, gitleaks, container build; in the staging project also push
and `gcloud run deploy`. A `vX.Y.Z` tag queues a prod build that waits in Cloud Build > History until an
approver releases it. The deploy step only updates `READINESS_PROVIDER`, `READINESS_ENV` and
`GOOGLE_CLOUD_PROJECT` on the service; every other runtime variable stays as Terraform set it from the
tfvars. To also update the ADK agent on Vertex AI Agent Engine on every build, follow
`docs/runbooks/DEPLOY_AGENT_ENGINE.md` (`_DEPLOY_AGENT=true`, `_AGENT_ENGINE_ID`, `_AGENT_SA`).

A dev project without a trigger can be deployed by hand from a checkout; the built-in `SHORT_SHA` is empty
outside triggered builds, so pass it:

```bash
gcloud builds submit --config cloudbuild.yaml --project <dev-project> \
  --substitutions _ENV=dev,_DEPLOY=true,_RUNTIME_SA=<runtime SA email>,SHORT_SHA=$(git rev-parse --short HEAD)
```

## 5. Verify

```bash
gcloud run services describe readiness-api --region asia-south1 \
  --format 'value(status.conditions[0].status,status.latestReadyRevisionName)'    # True + a revision
gcloud run services proxy readiness-api --region asia-south1 --port 8081 &          # needs ingress = ALL
curl -s localhost:8081/healthz
TOKEN=$(gcloud secrets versions access latest --secret READINESS_API_TOKEN)
curl -s -H "Authorization: Bearer $TOKEN" localhost:8081/profiles | head -c 300
```

With `ingress` set to the internal + load balancer value the proxy cannot reach the service (Google
returns a 404); verify through the Ready condition and the "Application startup complete" line in
`gcloud run services logs read readiness-api --region asia-south1 --limit 50` instead.

For a client-facing endpoint put IAP or an API gateway in front; do not set `allow_unauthenticated=true`.

## 6. Enable a real model (optional)

Complete `docs/security/LLM_PROVIDER_CHECKLIST.md`. Then in tfvars set `llm_provider = "gemini"` and
`allow_llm_egress = true`, apply, and add the key secret version. The runtime SA already has
`roles/aiplatform.user`; with Vertex you can leave `GEMINI_API_KEY` empty and use ADC.

## 7. Rollback

```bash
gcloud run revisions list --service readiness-api --region asia-south1
gcloud run services update-traffic readiness-api --region asia-south1 --to-revisions <previous>=100
# or redeploy a previous release tag (prod registry keeps :<sha>, :latest and :vX.Y.Z):
gcloud run deploy readiness-api --region asia-south1 --project <prod-project> \
  --image asia-south1-docker.pkg.dev/<prod-project>/readiness/readiness-api:<previous tag>
```

Infrastructure rollback: `git revert` the Terraform change and `make tf-apply ENV=<env>`. Rolling prod
back never means re-approving a failed build; fix on `main`, let staging verify, tag again
(`docs/planning/RELEASE_PLAN.md`, "Rollback").

## 8. Decommission an environment

In that project only: set `_DEPLOY=false` on (or delete) its trigger, set `deletion_protection = false` in
its tfvars and apply, empty both buckets (versioned: all versions; `force_destroy=false` refuses otherwise),
then `terraform destroy -var-file=envs/<env>.tfvars`, delete the secrets, and delete the state bucket last.
Prod additionally follows the retention period in `docs/security/DATA_HANDLING_POLICY.md` before the
buckets are emptied.
