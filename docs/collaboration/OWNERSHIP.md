# Ownership

Paths, the epic that owns them, and the reviewer role expected on changes. `.github/CODEOWNERS` mirrors
the security-sensitive rows with placeholder handles; replace them with real GitHub handles or teams.

| Path | Owning epic | Reviewer role |
|---|---|---|
| `src/readiness/guardrails/`, `config/redaction.yaml` | GRD | security owner |
| `src/readiness/adapters/llm/`, `docs/security/LLM_PROVIDER_CHECKLIST.md` | LLM | security owner |
| `infra/`, `cloudbuild.yaml`, `Dockerfile`, `.github/workflows/` | INF | infra owner |
| `src/readiness/ingestion/`, `src/readiness/adapters/sources/` | ING | engine owner |
| `src/readiness/scoring/`, `config/scoring/`, `config/profiles/` | SCR | product owner (scoring is the product) |
| `src/readiness/recommend/`, `config/recommendations/` | REC | product owner |
| `src/readiness/api/`, `src/readiness/cli.py` | API | engine owner |
| `src/readiness/agents/` | AGT | engine owner |
| `src/readiness/pipeline.py`, `models.py`, `config.py`, `adapters/registry.py` | FND | engine owner |
| `docs/product/`, `docs/planning/`, `docs/decisions/` | DOC | product owner |
| `docs/security/`, `SECURITY.md` | GRD | security owner |
| `docs/architecture/MIGRATION_PLAYBOOK.md`, `docs/architecture/PROVIDER_PORTABILITY.md` | MIG | infra owner |
| `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/collaboration/` | DOC | any maintainer |

Roles today may all be the same person. The table still matters: it says which hat to wear when reviewing.
