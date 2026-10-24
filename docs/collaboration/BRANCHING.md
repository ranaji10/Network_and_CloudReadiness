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

## GitHub ruleset for `main` (what to activate)

GitHub nags until the default branch is protected. Use a *ruleset* (Settings > Rules > Rulesets > New ruleset >
New branch ruleset), which is the current mechanism and works on personal repositories:

| Setting | Value | Why |
|---|---|---|
| Ruleset name / enforcement | `main`, Active | |
| Target branches | Default branch | |
| Bypass list | Repository admin (you) | emergency fixes without disabling the ruleset |
| Restrict deletions | on | |
| Block force pushes | on | history on `main` is the audit trail |
| Require a pull request before merging | on, required approvals 0 while you work alone (1 once a second person joins) | every change arrives through CI |
| Dismiss stale approvals, require conversation resolution | on | |
| Require review from Code Owners | off until `.github/CODEOWNERS` lists real teams and approvals > 0 | with approvals 0 it has no effect |
| Require status checks to pass | on: `quality`, `secrets`, `docker` | the GitHub Actions jobs; do not add the Cloud Build check, it runs after the merge |
| Require branches to be up to date before merging | on | Dependabot and agents must rebase on the latest `main` first |
| Require linear history | off | the working agreement allows merge commits |
| Require signed commits | off | agent sessions do not sign commits |

Also under Settings > General > Pull Requests: enable **Allow auto-merge** and **Automatically delete head
branches**. Auto-merge is what `.github/workflows/dependabot-automerge.yml` relies on; branch deletion
keeps the branch list to live work only.

### Dependabot policy

Minor and patch updates auto-merge once `quality`, `secrets` and `docker` pass (the workflow above enables
auto-merge on the PR; the ruleset decides when it actually merges). Major updates are left open with a note
and need a human to read the changelog. Action bumps arrive as one grouped PR per month so they cannot
conflict with each other; Python minor and patch bumps are grouped the same way.

## Cloud Build

The existing trigger builds every push. Keep `_DEPLOY=false` on branch builds; a second trigger on
`^main$` (or a tag pattern) carries `_DEPLOY=true`. See `docs/runbooks/DEPLOY_GCP.md`.
