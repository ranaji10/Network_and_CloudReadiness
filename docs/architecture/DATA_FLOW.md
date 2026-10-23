# Data flow

What happens to a client document from the moment the tool reads it, what is stored where, and what can
reach an external model.

```
source (file / gs / s3 / gdrive)
  │  bytes (never stored by the tool; read on demand)
  ▼
extract_text  ──►  text (in memory, capped at max_text_chars)
  ▼
classify      ──►  DocClass + confidence (metadata)
  ▼
Redactor      ──►  redacted text (secrets masked; identifiers masked or pseudonymised)
  │                mapping token→original kept in memory
  ▼
score_domain  ──►  CheckResult per check: status, points, evidence (doc id, name, signal; snippet only if enabled)
  │
  ├─ if use_llm_judge ─► GuardedLLM ─► redacted text in <document> tags + preamble ─► provider ─► JudgeBatch (schema)
  ▼
recommend     ──►  actions (catalog) + discovery (CAIQ questions)
  ▼
AssessmentReport (JSON) + Markdown
```

## What is stored, where, by whom

| Artefact | Content | Local provider | GCP provider | Lifetime |
|---|---|---|---|---|
| Source documents | raw client files | wherever the analyst put them (`data/`, git-ignored) | uploads bucket, tenant prefix | analyst deletes / 90-day lifecycle |
| Extracted text | redacted text | memory only | memory only | process lifetime |
| `report.json` | scores, check results, evidence doc names, optional snippets, recommendations | `workspace/<tenant>/<run>/` | reports bucket `<tenant>/<run>/` | until deleted / 90 days |
| `report.md` | same, rendered | same | same | same |
| `audit.jsonl` | events with run id, tenant, doc ids, hashes, counts, classes; no content | same | same (and stdout logs) | same |
| `pseudonym_mapping.local.json` | token to original identifier map | written only when provider is `local` and mode is `pseudonymize` | never written | analyst machine only |
| Temporary upload folder (API) | raw uploaded files | OS temp dir, deleted after the request | same (container ephemeral disk) | request lifetime |

## What can reach an external model

Only when `READINESS_LLM_PROVIDER` is not `mock` **and** `READINESS_ALLOW_LLM_EGRESS=true` **and**
`READINESS_USE_LLM_JUDGE=true` (or a future classifier flag):

- the system prompt (`JUDGE_SYSTEM` + untrusted-data preamble),
- the list of check ids and questions for one pillar,
- each relevant document's **redacted** text, truncated to a per-document budget, inside `<document>` tags.

Never: raw bytes, un-redacted text, the pseudonym map, secrets, file paths, tenant ids, previous reports.

## What reaches logs

Structured log lines and audit events carry: run id, tenant id, document ids and hashes, byte and
character counts, classification, truncation flag, extraction error type, LLM provider name, schema name,
prompt length, scores. `AuditLog.event` raises if any string field exceeds 200 characters, which blocks
accidental content logging at the source.
