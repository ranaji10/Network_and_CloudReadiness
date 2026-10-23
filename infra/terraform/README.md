# Infrastructure as code

| Folder | Status | What it creates |
|---|---|---|
| `gcp/` | **primary, applied by hand via `make tf-*`** | Cloud Run service, Artifact Registry, buckets, service accounts, secrets shells, optional Cloud Build trigger, optional budget |
| `aws/` | **skeleton, never applied** | Equivalent App Runner + S3 + Secrets Manager layout so a future AWS deployment starts from a plan, not a blank page |

Rules that keep migration frictionless (enforced by `scripts/check_portability.py`):

1. No project ids, account ids, bucket names, e-mails or billing accounts in `.tf` files. They live in
   `envs/<env>.tfvars` (git-ignored) copied from `envs/dev.tfvars.example`.
2. Remote state is configured per environment in `infra/terraform/backend.<env>.hcl` (git-ignored); the
   example file shows the shape. Moving account = new backend file + new tfvars, `terraform init -migrate-state`.
3. Everything the app needs at runtime is an environment variable named in `.env.example`; Terraform
   only *sets* them, the app never reads cloud metadata directly.

See `docs/runbooks/DEPLOY_GCP.md` for the step-by-step and `docs/architecture/MIGRATION_PLAYBOOK.md`
for moving between accounts or providers.
