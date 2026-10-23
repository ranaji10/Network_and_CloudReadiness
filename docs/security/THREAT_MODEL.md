# Threat model

## Assets

1. Client documents and everything derived from them (text, classifications, evidence, reports, pseudonym maps).
2. Operator secrets (model API keys, API tokens, cloud credentials, Terraform state).
3. Integrity of the score: a tampered configuration or prompt-injected verdict produces a wrong but plausible report.
4. Availability of the service for a running engagement (lower priority; reports can be regenerated).

## Actors

| Actor | Capability |
|---|---|
| Client (document author) | Can place arbitrary content, including instructions, in documents the tool reads |
| External attacker | Can reach the API if it is exposed; can submit uploads if they have a token |
| Operator staff / agents | Have repo write access and may run the tool against real data |
| Model provider | Receives whatever is sent to it; bound by its data-use terms |
| CI / build system | Runs code from the repo with build credentials |

## Trust boundaries

```
client source ──> DocumentSource ──> extract ──> classify ──> REDACT ──> score (rules)
   (untrusted)      (adapter)                                   │            │
                                                                ├──> GuardedLLM ──> model provider (external)
                                                                │
                                                        report / blob store / audit log
```

Everything left of REDACT is untrusted client data. Everything that leaves the process (model, bucket, log)
is on the right of it.

## Threats and mitigations

| # | Threat (STRIDE) | Mitigation in place | Where | Planned / story |
|---|---|---|---|---|
| T1 | Prompt injection via document content changes verdicts or exfiltrates instructions (Tampering, Information disclosure) | Documents wrapped in `<document>` tags with an explicit untrusted-data preamble; model must answer in a pydantic schema; LLM verdicts only override rules above a confidence threshold; rules run first and remain the baseline | `guardrails/policy.py`, `scoring/engine.py` | Output-side PII filter and injection detector: `GRD` epic |
| T2 | Secrets in documents reach the model, logs or report (Information disclosure) | `kind: secret` redaction rules run in every mode; scoring runs on redacted text so reports inherit it; audit log rejects fields over 200 chars; snippets off by default | `guardrails/redaction.py`, `guardrails/audit.py`, `config/redaction.yaml` | Presidio-based NER for names: `GRD` epic |
| T3 | Identifiers (IPs, hosts, e-mails) reach the model | Pseudonymise by default with stable per-run tokens; mapping never leaves the process except to a local-only file | `guardrails/redaction.py`, `pipeline.py` | |
| T4 | Real model called without approval (Information disclosure) | `READINESS_ALLOW_LLM_EGRESS=false` default; `Settings.require_llm_egress()` raised by both the factory and `GuardedLLM`; mock provider default in code, tests, Terraform | `config.py`, `adapters/registry.py`, `guardrails/policy.py`, `infra/terraform/gcp/variables.tf` | Provider checklist sign-off recorded in deployment: `docs/security/LLM_PROVIDER_CHECKLIST.md` |
| T5 | Path traversal in uploads or local source (Elevation of privilege) | Upload filenames reduced to basename; local source resolves symlinks and refuses paths outside its root; blob store refuses keys escaping its root; source schemes allow-listed | `api/app.py`, `adapters/sources/local_fs.py`, `adapters/storage/local.py`, `config.py` | |
| T6 | Cross-tenant read of reports (Information disclosure) | Tenant id prefixes every key and folder; API token per deployment; Cloud Run behind IAM, ingress internal/LB only | `pipeline.py`, `api/app.py`, Terraform | Per-tenant tokens and buckets: `GRD` epic; per-client project recommended |
| T7 | Unauthenticated API use (Spoofing) | Bearer token with constant-time compare; API refuses to start open unless `READINESS_AUTH_DISABLED=true`; Cloud Run requires IAM | `api/app.py`, Terraform | IAP / API gateway front door: `API` epic |
| T8 | Supply chain (Tampering) | `uv.lock` frozen installs; pinned base images; gitleaks and ruff security rules in CI; no cloud SDK outside adapters | `Dockerfile`, `cloudbuild.yaml`, `.github/workflows/ci.yml` | Dependency review / SBOM: `INF` epic |
| T9 | Over-privileged runtime or build identity (Elevation of privilege) | Dedicated service accounts; bucket-scoped roles; build SA limited to registry writer, run developer, logs | `infra/terraform/gcp/main.tf` | |
| T10 | Client data committed to git by a person or agent (Information disclosure) | `.gitignore` for data dirs and secret file patterns; `scripts/check_no_client_data.py`; gitleaks in pre-commit, CI and Cloud Build; CLAUDE.md rules | repo root, `scripts/`, `.pre-commit-config.yaml` | |
| T11 | Account-specific values leak into the repo, blocking migration and hinting at infrastructure (Information disclosure) | `scripts/check_portability.py` in CI | `scripts/` | |
| T12 | Denial of service via huge documents (Denial of service) | `max_doc_bytes` and `max_text_chars` limits; oversize uploads rejected with 413 | `config.py`, `ingestion/extract.py`, `api/app.py` | Rate limiting at the gateway: `API` epic |
| T13 | Tampered scoring config produces a misleading report (Tampering) | Config validated by pydantic; CODEOWNERS review on `config/`; profile version printed in the report | `scoring/profiles.py`, `.github/CODEOWNERS` | Signed config bundles: not planned |
| T14 | Repudiation: who ran what against which documents | Append-only audit log per run with run id, tenant, document ids and hashes, events | `guardrails/audit.py` | Ship audit log to central logging: `INF` epic |

## Out of scope for now

- Physical security of analyst laptops (operator policy).
- Malicious operator staff with repo and cloud admin rights.
- Attacks on the model provider itself.
