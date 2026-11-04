# Infrastructure as code

| Folder | Status | What it creates |
|---|---|---|
| `gcp/` | **primary, applied by hand via `make tf-*`** | Cloud Run service, Artifact Registry, buckets, service accounts, secrets shells, optional Cloud Build trigger, optional budget |
| `aws/` | **skeleton, never applied** | Equivalent App Runner + S3 + Secrets Manager layout so a future AWS deployment starts from a plan, not a blank page |

Rules that keep migration frictionless (enforced by `scripts/check_portability.py`):

1. No project ids, account ids, bucket names, e-mails or billing accounts in `.tf` files. They live in
   `envs/<env>.tfvars` (git-ignored) copied from the tracked `envs/<env>.tfvars.example`.
2. Remote state is configured per environment in `infra/terraform/backend.<env>.hcl` (git-ignored); the
   `backend.<env>.hcl.example` files show the shape. Moving account = new backend file + new tfvars,
   `terraform init -migrate-state`.
3. Everything the app needs at runtime is an environment variable named in `.env.example`; Terraform
   only *sets* them, the app never reads cloud metadata directly.
4. One GCP project per environment (`docs/decisions/ADR-20261103-one-project-per-environment.md`). The
   same module is applied three times with a different `ENV`; the example files are the intended posture:

   | ENV | Example files | Posture |
   |---|---|---|
   | `dev` | `gcp/envs/dev.tfvars.example`, `backend.dev.hcl.example` | cheapest; no CMEK, no deletion protection, may be destroyed |
   | `staging` | `gcp/envs/staging.tfvars.example`, `backend.staging.hcl.example` | prod's security posture (CMEK, deletion protection), scale to zero, 30-day retention, deploys on every push to `main` |
   | `prod` | `gcp/envs/prod.tfvars.example`, `backend.prod.hcl.example` | internal ingress only, one warm instance, 180-day retention, budget required, deploys on an approved `vX.Y.Z` tag build |

   `make tf-validate` checks `fmt` and `validate` offline; `make tf-plan-all` plans every environment that
   has a tfvars file.

See `docs/runbooks/DEPLOY_GCP.md` for the step-by-step, `docs/planning/RELEASE_PLAN.md` for promotion
between the environments and `docs/architecture/MIGRATION_PLAYBOOK.md` for moving between accounts or
providers.
