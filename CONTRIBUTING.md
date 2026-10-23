# Contributing

This guide is for people. Coding agents follow `CLAUDE.md` / `AGENTS.md`, which contain the same rules in
agent-oriented form. Read both if you work with agents.

## Setup

```bash
uv sync --group dev        # Python 3.12, creates .venv
cp .env.example .env       # optional; defaults run offline
make demo                  # confirm everything works
```

Optional extras: `uv sync --extra gcp` (GCS, Drive, Gemini), `--extra anthropic`, `--extra aws`, `--extra adk`.

## Workflow

1. Pick or create a story in `docs/planning/tracker/<EPIC>.yaml`, claim it (owner, branch, `in_progress`), run `make tracker`, commit.
2. Branch: `<type>/<STORY-ID>-<slug>` from `main`.
3. Make the change, add or update tests, update docs in the same PR.
4. `make check` must be green. Run `make secrets-scan` if you touched anything that could contain a secret.
5. Open a PR using the template. One approval merges; security-sensitive paths require the security code owner.
6. Set the story to `done` with the PR link, run `make tracker`, include it in the PR.

Full rules on parallel work: `docs/collaboration/WORKING_AGREEMENT.md`.

## Code style

- Python 3.12, type hints everywhere, pydantic models for data that crosses a boundary.
- `ruff` for lint and format, line length 120 (see `pyproject.toml`). `make fmt` fixes most things.
- Module docstrings explain *why* the module exists. Comments explain decisions, not syntax.
- No cloud SDK imports outside `src/readiness/adapters/`. Lazy-import SDKs inside adapter constructors.
- Behaviour lives in YAML under `config/`; Python reads it.

## Tests

- `pytest`, fixtures in `tests/conftest.py`. Tests never read a developer's `.env` and never call a network.
- Every new check needs a catalog entry (a test enforces it). Every new adapter needs a test with a fake client.
- Test data is synthetic. Put it in `tests/fixtures/` with a README that says so.

## Docs

- Architecture and security docs live in `docs/`; keep them current in the same PR as the code.
- Decisions: `docs/decisions/ADR-YYYYMMDD-<slug>.md`.
- Planning: `docs/product/ROADMAP.md` and the tracker.

## Commit messages

Conventional commits with the story id: `feat(ING-04): read Google Drive folders recursively`,
`fix(GRD-02): mask JWTs in connection strings`, `docs(DOC-01): add deploy runbook`. Body explains why.

## Review rules

- One approval from someone who did not write the change.
- Paths in `.github/CODEOWNERS` (guardrails, redaction config, infra, CI) need the listed owner.
- Reviewers check: tests, no account-specific values, config over code, docs updated, tracker updated.
