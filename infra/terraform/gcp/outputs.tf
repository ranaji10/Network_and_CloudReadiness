output "service_url" {
  value = var.deploy_cloud_run ? google_cloud_run_v2_service.api[0].uri : null
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${var.ar_repo}"
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

output "build_service_account" {
  value = google_service_account.build.email
}

output "buckets" {
  value = { uploads = google_storage_bucket.uploads.name, reports = google_storage_bucket.reports.name }
}

output "cloudbuild_substitutions" {
  description = "Paste these on the existing trigger if create_build_trigger=false."
  value = {
    _REGION     = var.region
    _AR_REPO    = var.ar_repo
    _SERVICE    = var.service_name
    _DEPLOY     = var.deploy_cloud_run ? "true" : "false"
    _RUNTIME_SA = google_service_account.runtime.email
  }
}
