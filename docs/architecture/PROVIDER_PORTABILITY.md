# Provider portability

Goal: moving between Google accounts, to another GCP project, or to another cloud is a configuration and
infrastructure change, never an application code change.

## The rule

**No cloud SDK import outside `src/readiness/adapters/`.** Adapters import SDKs lazily inside their
constructors, so the core installs and runs with no cloud dependency. The only place that maps a provider
name to an adapter is `src/readiness/adapters/registry.py`.

## Ports and adapters

| Port (`ports/__init__.py`) | local | GCP | AWS | Other |
|---|---|---|---|---|
| `DocumentSource` (list, read) | `sources/local_fs.py` implemented, tested | `sources/gcs.py` implemented, untested live; `sources/gdrive.py` implemented, untested live (ING epic) | `sources/s3.py` implemented, untested live | SharePoint / OneDrive: todo (ING epic) |
| `LLMProvider` (generate_structured) | `llm/mock.py` implemented, tested | `llm/gemini.py` (Vertex via ADC or API key) implemented, untested live | Bedrock: todo (LLM-03) | `llm/anthropic_llm.py` implemented, untested live |
| `BlobStore` (put, get, exists) | `storage/local.py` implemented, tested | `storage/gcs.py` implemented, untested live | `storage/s3.py` implemented, untested live | |
| `SecretStore` (get) | `secrets/env.py` implemented | `secrets/gcp_secret_manager.py` implemented, untested live | `secrets/aws_secrets_manager.py` implemented, untested live | |

"Untested live" means unit-level only; validating each against a real account is a tracker story.

## The environment contract

Everything the application needs is an environment variable listed in `.env.example` and parsed by
`src/readiness/config.py`. Switching is a matter of:

| Move | Variables that change |
|---|---|
| Personal GCP project to org GCP project | `GOOGLE_CLOUD_PROJECT`, bucket names (set by Terraform), secret values |
| GCP to AWS | `READINESS_PROVIDER=aws`, `AWS_REGION`, `READINESS_S3_BUCKET_*`, `READINESS_LLM_PROVIDER` (anthropic or, once built, bedrock) |
| Gemini to Claude or back | `READINESS_LLM_PROVIDER`, `READINESS_LLM_MODEL`, the matching key in the secret store, a new provider checklist |
| Online to fully offline | `READINESS_PROVIDER=local`, `READINESS_LLM_PROVIDER=mock` |

## Infrastructure per provider

| | GCP | AWS |
|---|---|---|
| Terraform | `infra/terraform/gcp/` (primary) | `infra/terraform/aws/` (skeleton, INF-06) |
| Account-specific input | `envs/<env>.tfvars` (git-ignored) + `backend.<env>.hcl` (git-ignored) | same pattern |
| CI | Cloud Build (`cloudbuild.yaml`) and GitHub Actions run the same gate | GitHub Actions already provider-neutral; CodeBuild optional |
| Secrets | Secret Manager shells created by Terraform, values added by hand | Secrets Manager shells |

## Known non-portable spots and how they are contained

| Spot | Containment |
|---|---|
| Gemini 3 models only served from the `global` Vertex location | `GOOGLE_CLOUD_LOCATION=global` default; logic only in `adapters/llm/gemini.py` and `agents/adk_app.py` |
| ADK / Agent Engine hosting | optional extra, `agents/` package only; the pipeline does not depend on it |
| Cloud Build substitutions (`_DEPLOY`, `_REGION`, ...) | mirrored by `.github/workflows/ci.yml`; deploy step is a plain `gcloud run deploy` that could be swapped for any CLI |
| Google Drive export MIME types | inside `adapters/sources/gdrive.py` |

`scripts/check_portability.py` fails CI if a project id, billing account, bucket name, e-mail or similar
appears in a tracked file.
