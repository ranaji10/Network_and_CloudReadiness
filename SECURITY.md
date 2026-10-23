# Security

## Reporting a vulnerability or a data exposure

Do not open a public issue. Use the private channel agreed inside the organisation (see
`.github/ISSUE_TEMPLATE/security.md` for what to include) or GitHub private vulnerability reporting if it
is enabled on this repository. If client data has been exposed, follow
`docs/runbooks/INCIDENT_DATA_LEAK.md` immediately, then report.

## Supported versions

Only the `main` branch and the latest tagged release receive fixes.

## Confidentiality commitments (one screen)

| Commitment | How it is kept |
|---|---|
| Client documents never enter version control | `.gitignore`, `scripts/check_no_client_data.py`, gitleaks in CI and pre-commit |
| Secrets never enter version control or logs | gitleaks, `config/redaction.yaml` `kind: secret` rules always on, audit log rejects content-sized fields |
| No text reaches an external model unless an operator opts in | `READINESS_ALLOW_LLM_EGRESS=false` default, enforced in `guardrails/policy.py` and `adapters/registry.py` |
| What does reach a model is redacted and delimited as untrusted | `guardrails/redaction.py`, `guardrails/policy.GuardedLLM` |
| Reports do not contain identifiers the policy would hide | scoring runs on redacted text; snippets off by default |
| Tenants are isolated | tenant id prefix on workspace and buckets; one project per client recommended |
| Stored client data expires | 90-day lifecycle on buckets (Terraform), per-run workspace folders |
| No account-specific values in the repo | `scripts/check_portability.py` in CI |
| Runtime and build identities are least privilege | dedicated service accounts with bucket-scoped roles in `infra/terraform/gcp` |

Details: `docs/security/DATA_HANDLING_POLICY.md`, `docs/security/THREAT_MODEL.md`,
`docs/security/GUARDRAILS.md`, `docs/security/LLM_PROVIDER_CHECKLIST.md`.
