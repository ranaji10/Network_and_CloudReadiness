# One GCP project per environment, promoted by tag, never by hand

Status: accepted
Date: 2026-11-03

## Context
Until now there was a single `dev` project: Cloud Build deployed every push to `main` into it, and the
release plan promised `staging` and `prod` "when INF-07 is done". The product is about to run real
client documents (ADR-20261103-outside-the-client-network), so three things that one project cannot
give us became requirements:

- an **isolation boundary** between synthetic pilot data and client data that a client security
  team can verify with one question ("which project?") rather than by reading IAM bindings;
- a **blast radius** for infrastructure mistakes: a wrong `terraform apply`, a bucket lifecycle
  change or a deleted secret in one environment must not touch another;
- a **release gate**: something that is not `main` has to decide what runs in prod, with a person
  approving it and a way back that does not involve rebuilding.

The alternatives were one project with environment-suffixed resources (cheaper, but IAM, budgets,
CMEK keys, audit logs and VPC-SC perimeters are all project-scoped, so the isolation would be by
naming convention only) and folders of projects per environment (right for an organisation with
many services; overkill for one API and one agent).

## Decision
**Every environment is its own GCP project, with its own Terraform state, its own Cloud Build
trigger, its own secrets and its own budget. The same code, the same `cloudbuild.yaml` and the same
Terraform module are applied to all three; only `envs/<env>.tfvars` and `backend.<env>.hcl` differ.**

- Environments: `dev` (developer target, deploys from `main` if the developer wants),
  `staging` (automatic from every push to `main`), `prod` (from a release tag `vX.Y.Z` only, after
  a manual approval in Cloud Build). Promotion is documented in `docs/planning/RELEASE_PLAN.md`.
- The environment is an input (`env`), validated to `dev | staging | prod`, stamped as the
  `environment` label on every labelable resource and passed to the runtime as `READINESS_ENV`.
- Posture differences are Terraform variables with environment-specific values in the tracked
  `envs/<env>.tfvars.example` files (`use_cmek`, `deletion_protection`, `ingress`, `min_instances`,
  `max_instances`, `report_retention_days`, `monthly_budget_usd`, `build_tag_regex`,
  `build_approval_required`). Nothing environment-specific is hard-coded in `.tf` files or in
  `cloudbuild.yaml`; the build only learns its environment from the `_ENV` substitution.
- Secrets are per project. A value is added by hand in the project that needs it and is never copied
  between projects through files or CI variables.
- Cloud Build updates the Cloud Run image and the three variables it owns (`READINESS_PROVIDER`,
  `READINESS_ENV`, `GOOGLE_CLOUD_PROJECT`) and nothing else; every other runtime variable is set by
  Terraform from the tfvars, so an environment's behaviour is reviewable in one file.
- The image built for a release tag is pushed as `:<sha>`, `:latest` and `:vX.Y.Z` into the prod
  project's registry, so a rollback is a redeploy of a previous tag, not a rebuild.

## Consequences
- Standing up or tearing down an environment is a bootstrap script run plus a Terraform apply in a
  fresh project; the repository does not change. The migration playbook's "new project" procedure is
  now the normal way to create an environment.
- Three projects mean three GitHub connections in Cloud Build (each needs an interactive OAuth
  step), three triggers, three sets of secret values and three budgets to watch. The bootstrap script
  and the runbook spell out the per-project steps; `make tf-plan-all` shows drift across all three.
- Prod cannot be deployed from a branch at all: the trigger listens to tags, the build waits for an
  approver, and the Cloud Run service carries deletion protection. A hotfix therefore goes through
  `main`, staging and a new tag, which is the point.
- `terraform init` now runs with `-reconfigure` so switching `ENV` never offers to migrate state
  between projects. Anyone who had applied the dev project before this decision keeps working; the
  `environment` label and the explicit scaling values are an in-place update.
- The AWS skeleton inherits the same rule (`env` input, one account or one set of resources per
  environment) when INF-06 validates it.
