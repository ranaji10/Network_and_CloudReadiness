# Runbook: deliver the agent to Vertex AI Agent Engine and Gemini Enterprise

Goal: every merge to `main` updates the ADK agent that users see in Gemini Enterprise, with no manual
step. This continues the V1.1 path; the half-built flow-builder agent in the Agent Platform UI cannot
pull code from GitHub, so it is replaced by the ADK agent below once that is registered.

How it fits together:

```
GitHub main ──push──> Cloud Build (cloudbuild.yaml)
                        ├─ quality gate, secret scan, image build            (always)
                        ├─ push image + gcloud run deploy  (_DEPLOY=true)    -> Cloud Run API + web UI
                        └─ adk deploy agent_engine        (_DEPLOY_AGENT=true)
                                 │  updates reasoningEngines/<_AGENT_ENGINE_ID>
                                 ▼
                     Vertex AI Agent Engine  <──registered once──  Gemini Enterprise app (Agents > Add agent)
```

The agent code is `src/readiness/agents/` (ADK app: `agent.py` exposes `root_agent`). It calls the same
`readiness.pipeline` as the CLI and API. The package and its YAML config are staged alongside the agent
with `--extra_packages src/readiness --extra_packages config`; `readiness.config.resolve_default_config_dir`
finds the staged `config/` at runtime. Third-party dependencies come from
`src/readiness/agents/requirements.txt` (a test keeps it in sync with `pyproject.toml`).

## 1. One-time setup

1. Apply Terraform with `deploy_agent_engine = true` (creates `readiness-agent-<env>` and grants the build
   service account `roles/aiplatform.user`, `roles/storage.objectAdmin`, `roles/cloudbuild.builds.editor`
   and `iam.serviceAccountUser` on the agent identity). APIs: `aiplatform.googleapis.com` and
   `cloudresourcemanager.googleapis.com` are enabled by the bootstrap script.
2. On the `main` trigger set the substitutions from `terraform output cloudbuild_substitutions`
   (`_DEPLOY_AGENT=true`, `_AGENT_SA=<agent SA email>`, `_AGENT_ENGINE_ID` empty for the first run).
3. Merge or re-run the build. The `deploy-agent-engine` step prints the new resource name
   `projects/<n>/locations/<region>/reasoningEngines/<id>`.
4. Put `<id>` into `agent_engine_id` in your tfvars (or directly into the trigger substitution
   `_AGENT_ENGINE_ID`) and apply. From now on every main build updates that instance in place.
   Until the id is pinned, the build looks up the newest instance with the same display name
   (`scripts/find_agent_engine.py`) and updates it rather than creating another; if you still end up
   with duplicates (builds that ran before this safeguard existed), keep the one whose id is on the
   trigger and delete the rest from Agent Platform > Deployments (more actions > Delete).
5. Register the agent in Gemini Enterprise: Google Cloud console > Gemini Enterprise > your app > Agents >
   Add agent > custom agent via Agent Engine, pick the reasoning engine above. Needs the Discovery Engine
   Admin role and the Discovery Engine API. Google's guide:
   https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent

Registration is a pointer to the Agent Engine instance, so later code updates do not need re-registration.

## 2. Local check before relying on the pipeline

```bash
uv sync --group dev --extra gcp --extra adk
READINESS_ALLOW_LLM_EGRESS=true READINESS_LLM_PROVIDER=gemini GOOGLE_CLOUD_PROJECT=<project> \
  uv run adk web src/readiness/agents           # chat locally; the agent calls run_readiness_assessment
uv run adk deploy agent_engine --project <project> --region <region> \
  --display_name readiness-assessor --extra_packages src/readiness --extra_packages config \
  --temp_folder /tmp/readiness-agent-stage \
  --service_account <agent SA email> src/readiness/agents
```

`--temp_folder` must point outside `src/readiness`: by default adk stages into a timestamped folder next to
the agent app, inside the tree that `--extra_packages src/readiness` copies, and the copy recurses into itself.

The model used by the agent is `READINESS_LLM_MODEL` (default `gemini-2.5-flash`), pinned to the
`global` Vertex location by `GlobalGemini` (the V1.1 workaround). The assessment tool itself stays
deterministic unless `READINESS_USE_LLM_JUDGE=true`.

## 3. Rollback

`gcloud ai reasoning-engines list --region <region>` shows versions; redeploying an older commit from
Cloud Build (Run trigger > pick commit) restores it. Deleting the instance breaks the Gemini Enterprise
registration, so prefer redeploying over deleting.

## 4. Cost control during the free-credit period

Agent Engine bills per vCPU/GiB-hour while an instance exists plus model tokens. One dev instance and
`min_instance_count = 0` on Cloud Run keep idle cost near zero; the Terraform budget alert
(`billing_account`, `monthly_budget_usd`) warns at 50/90/100%.
