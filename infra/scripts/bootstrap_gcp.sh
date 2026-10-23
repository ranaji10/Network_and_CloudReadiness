#!/usr/bin/env bash
# One-time bootstrap for a GCP project: enables APIs and creates the Terraform state bucket.
# Idempotent. Usage: PROJECT_ID=my-proj REGION=asia-south1 ENV=dev ./infra/scripts/bootstrap_gcp.sh
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-south1}"
ENV="${ENV:-dev}"
STATE_BUCKET="${STATE_BUCKET:-${PROJECT_ID}-tfstate}"

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
[ -f "${BACKEND}" ] || printf 'bucket = "%s"\nprefix = "readiness/%s"\n' "${STATE_BUCKET}" "${ENV}" > "${BACKEND}"
[ -f "${TFVARS}" ] || sed "s/REPLACE-with-your-project-id/${PROJECT_ID}/; s/asia-south1/${REGION}/; s/\"dev\"/\"${ENV}\"/" \
  "${ROOT}/infra/terraform/gcp/envs/dev.tfvars.example" > "${TFVARS}"

cat <<MSG
>> done. Next:
   make tf-init ENV=${ENV}
   make tf-plan ENV=${ENV}
   make tf-apply ENV=${ENV}
   then set the Cloud Build trigger substitutions from: terraform output cloudbuild_substitutions
   and add secret values:  echo -n '<token>' | gcloud secrets versions add READINESS_API_TOKEN --data-file=-
MSG
