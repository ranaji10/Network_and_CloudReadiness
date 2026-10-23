# Working agreement: humans and agents in parallel

Several people and several coding agents (Claude Cowork, Claude Code, others) work on this repository at
the same time, often without talking to each other. These rules make that safe.

## 1. The tracker is the shared brain

- `docs/planning/tracker/<EPIC>.yaml` is the source of truth. `docs/planning/TRACKER.md` is rendered from it by `make tracker`; never edit the Markdown by hand.
- One file per epic, so two people claiming stories in different epics never touch the same file.
- Every story has `id`, `title`, `status` (`todo`, `in_progress`, `blocked`, `done`), `owner`, `branch`, `depends_on`, `notes`.
- Read the tracker at the start of every session. It replaces stand-ups for asynchronous work.

## 2. Claim by commit

1. Choose a `todo` story whose `depends_on` are `done`.
2. Set `status: in_progress`, `owner`, `branch` in the YAML. Run `make tracker`. Commit **only that change** and push it (on `main` directly if branch protection allows docs-only commits; otherwise as the first commit of your branch, then a tiny PR).
3. If a push is rejected because someone claimed the same story first, pull, pick another story.
4. Agents put a recognisable value in `owner`: `claude-cowork`, `claude-code`, `codex`, `gemini-cli`, or `<agent>/<human handle>` when a person supervises. Humans use their GitHub handle.
5. A story that stays `in_progress` with no commits for 7 days may be reclaimed; note it in `notes`.

## 3. One story, one branch, one PR

- Branch: `<type>/<STORY-ID>-<slug>`. A session with a designated branch (for example `claude/trusting-keller-qe5w65`) uses that branch and records it in the tracker.
- Keep PRs small (one story, typically under 500 changed lines excluding generated files). Split large stories in the tracker first.
- Do not bundle unrelated refactors. If you see something to fix outside your story, create a story.

## 4. Module ownership map (what is independent)

| Area | Paths | Can be worked in parallel with |
|---|---|---|
| Ingestion | `src/readiness/ingestion/`, `src/readiness/adapters/sources/` | everything else |
| Scoring config | `config/scoring/<domain>.yaml` (one file per domain) | other domains, code |
| Recommendations | `config/recommendations/catalog.yaml` | code; coordinate when two people edit the same domain's entries, or split the file per domain (allowed, loader change needed) |
| Scoring engine | `src/readiness/scoring/` | config, adapters, API |
| Guardrails | `src/readiness/guardrails/`, `config/redaction.yaml` | everything except pipeline wiring |
| LLM adapters | `src/readiness/adapters/llm/` | all other adapters |
| Storage / secrets adapters | `src/readiness/adapters/storage/`, `adapters/secrets/` | all other adapters |
| API and CLI | `src/readiness/api/`, `src/readiness/cli.py` | engine internals |
| ADK agent | `src/readiness/agents/` | everything |
| Infra | `infra/`, `cloudbuild.yaml`, `Dockerfile`, `.github/workflows/` | application code |
| Docs | `docs/**` (one file per topic) | everything |

Shared files to touch with care (coordinate in the story notes first): `src/readiness/pipeline.py`,
`src/readiness/models.py`, `src/readiness/config.py`, `adapters/registry.py`, `pyproject.toml`, `Makefile`.

## 5. Files designed not to conflict

| Risk | Design |
|---|---|
| Everyone edits one tracker file | one YAML per epic; Markdown is generated |
| Sequential ADR numbers collide on parallel branches | ADRs are `ADR-YYYYMMDD-<slug>.md` |
| One giant scoring file | one YAML per domain, unique id prefixes (`NS-`, `CR-`, `AI-`) |
| One giant catalog | entries keyed by check id; splitting per domain is allowed |
| Two agents add the same adapter | claim the story first; registry has one line per provider |

## 6. Merge and rebase rules

- `main` is always green. Merge only with CI green and the tracker updated.
- Rebase your branch on `main` before review; never rebase or force-push someone else's branch. Use a merge commit to bring `main` into a shared branch.
- Merge order when two PRs touch shared files: the one that was claimed first merges first; the other rebases.
- Generated files (`TRACKER.md`, `ccm_v4.1.json`, `uv.lock`) are regenerated, never hand-merged.

## 7. When blocked

- Set `status: blocked`, write why in `notes`, run `make tracker`, commit, push. Then pick another story.
- If blocked on a decision, write an ADR draft in `docs/decisions/` with the options and open a PR for discussion.
- If blocked on credentials or cloud access, say so in `notes`; do not work around it with personal credentials.

## 8. Definition of done

See `CLAUDE.md` section 6. In short: `make check` green, tests added, docs and tracker updated, no
account-specific values, no new cloud SDK import outside adapters, mock LLM still default.

## 9. Communication

- Progress: the tracker and PR descriptions. Decisions: ADRs. Questions: PR comments or the issue templates.
- Keep client names and client data out of all of it.
