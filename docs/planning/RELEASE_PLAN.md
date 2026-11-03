# Release plan

## Versioning

- Semantic versioning. The version lives in `pyproject.toml` and `src/readiness/__init__.py`
  (`__version__`) and is printed in every report as `tool_version`, so a client report can always be
  traced to the code that produced it.
- Scoring domains and profiles carry their own `version` field. Bump a domain or profile version
  when weights, points or thresholds change, because that changes scores for the same documents.
- Patch: fixes, signal tweaks that do not change points. Minor: new checks, new adapters, new
  surfaces. Major: report schema or API changes that break consumers.

## Environments

One GCP project per environment, same code, same `cloudbuild.yaml`, same Terraform module; only the
git-ignored `infra/terraform/gcp/envs/<env>.tfvars` and `infra/terraform/backend.<env>.hcl` differ
(`docs/decisions/ADR-20261103-one-project-per-environment.md`). The tracked `*.example` files next to
them are the intended posture of each environment and are reviewed like code.

| Environment | Project / Terraform | Purpose | Who deploys |
|---|---|---|---|
| local | none (`docker compose`, `make serve`) | development, offline demos | anyone |
| dev | own project, `envs/dev.tfvars` | developer target against real GCP services; may be destroyed | Cloud Build on push to `main` in the dev project when its trigger has `_DEPLOY=true`, or a manual `gcloud builds submit` |
| staging | own project, `envs/staging.tfvars` | release candidates, client pilots with synthetic data, the soak before a tag | Cloud Build, automatically, on every push to `main` |
| prod | own project, `envs/prod.tfvars` | client assessments: the only environment that may hold client documents | Cloud Build on tag `vX.Y.Z`, after a release owner approves the build |

What differs between the projects, by design:

| | dev | staging | prod |
|---|---|---|---|
| Ingress | all (IAM) | all (IAM) until IAP exists (INF-04) | internal + load balancer only |
| Scaling | 0-5 | 0-3 | 1-10 (one warm instance) |
| CMEK on buckets | off | on | on |
| Deletion protection | off | on | on |
| Retention of uploads and reports | 90 days | 30 days | 180 days |
| Budget alert | optional, 50 USD | recommended, 50 USD | required, 200 USD |
| Model egress | mock, off | mock, off | mock, off until the provider checklist is signed |

Never run real client data through dev or staging, with or without egress.

## Release checklist

1. `make check` and `make secrets-scan` green locally.
2. Tracker: every story in the release is `done`; `make tracker` run.
3. Version bumped in `pyproject.toml` and `__init__.py`; `uv lock` refreshed if dependencies moved.
4. Domain and profile versions bumped where scoring changed, with a line in `CHANGELOG.md`
   (create it at the first tagged release) saying what moved and why.
5. Run the synthetic demo (`make demo`) and compare the scores with the previous release; explain
   any change.
6. Staging is green for the exact `main` commit you are about to tag (it deployed automatically on
   merge): `/healthz`, one synthetic assessment through the API, scores compared with the previous
   release.
7. Tag `vX.Y.Z` on that commit and push the tag. The prod trigger builds it and waits for approval.
8. Approve the build in the prod project (Cloud Build > History > Approve). Check `/healthz` and run
   one assessment with the synthetic pack through the API in prod.
9. Record the deployed image digest and the Cloud Run revision name in the release notes.

## Promotion

```
feature branch ──PR, make check green──> main ──staging trigger (push, automatic)──> staging project
                                           │
                                           └── git tag vX.Y.Z ──prod trigger (tag, manual approval)──> prod project
```

Each environment's trigger lives in that environment's project and runs the same `cloudbuild.yaml`
with `_ENV` set to the environment (`terraform output cloudbuild_substitutions` prints the full set).

