# Scoring, recommendations and redaction live in YAML, not code

Status: accepted
Date: 2026-10-23

## Context
Domain experts need to tune pillars, weights, signals, control mappings and product options without
touching Python, and clients will want profiles of their own.

## Decision
`config/scoring/*.yaml`, `config/profiles/*.yaml`, `config/recommendations/catalog.yaml` and
`config/redaction.yaml` are the product's behaviour. Python validates them with pydantic on load and
fails fast on a typo. Tests assert that every check has a recommendation and valid CCM ids.

## Consequences
- A new check or profile is a reviewable YAML diff.
- Config files need versions (`version:`) because changing them changes scores.
- The config schema is an API; `DOC-04` documents it.
