# Cloud Build trigger (2nd-gen GitHub connection). The connection itself must be created once per project
# in the console (Cloud Build > Repositories > Connect) because it needs an interactive GitHub OAuth step.
# One trigger per environment, each in its own project (docs/decisions/ADR-20261103-one-project-per-environment.md):
#   dev      push to main (build_branch_regex), deploys when deploy_cloud_run=true
#   staging  push to main, deploys automatically
#   prod     tag matching build_tag_regex (vX.Y.Z), held for manual approval (build_approval_required=true)
# The dev repo already has a trigger created by hand; import it or let this one replace it:
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
      # Exactly one of branch / tag; a null attribute is omitted.
      branch = var.build_tag_regex == "" ? var.build_branch_regex : null
      tag    = var.build_tag_regex != "" ? var.build_tag_regex : null
    }
  }

  dynamic "approval_config" {
    for_each = var.build_approval_required ? [1] : []
    content {
      approval_required = true
    }
  }

  substitutions = {
    _ENV             = var.env
    _REGION          = var.region
    _AR_REPO         = var.ar_repo
    _SERVICE         = var.service_name
    _DEPLOY          = var.deploy_cloud_run ? "true" : "false"
    _INGRESS         = var.ingress == "INGRESS_TRAFFIC_ALL" ? "all" : "internal-and-cloud-load-balancing"
    _RUNTIME_SA      = google_service_account.runtime.email
    _DEPLOY_AGENT    = var.deploy_agent_engine ? "true" : "false"
    _AGENT_ENGINE_ID = var.agent_engine_id
    _AGENT_SA        = google_service_account.agent.email
  }
}
