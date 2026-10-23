# CLAUDE.md: how to work in this repository

These are the operating rules for any coding agent (Claude Code, Claude Cowork, Codex, Gemini CLI, a
human with a terminal) working in this repository. `CLAUDE.md` is the canonical copy; `AGENTS.md` must
stay byte-identical below the first heading. If you change one, change the other.

## 1. Before you write code

1. Read `docs/planning/TRACKER.md`. Pick a story whose status is `todo` and whose dependencies are `done`.
2. Claim it: edit `docs/planning/tracker/<EPIC>.yaml`, set `status: in_progress`, `owner: <your handle>`
   (`claude-code`, `claude-cowork`, or a person's handle) and `branch: <type>/<STORY-ID>-<slug>`.
   Run `make tracker` and commit that change on its own first. Whoever pushes the claim first owns the story.
3. Branch from `main`: `git checkout -b feat/ING-04-drive-source`. Types: `feat`, `fix`, `docs`, `infra`, `chore`.
   If a session has a designated branch (for example `claude/trusting-keller-qe5w65`), use that branch instead and
   still record it in the tracker.
4. Read the directories you will touch and the matching doc in `docs/architecture/` before editing.

## 2. Hard rules (CI enforces most of them)

- **Never commit client or organisation data.** Nothing under `data/`, `workspace/`, `uploads/`, `reports/`,
  no `*.tfvars`, no `.env`, no `backend.*.hcl`, no credentials of any kind. `scripts/check_no_client_data.py`,
  `.gitignore` and gitleaks block the obvious cases; you are responsible for the rest.
- **Never put account-specific values in tracked files**: project ids, billing accounts, bucket names,
  e-mail addresses, client names, hostnames, IPs. They belong in `.env`, `envs/<env>.tfvars` or a secret store.
  `scripts/check_portability.py` fails the build if it finds them.
- **All cloud-specific code lives in `src/readiness/adapters/`** and implements a protocol from
  `src/readiness/ports/__init__.py`. No cloud SDK import anywhere else. New provider = new adapter + a line in
  `adapters/registry.py`.
- **Product behaviour is configuration.** Weights, checks, signals, thresholds, products and redaction rules
  are YAML under `config/`. Do not hard-code them in Python.
- **The mock LLM stays the default.** `READINESS_LLM_PROVIDER=mock` and `READINESS_ALLOW_LLM_EGRESS=false`
  unless an operator changes them at deploy time. Never flip these in code, tests or committed config.
- **Document text is untrusted.** Anything that sends text to a model goes through `guardrails.policy.GuardedLLM`.
- **Logs and audit records carry metadata only**, never document content. `AuditLog.event` rejects long strings.
- Run `make check` before every push. A red `make check` is never pushed.

## 3. Where things live

| Need | Path |
|---|---|
| Orchestration | `src/readiness/pipeline.py` |
| Domain models | `src/readiness/models.py` |
| Settings / env contract | `src/readiness/config.py`, `.env.example` |
| Ports (interfaces) | `src/readiness/ports/__init__.py` |
| Adapters and the factory | `src/readiness/adapters/**`, `adapters/registry.py` |
| Text extraction and classification | `src/readiness/ingestion/` |
| Redaction, egress policy, audit | `src/readiness/guardrails/` |
| Scoring engine, profile loader, CCM catalog | `src/readiness/scoring/` |
| Recommendations | `src/readiness/recommend/engine.py` |
| Report rendering | `src/readiness/report/markdown.py` |
| HTTP API / CLI / ADK agent | `src/readiness/api/app.py`, `src/readiness/cli.py`, `src/readiness/agents/` |
| Tunable product config | `config/profiles/`, `config/scoring/`, `config/recommendations/catalog.yaml`, `config/redaction.yaml` |
| Tests and synthetic fixtures | `tests/`, `tests/fixtures/synthetic_acme/` |
| Infra | `infra/terraform/gcp/`, `infra/terraform/aws/`, `infra/scripts/`, `cloudbuild.yaml`, `Dockerfile` |
| Planning | `docs/product/`, `docs/planning/tracker/*.yaml`, `docs/planning/TRACKER.md`, `docs/decisions/ADR-*.md` |
| Security policy and guardrail list | `docs/security/` |

## 4. Commands

| Command | Purpose |
|---|---|
| `uv sync --group dev` | create `.venv` with dev tools |
| `make check` | lint, format check, tests, portability check, client-data check, tracker sync check (CI gate) |
| `make test` / `make lint` / `make fmt` | the individual pieces |
| `make demo` | offline assessment of the synthetic sample |
| `make tracker` | re-render `docs/planning/TRACKER.md` after editing tracker YAML |
| `make catalog` | regenerate the CCM/CAIQ JSON from `reference/` |
| `make secrets-scan` | gitleaks over the working tree |
| `make serve`, `make docker-build`, `make docker-run` | run the API locally |
| `make tf-init ENV=dev`, `make tf-plan`, `make tf-apply` | Terraform for GCP (needs `envs/dev.tfvars` and `backend.dev.hcl`) |
| `uv run readiness --help` | CLI (`assess`, `profiles`, `checks`, `controls`, `redact`, `serve`) |

## 5. Recipes

**Add a check.** Edit the right `config/scoring/<domain>.yaml`: add an entry under a pillar with a unique
`id` (`NS-`, `CR-`, `AI-` prefix), `title`, `points`, `ccm` ids that exist in the catalog, `signals` and
optionally `strong_signals`, `negative_signals`, `doc_classes`, `question`. Then add a matching entry to
`config/recommendations/catalog.yaml` (the test `test_every_check_has_catalog_entry_and_valid_ccm_ids`
fails otherwise). Run `make test`.

**Add or change a recommendation.** Edit `config/recommendations/catalog.yaml`. Keep at least one `gcp`,
one `aws` and one `oss` option where a product exists; use `process` for non-technical actions.

**Add a profile.** Copy `config/profiles/default.yaml` to `config/profiles/<id>.yaml`, change `id`, domain
weights, thresholds and `target_providers`. It is picked up automatically (`readiness profiles`).

**Add a provider adapter.** Create `src/readiness/adapters/<kind>/<name>.py` implementing the protocol
from `ports/__init__.py` with lazy SDK imports inside `__init__`. Register it in `adapters/registry.py`.
Add the SDK to an optional extra in `pyproject.toml`. Add a unit test that uses a fake client; never a live account.

**Add a redaction rule.** Edit `config/redaction.yaml` (`kind: secret` rules are always applied). Add a case
to `tests/test_redaction.py` and try it with `uv run readiness redact <file>`.

**Record a decision.** Create `docs/decisions/ADR-YYYYMMDD-<slug>.md` (date-based names avoid number
collisions between parallel branches).

## 6. Definition of done

- `make check` green locally and in CI; new behaviour has a test.
- Config changes documented in the YAML comments; code changes documented where the module docstring describes them.
- Tracker story set to `done` with the PR link; `make tracker` run.
- No new account-specific value, no new cloud SDK import outside adapters, mock LLM still the default.
- If the change affects data handling, `docs/security/GUARDRAILS.md` or `DATA_HANDLING_POLICY.md` is updated in the same PR.

## 7. PR etiquette

- One story per PR. Small PRs merge faster and conflict less.
- Title: `<type>(<STORY-ID>): <summary>` (conventional commits). Fill in `.github/PULL_REQUEST_TEMPLATE.md`.
- Do not force-push shared branches. Rebase your own branch on `main` before asking for review.
- Reply to every review comment, resolve the thread when addressed.
- Security-sensitive paths (see `.github/CODEOWNERS`) need a review from the security owner.