| Step | What happens | Who | Gate |
|---|---|---|---|
| dev | A developer applies `envs/dev.tfvars` to a dev project and, if they want, points its trigger at `main` with `_DEPLOY=true`; or runs `gcloud builds submit` by hand. Nothing in dev is a release artefact. | any maintainer | `make check` locally |
| main → staging | The staging trigger (`^main$`, `_ENV=staging`, `_DEPLOY=true`) runs the quality gate, gitleaks, the image build, pushes `:<sha>` and `:latest` to the staging registry and runs `gcloud run deploy`. Nobody deploys to staging by hand. | Cloud Build | PR review + green CI on the PR; the build repeats the gate |
| staging soak | The release owner runs the checklist above against staging. A staging failure is fixed on `main` (a new merge redeploys staging); staging is never patched in place. | release owner | checklist items 1-6 |
| tag → prod | `git tag -a vX.Y.Z -m "..." <sha> && git push origin vX.Y.Z` on the commit staging verified. The prod trigger (`^v[0-9]+\.[0-9]+\.[0-9]+$`, `_ENV=prod`, `_DEPLOY=true`, approval required) creates a build in the *pending approval* state. | release owner (tag), a Cloud Build approver (approve) | protect `v*` tags in GitHub so only release owners can push them; approvers hold `roles/cloudbuild.builds.approver` on the prod project and nothing else by default |
| prod deploy | On approval the build re-runs the full gate in the prod project, pushes `:<sha>`, `:latest` and `:vX.Y.Z` to the prod registry and deploys. The approver compares the build's commit with the one staging verified before approving. | Cloud Build | the approval itself; a release that changes `envs/prod.tfvars.example`, `config/redaction.yaml` or anything under `docs/security/` additionally needs the security owner's PR review (CODEOWNERS) |
| after | `/healthz` through the load balancer (prod has no direct `run.app` access), one synthetic assessment, release notes with image digest and revision name. | release owner | |

Prod is rebuilt from the tagged commit rather than pulling staging's image; `uv.lock`, the pinned base
image and the frozen install make the two builds equivalent, and the prod build is the one whose digest
is recorded. If a client contract ever requires a byte-identical promotion, grant the prod build service
account `roles/artifactregistry.reader` on the staging registry and set the prod trigger's `_IMAGE`
substitution to the staging path; `cloudbuild.yaml` needs no change.

### Configuration and secret differences per project

| What | Where it lives | How it changes |
|---|---|---|
| Infrastructure posture (retention, CMEK, ingress, scaling, budget, trigger event) | `infra/terraform/gcp/envs/<env>.tfvars` (git-ignored) copied from the tracked `envs/<env>.tfvars.example` | change the `.example` in a PR; after merge the environment's operator updates the local tfvars and runs `make tf-plan ENV=<env>` / `make tf-apply ENV=<env>`. The example files are the source of truth for the intended posture; `make tf-plan-all` shows which environment has drifted from them. |
| Runtime environment variables (`READINESS_*`, bucket names, model provider, egress flag) | set on the Cloud Run service by Terraform from the tfvars | only through Terraform. Cloud Build updates exactly `READINESS_PROVIDER`, `READINESS_ENV` and `GOOGLE_CLOUD_PROJECT` (`--update-env-vars`) and leaves the rest alone. |
| Secrets (`READINESS_API_TOKEN`, `READINESS_TENANT_TOKENS`, model keys) | Secret Manager in each project; Terraform creates empty shells, never values | added by hand in the project that needs them (`gcloud secrets versions add ... --project <that project>`), never copied between projects, rotated per project. The prod API token is known to the prod operators only. |
| Cloud Build substitutions | one trigger per project, values from `terraform output cloudbuild_substitutions` in that project | re-run the output after a Terraform change and paste; with `create_build_trigger=true` Terraform owns them |
| Terraform state | `backend.<env>.hcl`, one state bucket per project | never migrated between environments; `make tf-init` runs with `-reconfigure` so switching `ENV` cannot carry state across |
| Product configuration (`config/**/*.yaml`) | baked into the image | identical in every environment by construction; a scoring change is a release, not an environment setting |

### Rollback

Preferred, no new build: redeploy the previous release tag in the prod registry.

```
gcloud run deploy readiness-api --region <region> --project <prod-project> \
  --image <region>-docker.pkg.dev/<prod-project>/readiness/readiness-api:vX.Y.(Z-1)
```

Fastest, same image already running: shift traffic to the previous revision.

```
gcloud run services update-traffic readiness-api --region <region> --to-revisions <previous-revision>=100
```

Terraform ignores the image on the Cloud Run service, so neither path drifts the state. If a release
changed Terraform resources, `terraform apply` the previous tag's `infra/` with the same tfvars. A rolled
back prod stays rolled back until a new tag goes through staging; do not re-approve the failed build.
Staging is rolled back by reverting on `main`.

Reports are immutable per run id, so a rollback never changes an already produced report; re-run
the assessment on the rolled-back version if a client needs a corrected report.
