# Cloud Build is the primary CI, GitHub Actions mirrors it

Status: accepted
Date: 2026-10-23

## Context
A Cloud Build trigger already exists on the repository and was failing because there was nothing to
build. Contributors on forks and agents without GCP access still need a gate they can see.

## Decision
`cloudbuild.yaml` runs the quality gate (lint, tests, policy checks), a secret scan, and the
container build on every push; push and deploy are gated by `_DEPLOY=true`. A GitHub Actions
workflow runs the same quality gate so pull requests show status without GCP. The gate is
`make check` in both places.

## Consequences
- The existing trigger goes green with no cloud resources.
- Deployment is a substitution flip, so the same pipeline serves dev, staging and prod.
- Two CI definitions must stay in step; both call the same Make targets to limit drift.
