# Branching

Trunk-based development with short-lived branches.

| Rule | Value |
|---|---|
| Trunk | `main`, always deployable, always green |
| Feature branches | `<type>/<STORY-ID>-<slug>`, e.g. `feat/ING-04-drive-source`; type is `feat`, `fix`, `docs`, `infra`, `chore` |
| Agent session branches | `claude/<session-slug>` as assigned by the tool; recorded in the tracker like any branch |
| Lifetime | days, not weeks; rebase on `main` daily |
| Merge method | squash or merge commit, never rebase-merge of shared branches |
| Releases | tags `v<major>.<minor>.<patch>` on `main`; version in `pyproject.toml` and `src/readiness/__init__.py` bumped in the release PR |
| Hotfix | `fix/<STORY-ID>-<slug>` from `main`, tag a patch release |

## GitHub branch protection to configure on `main`

- Require status checks: `quality`, `secrets`, `docker` (GitHub Actions) and the Cloud Build check.
- Require 1 approving review; require review from code owners.
- Dismiss stale approvals on new pushes.
- Block force pushes and deletions.
- Require linear history is optional; squash merges keep it tidy.

## Cloud Build

The existing trigger builds every push. Keep `_DEPLOY=false` on branch builds; a second trigger on
`^main$` (or a tag pattern) carries `_DEPLOY=true`. See `docs/runbooks/DEPLOY_GCP.md`.
