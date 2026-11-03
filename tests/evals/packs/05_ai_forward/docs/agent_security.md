# Lumen Fox AI - Agent Security Standard (SYNTHETIC)

- Each agent has its own service account (non-human identity) with least privilege IAM roles and short-lived credentials.
- Secrets in Secret Manager only; secret scanning in CI; no secrets in prompts or code.
- Prompt injection and jailbreak defences: Model Armor content filter, DLP based PII redaction on inputs and output filtering.
- Tracing with OpenTelemetry and Langfuse; audit trail per tool call; token usage dashboards (LLM observability).
- Evaluation: golden set regression test, benchmark suite and a red team review before every release.
