# Migration playbook

## A. Personal GCP account to an organisation account or a new project

Estimated effort: an afternoon. Nothing in the repository changes except git-ignored files.

1. **New project**: create it under the organisation; link billing; note `PROJECT_ID`.
2. **Bootstrap**: `PROJECT_ID=<new> REGION=<region> ENV=prod ./infra/scripts/bootstrap_gcp.sh`
   (enables APIs, creates the state bucket, writes `infra/terraform/backend.prod.hcl` and `envs/prod.tfvars`).
3. **Review `envs/prod.tfvars`**: `use_cmek`, `report_retention_days`, `billing_account`, `create_build_trigger`.
4. **Apply**: `make tf-init ENV=prod && make tf-plan ENV=prod && make tf-apply ENV=prod`.
   To move existing state instead of creating fresh resources, run
   `terraform init -migrate-state -backend-config=../backend.prod.hcl` in `infra/terraform/gcp` and then
   `terraform apply -var-file=envs/prod.tfvars`; resources whose names embed the project id (buckets) are recreated.
5. **Secrets**: add versions in the new project (`gcloud secrets versions add READINESS_API_TOKEN --data-file=-`, same for model keys). Never copy values through files in the repo.
6. **Cloud Build**: in the new project, Cloud Build > Repositories > connect GitHub (interactive). Then either
   set `create_build_trigger=true` with `github_connection` and `github_repo_uri` and re-apply, or create the
   trigger by hand with the substitutions from `terraform output cloudbuild_substitutions`.
7. **Cut over**: run the pipeline once with `_DEPLOY=true`; check `/healthz` (see `docs/runbooks/DEPLOY_GCP.md`); point any client-facing gateway or IAP at the new service.
8. **Decommission the old project**: disable the old trigger, delete bucket objects (versioned: all versions), delete the Cloud Run service, remove the Terraform state or destroy with the old tfvars, then shut the project down after the retention period.
9. Record the move in an ADR and update the provider checklist if the model provider or region changed.

## B. GCP to AWS

Already in place: `S3Source`, `S3BlobStore`, `AWSSecretsManagerStore`, the Anthropic adapter, the Terraform
skeleton in `infra/terraform/aws/`. Missing: a validated App Runner/ECS service definition (INF-06) and a
Bedrock `LLMProvider` (LLM-03) if you want models billed through AWS.

1. Complete INF-06 and apply the AWS Terraform with `region` and an `env`.
2. Build and push the same image to ECR (GitHub Actions `docker` job can push with OIDC; add a workflow).
3. Set the runtime environment: `READINESS_PROVIDER=aws`, `AWS_REGION`, `READINESS_S3_BUCKET_UPLOADS`, `READINESS_S3_BUCKET_REPORTS`, `READINESS_LLM_PROVIDER` (`anthropic` today, `bedrock` after LLM-03), `READINESS_API_TOKEN` from Secrets Manager.
4. Run the synthetic sample through `POST /assessments/upload` and compare the JSON with a GCP run; scores must be identical because scoring is provider-independent.
5. Complete a new provider checklist.

## C. Any provider to fully on-premises

`docker compose up` with `READINESS_PROVIDER=local` and `READINESS_LLM_PROVIDER=mock`. Documents in
`./data`, reports in `./workspace`. No outbound network is required. A self-hosted model adapter
(for example an OpenAI-compatible local endpoint) would be a new `LLMProvider` adapter.

## D. Checklist of things that are not portable and how we contained them

| Item | Where | What to do when moving |
|---|---|---|
| Vertex `global` location for Gemini 3 | `adapters/llm/gemini.py`, `agents/adk_app.py` | nothing; irrelevant off GCP |
| ADK / Agent Engine | `agents/` optional extra | re-host as a plain API client or on the target's agent runtime; the pipeline is unchanged |
| Cloud Build substitutions and `gcloud run deploy` | `cloudbuild.yaml` | GitHub Actions already runs the gate; add a deploy job for the target |
| Google Drive source | `adapters/sources/gdrive.py` | still works from any provider with Google credentials; or export the Drive folder to the target bucket |
| Terraform GCS backend | `versions.tf` | AWS uses the S3 backend in `aws/main.tf`; state is per provider |
| Bucket names embedding the project id | Terraform | expected to change; the app reads them from env |
