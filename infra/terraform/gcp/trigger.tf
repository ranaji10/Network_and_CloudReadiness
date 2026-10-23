# Cloud Build trigger (2nd-gen GitHub connection). The connection itself must be created once in the
# console (Cloud Build > Repositories > Connect) because it needs an interactive GitHub OAuth step.
# The repo already has a trigger created by hand; import it or let this one replace it:
#   terraform import 'google_cloudbuild_trigger.main[0]' projects/<project>/locations/<region>/triggers/<id>

resource "google_cloudbuildv2_repository" "repo" {
  count             = var.create_build_trigger ? 1 : 0
  provider          = google-beta
  name              = "readiness-source"
  location          = var.region
  parent_connection = "projects/${var.project_id}/locations/${var.region}/connections/${var.github_connection}"
  remote_uri        = var.github_repo_uri
}

resource "google_cloudbuild_trigger" "main" {
  count           = var.create_build_trigger ? 1 : 0
  provider        = google-beta
  name            = "readiness-${var.env}"
  location        = var.region
  service_account = google_service_account.build.id
  filename        = "cloudbuild.yaml"

  repository_event_config {
    repository = google_cloudbuildv2_repository.repo[0].id
    push {
      branch = var.build_branch_regex
    }
  }

  substitutions = {
    _REGION          = var.region
    _AR_REPO         = var.ar_repo
    _SERVICE         = var.service_name
    _DEPLOY          = var.deploy_cloud_run ? "true" : "false"
    _RUNTIME_SA      = google_service_account.runtime.email
    _DEPLOY_AGENT    = var.deploy_agent_engine ? "true" : "false"
    _AGENT_ENGINE_ID = var.agent_engine_id
    _AGENT_SA        = google_service_account.agent.email
  }
}
