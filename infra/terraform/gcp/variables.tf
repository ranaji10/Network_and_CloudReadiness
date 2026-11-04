variable "project_id" {
  description = "GCP project id. Never hard-code; comes from envs/<env>.tfvars."
  type        = string
}

variable "region" {
  description = "Primary region for Cloud Run, Artifact Registry and buckets."
  type        = string
  default     = "asia-south1"
}

variable "env" {
  description = "Environment name (dev, staging, prod). Used in resource names and labels. One GCP project per environment (docs/decisions/ADR-20261103-one-project-per-environment.md)."
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of: dev, staging, prod."
  }
}

variable "service_name" {
  type    = string
  default = "readiness-api"
}

variable "ar_repo" {
  description = "Artifact Registry repository name."
  type        = string
  default     = "readiness"
}

variable "image" {
  description = "Container image to deploy. Empty = create the service with a placeholder image; Cloud Build updates it."
  type        = string
  default     = ""
}

variable "deploy_cloud_run" {
  description = "Create the Cloud Run service (set false to only lay down registry, buckets, IAM)."
  type        = bool
  default     = true
}

variable "allow_unauthenticated" {
  description = "Expose the API without IAM. Keep false; front with IAP or an API gateway instead."
  type        = bool
  default     = false
}

variable "llm_provider" {
  description = "mock | gemini | anthropic — runtime READINESS_LLM_PROVIDER."
  type        = string
  default     = "mock"
}

variable "allow_llm_egress" {
  description = "Must be explicitly true before any real model is called (guardrail)."
  type        = bool
  default     = false
}

variable "redaction_mode" {
  type    = string
  default = "pseudonymize"
}

variable "use_cmek" {
  description = "Encrypt buckets with a customer-managed key (creates a KMS keyring/key)."
  type        = bool
  default     = false
}

variable "report_retention_days" {
  description = "Delete stored reports/uploads after N days (data minimisation)."
  type        = number
  default     = 90
}

variable "create_build_trigger" {
  description = "Create the Cloud Build GitHub trigger via Terraform (requires an existing Cloud Build GitHub connection)."
  type        = bool
  default     = false
}

variable "github_connection" {
  description = "Name of the existing Cloud Build (2nd gen) GitHub connection, e.g. 'github'."
  type        = string
  default     = ""
}

variable "github_repo_uri" {
  description = "HTTPS URI of the GitHub repo, e.g. https://github.com/<owner>/<repo>.git"
  type        = string
  default     = ""
}

variable "build_branch_regex" {
  description = "Branch regex for the Cloud Build trigger (dev and staging deploy from main). Ignored when build_tag_regex is set."
  type        = string
  default     = "^main$"
}

variable "build_tag_regex" {
  description = "When non-empty the trigger fires on git tags matching this regex instead of on branches (prod: release tags vX.Y.Z, see envs/prod.tfvars.example)."
  type        = string
  default     = ""
}

variable "build_approval_required" {
  description = "Hold every build from this trigger until a Cloud Build Approver approves it in the console (prod). Needs roles/cloudbuild.builds.approver on the approvers."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Refuse to destroy the Cloud Run service through Terraform. Keep true in staging and prod; dev may set false so a throw-away project can be torn down. Buckets are always force_destroy=false (client data) regardless of this flag."
  type        = bool
  default     = true
}

variable "min_instances" {
  description = "Cloud Run minimum instance count. 0 scales to zero (dev, staging); prod keeps 1 warm so client-facing calls do not pay a cold start."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Cloud Run maximum instance count: the cost ceiling of the environment."
  type        = number
  default     = 5
}

variable "billing_account" {
  description = "Billing account id for the optional budget alert. Empty disables the budget."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  type    = number
  default = 50
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "deploy_agent_engine" {
  description = "Let the main-branch build deploy the ADK agent to Vertex AI Agent Engine (_DEPLOY_AGENT=true)."
  type        = bool
  default     = false
}

variable "agent_engine_id" {
  description = "Resource id of the Agent Engine instance to update on each deploy. Empty = create a new one on the first run, then paste the id here."
  type        = string
  default     = ""
}

variable "ingress" {
  description = "Cloud Run ingress. INGRESS_TRAFFIC_ALL keeps IAM auth but lets `gcloud run services proxy` reach the service; switch to INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER once IAP / a load balancer exists (INF-04)."
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "tenant_tokens_secret" {
  description = "Mount the READINESS_TENANT_TOKENS secret (JSON map tenant -> token) into Cloud Run. Add a version to the secret first."
  type        = bool
  default     = false
}
