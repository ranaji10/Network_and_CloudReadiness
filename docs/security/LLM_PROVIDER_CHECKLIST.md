# LLM provider checklist

Complete one copy of this template per deployment before setting `READINESS_ALLOW_LLM_EGRESS=true`.
Store the completed copy with the deployment record (outside this repository if it names a client).
`READINESS_LLM_PROVIDER=mock` needs no checklist.

| Item | Answer |
|---|---|
| Deployment / environment | |
| Provider and product (e.g. Vertex AI Gemini, Anthropic API, Bedrock) | |
| Model id | |
| Data-use terms confirmed: provider does not train on inputs | yes / no, link to terms |
| Retention: zero-data-retention or stated retention window | window: |
| Region or location where inference runs; matches client residency requirement | |
| Enterprise agreement / DPA in place with the provider | yes / no, reference |
| `READINESS_REDACTION_MODE` to be used (`pseudonymize` required unless the client waives it in writing) | |
| `READINESS_INCLUDE_EVIDENCE_SNIPPETS` stays `false` for shared reports | yes / no |
| Client informed and consent recorded (where the client's documents will be sent) | yes / no, date |
| Audit logging destination confirmed | |
| Who approved (name, role) | |
| Date approved | |
| Review date (max 12 months) | |

Switching provider later is a configuration change (`READINESS_LLM_PROVIDER`, model id, credentials in the
secret store) and a fresh copy of this checklist.
