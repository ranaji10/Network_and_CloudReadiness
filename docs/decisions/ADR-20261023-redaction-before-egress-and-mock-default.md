# Redaction before any egress, and no egress by default

Status: accepted
Date: 2026-10-23

## Context
The tool reads the most sensitive documents a business has. Any path from a document to a model,
a log or a shared report is a leak path.

## Decision
- `READINESS_LLM_PROVIDER` defaults to `mock`; a real provider raises unless
  `READINESS_ALLOW_LLM_EGRESS=true`.
- All document text passes `guardrails/redaction.py` before scoring, so neither prompts nor reports
  can contain an identifier the policy hides. Secrets are masked in every mode; identifiers are
  pseudonymised with a per-run mapping that never leaves the local workspace.
- `GuardedLLM` wraps every provider: it redacts, declares document text untrusted, and audits.
- The audit log refuses string fields longer than 200 characters.

## Consequences
- Enabling a real model is a deliberate, reviewable step (GRD-04 before LLM-01).
- Pseudonyms slightly reduce model accuracy; accepted.
- Redaction patterns need review on real data; false negatives are the main residual risk.
