# Rule engine first, LLM second

Status: accepted
Date: 2026-10-23

## Context
V1 relied on model calls for every stage, which made scores non-reproducible, expensive, and
impossible to run without sending client text to a model.

## Decision
Scoring is a deterministic rule engine (`scoring/engine.py`) over signals declared in YAML. An LLM
judge is optional (`READINESS_USE_LLM_JUDGE`), runs per pillar, and may override a rule verdict only
above a configured confidence. The mock provider is the default, so the full pipeline runs offline.

## Consequences
- Same documents, same score, every time; CI can assert on scores.
- The judge improves nuance where enabled but can never be the only source of a score.
- Signal lists need tuning against real packs (SCR-04); the rules are only as good as their YAML.
