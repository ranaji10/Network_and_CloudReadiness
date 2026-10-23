# AWS deployment skeleton (NOT YET APPLIED)

Mirror of `../gcp` for a future AWS target. It exists so the migration playbook has a concrete starting
point; it has not been applied or tested. Tracker item INF-06 covers validating it.

Mapping used:

| GCP | AWS |
|---|---|
| Cloud Run | App Runner (or ECS Fargate) |
| Artifact Registry | ECR |
| Cloud Storage buckets | S3 (SSE-KMS, lifecycle) |
| Secret Manager | Secrets Manager |
| Cloud Build | CodeBuild (or GitHub Actions with OIDC) |
| Vertex AI Gemini | Amazon Bedrock (set READINESS_LLM_PROVIDER accordingly; a Bedrock adapter is tracker item LLM-03) |
