#!/usr/bin/env bash
# One-time bootstrap for a GCP project: enables APIs and creates the Terraform state bucket.
# Run it once per environment, each against its own project (one project per environment,
# docs/decisions/ADR-20261103-one-project-per-environment.md):
#   PROJECT_ID=<dev-project>     ENV=dev     ./infra/scripts/bootstrap_gcp.sh
#   PROJECT_ID=<staging-project> ENV=staging ./infra/scripts/bootstrap_gcp.sh
#   PROJECT_ID=<prod-project>    ENV=prod    ./infra/scripts/bootstrap_gcp.sh
# Idempotent. Writes the git-ignored infra/terraform/backend.<env>.hcl and envs/<env>.tfvars from the
# matching .example files when they do not exist yet; never overwrites them.
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-south1}"
ENV="${ENV:-dev}"
STATE_BUCKET="${STATE_BUCKET:-${PROJECT_ID}-tfstate}"
case "${ENV}" in dev|staging|prod) ;; *) echo "ENV must be dev, staging or prod (got '${ENV}')" >&2; exit 2 ;; esac

echo ">> project=${PROJECT_ID} region=${REGION} env=${ENV} state_bucket=${STATE_BUCKET}"
gcloud config set project "${PROJECT_ID}" >/dev/null

echo ">> enabling APIs"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  secretmanager.googleapis.com storage.googleapis.com iam.googleapis.com logging.googleapis.com \
  monitoring.googleapis.com aiplatform.googleapis.com cloudkms.googleapis.com cloudresourcemanager.googleapis.com \
  cloudbilling.googleapis.com billingbudgets.googleapis.com

if ! gcloud storage buckets describe "gs://${STATE_BUCKET}" >/dev/null 2>&1; then
  echo ">> creating state bucket gs://${STATE_BUCKET}"
  gcloud storage buckets create "gs://${STATE_BUCKET}" --location="${REGION}" \
    --uniform-bucket-level-access --public-access-prevention
  gcloud storage buckets update "gs://${STATE_BUCKET}" --versioning
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/infra/terraform/backend.${ENV}.hcl"
TFVARS="${ROOT}/infra/terraform/gcp/envs/${ENV}.tfvars"
EXAMPLE="${ROOT}/infra/terraform/gcp/envs/${ENV}.tfvars.example"
[ -f "${EXAMPLE}" ] || EXAMPLE="${ROOT}/infra/terraform/gcp/envs/dev.tfvars.example"
[ -f "${BACKEND}" ] || printf 'bucket = "%s"\nprefix = "readiness/%s"\n' "${STATE_BUCKET}" "${ENV}" > "${BACKEND}"
[ -f "${TFVARS}" ] || sed "s/REPLACE-with-your-project-id/${PROJECT_ID}/; s/asia-south1/${REGION}/; s/^env  *= *\"[a-z]*\"/env                     = \"${ENV}\"/" \
  "${EXAMPLE}" > "${TFVARS}"

cat <<MSG
>> done. Review ${TFVARS} (every REPLACE-... value must go; prod needs billing_account). Next:
   make tf-init ENV=${ENV}
   make tf-plan ENV=${ENV}
   make tf-apply ENV=${ENV}
   then connect GitHub in this project (Cloud Build > Repositories) and create the ${ENV} trigger from:
     terraform -chdir=infra/terraform/gcp output cloudbuild_trigger_event
     terraform -chdir=infra/terraform/gcp output cloudbuild_substitutions
   and add secret values:  echo -n '<token>' | gcloud secrets versions add READINESS_API_TOKEN --data-file=-
   Full steps: docs/runbooks/DEPLOY_GCP.md
MSG
