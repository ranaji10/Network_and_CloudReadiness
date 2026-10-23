locals {
  labels = merge({ app = "readiness", env = var.env, managed_by = "terraform" }, var.labels)
  apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudkms.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ]
  runtime_env = {
    READINESS_PROVIDER                  = "gcp"
    READINESS_ENV                       = var.env
    GOOGLE_CLOUD_PROJECT                = var.project_id
    GOOGLE_CLOUD_LOCATION               = "global"
    READINESS_LLM_PROVIDER              = var.llm_provider
    READINESS_ALLOW_LLM_EGRESS          = tostring(var.allow_llm_egress)
    READINESS_REDACTION_MODE            = var.redaction_mode
    READINESS_GCS_BUCKET_UPLOADS        = google_storage_bucket.uploads.name
    READINESS_GCS_BUCKET_REPORTS        = google_storage_bucket.reports.name
    READINESS_INCLUDE_EVIDENCE_SNIPPETS = "false"
  }
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ---------------- Artifact Registry ----------------
resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = var.ar_repo
  format        = "DOCKER"
  labels        = local.labels
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions { keep_count = 10 }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition { older_than = "2592000s" } # 30 days
  }
  depends_on = [google_project_service.apis]
}

# ---------------- Service accounts (least privilege) ----------------
resource "google_service_account" "runtime" {
  account_id   = "readiness-runtime-${var.env}"
  display_name = "Readiness API runtime (${var.env})"
}

resource "google_service_account" "build" {
  account_id   = "readiness-build-${var.env}"
  display_name = "Readiness Cloud Build (${var.env})"
}

# Agent Engine runtime identity: same data access as the API runtime, nothing project-wide.
resource "google_service_account" "agent" {
  account_id   = "readiness-agent-${var.env}"
  display_name = "Readiness ADK agent on Agent Engine (${var.env})"
}

resource "google_storage_bucket_iam_member" "agent_uploads" {
  bucket = google_storage_bucket.uploads.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_storage_bucket_iam_member" "agent_reports" {
  bucket = google_storage_bucket.reports.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_project_iam_member" "agent_roles" {
  for_each = toset(["roles/logging.logWriter", "roles/monitoring.metricWriter", "roles/aiplatform.user", "roles/cloudtrace.agent"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.agent.email}"
}

# Runtime: read uploads, write reports, read secrets, call Vertex, write logs. Nothing project-wide.
resource "google_storage_bucket_iam_member" "runtime_uploads" {
  bucket = google_storage_bucket.uploads.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket_iam_member" "runtime_reports" {
  bucket = google_storage_bucket.reports.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_roles" {
  for_each = toset(["roles/logging.logWriter", "roles/monitoring.metricWriter", "roles/aiplatform.user"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.runtime.email}"
}

# Build: push images, deploy Cloud Run, deploy to Agent Engine, act as the runtime SAs, write logs.
resource "google_project_iam_member" "build_roles" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/run.developer",
    "roles/logging.logWriter",
    "roles/aiplatform.user",                    # adk deploy agent_engine (create/update reasoning engines)
    "roles/storage.objectAdmin",                # Agent Engine stages the source bundle in a bucket during deploy
    "roles/cloudbuild.builds.editor",           # Agent Engine builds the agent image with Cloud Build
    "roles/developerconnect.readTokenAccessor", # trigger fetches source through a Developer Connect (2nd-gen GitHub) link
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.build.email}"
}

resource "google_service_account_iam_member" "build_acts_as_runtime" {
  for_each           = { runtime = google_service_account.runtime.name, agent = google_service_account.agent.name }
  service_account_id = each.value
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.build.email}"
}

# ---------------- Storage (client data: private, versioned, short-lived) ----------------
resource "google_kms_key_ring" "this" {
  count      = var.use_cmek ? 1 : 0
  name       = "readiness-${var.env}"
  location   = var.region
  depends_on = [google_project_service.apis]
}

resource "google_kms_crypto_key" "storage" {
  count           = var.use_cmek ? 1 : 0
  name            = "storage"
  key_ring        = google_kms_key_ring.this[0].id
  rotation_period = "7776000s" # 90 days
}

data "google_storage_project_service_account" "gcs" {}

resource "google_kms_crypto_key_iam_member" "gcs_uses_key" {
  count         = var.use_cmek ? 1 : 0
  crypto_key_id = google_kms_crypto_key.storage[0].id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}"
}

resource "google_storage_bucket" "uploads" {
  name                        = "${var.project_id}-readiness-uploads-${var.env}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels
  versioning { enabled = true }
  lifecycle_rule {
    action { type = "Delete" }
    condition { age = var.report_retention_days }
  }
  dynamic "encryption" {
    for_each = var.use_cmek ? [1] : []
    content { default_kms_key_name = google_kms_crypto_key.storage[0].id }
  }
  depends_on = [google_project_service.apis, google_kms_crypto_key_iam_member.gcs_uses_key]
}

resource "google_storage_bucket" "reports" {
  name                        = "${var.project_id}-readiness-reports-${var.env}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = local.labels
  versioning { enabled = true }
  lifecycle_rule {
    action { type = "Delete" }
    condition { age = var.report_retention_days }
  }
  dynamic "encryption" {
    for_each = var.use_cmek ? [1] : []
    content { default_kms_key_name = google_kms_crypto_key.storage[0].id }
  }
  depends_on = [google_project_service.apis, google_kms_crypto_key_iam_member.gcs_uses_key]
}

# ---------------- Secrets (shells only; values are added out-of-band, never via Terraform) ----------------
resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(["READINESS_API_TOKEN", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"])
  secret_id = each.value
  labels    = local.labels
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "runtime_reads" {
  for_each  = google_secret_manager_secret.secrets
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# ---------------- Cloud Run ----------------
resource "google_cloud_run_v2_service" "api" {
  count    = var.deploy_cloud_run ? 1 : 0
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  labels   = local.labels

  template {
    service_account = google_service_account.runtime.email
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
    containers {
      image = var.image != "" ? var.image : "us-docker.pkg.dev/cloudrun/container/hello"
      ports { container_port = 8080 }
      resources {
        limits = { cpu = "2", memory = "2Gi" }
      }
      dynamic "env" {
        for_each = local.runtime_env
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "READINESS_API_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secrets["READINESS_API_TOKEN"].secret_id
            version = "latest"
          }
        }
      }
    }
  }
  lifecycle {
    ignore_changes = [template[0].containers[0].image] # Cloud Build owns the image after first apply
  }
  depends_on = [google_project_service.apis, google_secret_manager_secret_iam_member.runtime_reads]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.deploy_cloud_run && var.allow_unauthenticated ? 1 : 0
  name     = google_cloud_run_v2_service.api[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------- Budget (optional) ----------------
resource "google_billing_budget" "monthly" {
  count           = var.billing_account != "" ? 1 : 0
  billing_account = var.billing_account
  display_name    = "readiness-${var.env}-monthly"
  budget_filter {
    projects = ["projects/${var.project_id}"]
  }
  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_usd)
    }
  }
  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 0.9 }
  threshold_rules { threshold_percent = 1.0 }
}
