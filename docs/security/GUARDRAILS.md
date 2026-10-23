# Guardrails

Each guardrail lists where it is implemented and how to prove it still works. Add a row whenever you add one.

## In code (runtime)

| Guardrail | Implemented in | How to test |
|---|---|---|
| Egress is off by default; a real model cannot be constructed without `READINESS_ALLOW_LLM_EGRESS=true` | `config.Settings.require_llm_egress`, `adapters/registry.make_llm`, `guardrails/policy.GuardedLLM.__init__` | `tests/test_pipeline.py::test_egress_guardrail_blocks_real_provider` |
| Every prompt is redacted before it reaches a provider | `guardrails/policy.GuardedLLM.generate_structured` | `tests/test_pipeline.py::test_llm_judge_uses_guarded_mock` asserts no fixture identifiers appear in prompts |
| Document text is delimited and declared untrusted in the system prompt | `guardrails/policy.UNTRUSTED_PREAMBLE`, `wrap_untrusted` | same test asserts the preamble is present |
| Model output must match a pydantic schema; free text is rejected | `ports.LLMProvider.generate_structured`, adapters | adapter unit tests with fake clients (`LLM` epic) |
| Secrets (keys, tokens, private keys, passwords, connection strings) are always masked, in every redaction mode | `config/redaction.yaml` rules with `kind: secret`; `Redactor.redact` | `tests/test_redaction.py::test_off_mode_still_masks_secrets` |
| Identifiers are pseudonymised with a stable per-run map that never leaves the process | `guardrails/redaction.Redactor` | `tests/test_redaction.py::test_pseudonymize_is_stable_and_masks_secrets` |
| Scoring runs on redacted text, so reports cannot contain hidden identifiers | `pipeline.run_assessment` (redaction happens before scoring) | `tests/test_pipeline.py::test_end_to_end_offline` asserts fixture IPs and e-mails are absent from the report |
| Evidence snippets are off unless explicitly requested | `Settings.include_evidence_snippets=False`, `--snippets` | `tests/test_scoring.py::test_snippets_only_when_requested` |
| Audit log stores metadata only; content-sized strings are refused | `guardrails/audit.AuditLog.event` | `test_end_to_end_offline` asserts secrets never appear in `audit.jsonl` |
| Pseudonym map is written only for local provider runs and marked `.local.json` (git-ignored pattern) | `pipeline.run_assessment` | `test_end_to_end_offline` |
| Local source cannot escape its root; symlinks resolved and checked | `adapters/sources/local_fs.LocalFolderSource` | unit test to add under `ING` epic |
| Blob store keys cannot escape the store root | `adapters/storage/local.LocalBlobStore._path` | unit test to add under `GRD` epic |
| Upload file names are reduced to a basename; oversize uploads rejected | `api/app.create_from_upload` | `tests/test_api.py` |
| Source schemes are allow-listed | `Settings.allowed_source_schemes`, `registry.make_source` | manual: set the list to `["file"]` and request `gs://` |
| API needs a bearer token unless explicitly disabled; constant-time compare | `api/app.auth` | `tests/test_api.py::test_api_requires_token_when_enabled` |
| Document size and text length caps | `Settings.max_doc_bytes`, `max_text_chars`; `ingestion/extract.extract_text` | `tests/test_pipeline.py` (truncated flag) |
| Tenant prefix on every output path and key | `pipeline.run_assessment`, `api/app._run` | `tests/test_api.py` round trip |

## In CI and the repo

| Guardrail | Implemented in | How to test |
|---|---|---|
| Client data directories and secret file patterns are ignored by git | `.gitignore` | `git check-ignore data/x.pdf .env infra/terraform/gcp/envs/dev.tfvars` |
| Tracked files are scanned for client-data-like content | `scripts/check_no_client_data.py` (in `make check`, Cloud Build, GitHub Actions) | `uv run python scripts/check_no_client_data.py` |
| Tracked files are scanned for account-specific values | `scripts/check_portability.py` | `uv run python scripts/check_portability.py` |
| Secret scanning on every push and before every commit | `.gitleaks.toml`, `.pre-commit-config.yaml`, `cloudbuild.yaml` step `secret-scan`, `.github/workflows/ci.yml` job `secrets` | `make secrets-scan` |
| Every check must have a recommendation and valid CCM ids | `tests/test_config_profiles.py` | `make test` |
| Security-sensitive paths need the security owner's review | `.github/CODEOWNERS` | GitHub branch protection |
| Same quality gate in Cloud Build and GitHub Actions, so no single CI is a bypass | `cloudbuild.yaml`, `.github/workflows/ci.yml` | both green on the PR |
| Deployments do not happen from a green build by accident | `_DEPLOY=false` default substitution | Cloud Build log shows "deploy skipped" |

## In infrastructure (Terraform)

| Guardrail | Implemented in |
|---|---|
| Buckets: uniform access, public access prevention enforced, versioning, 90-day lifecycle, optional CMEK | `infra/terraform/gcp/main.tf` |
| Dedicated runtime and build service accounts with bucket-scoped roles | `main.tf` |
| Cloud Run not public by default, ingress internal and load-balancer only, secrets mounted from Secret Manager | `main.tf` |
| Secret values never pass through Terraform (shells only) | `main.tf`, runbook |
| Optional budget alert | `main.tf` |

## In process

| Guardrail | Where |
|---|---|
| Provider checklist must be completed before egress is enabled | `docs/security/LLM_PROVIDER_CHECKLIST.md` |
| Data handling rules for analysts | `docs/security/DATA_HANDLING_POLICY.md` |
| Incident procedure | `docs/runbooks/INCIDENT_DATA_LEAK.md` |
| Agent and contributor rules | `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md` |

## Guardrails we deliberately do not have yet

| Gap | Why not yet | Story |
|---|---|---|
| Named-entity (person, organisation) redaction | Needs Presidio or a model; regex cannot do it reliably. The `pii` extra is declared but unused | `GRD` epic |
| Output filtering of model responses for leaked data | Rules-first scoring limits exposure; add when the LLM judge is enabled in production | `GRD` epic |
| Per-tenant API tokens and per-tenant buckets | One deployment per client is the recommended pattern today | `GRD` epic |
| Rate limiting and WAF in front of the API | Cloud Run IAM is sufficient while the API is internal | `API` epic |
| Central shipping of the audit log and alerting | Needs the deployment to exist first | `INF` epic |
| SBOM and dependency review | Lockfile is pinned; automate once CI is stable | `INF` epic |
| Encrypting local `workspace/` | Relies on analyst disk encryption today | not planned |
