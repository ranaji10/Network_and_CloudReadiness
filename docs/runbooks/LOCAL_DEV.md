# Runbook: local development

## Prerequisites

- Python 3.12 and `uv` (https://docs.astral.sh/uv/). Docker optional. Terraform only for infra work.

## Setup

```bash
git clone <repo-url> && cd Network_and_CloudReadiness
uv sync --group dev
cp .env.example .env            # optional; defaults are offline
make demo                       # prints a Markdown report for the synthetic sample
make check                      # what CI runs
```

## Daily loop

| Task | Command |
|---|---|
| Run tests | `make test` or `uv run pytest -q tests/test_scoring.py -k partial` |
| Lint and format | `make lint`, `make fmt` |
| Assess a folder | `uv run readiness assess ./data/<folder> --profile default --snippets` |
| Try a redaction rule | `uv run readiness redact some.txt --mode pseudonymize` |
| List checks / profiles / controls | `uv run readiness checks cloud_readiness`, `readiness profiles`, `readiness controls backup` |
| Run the API | `make serve` then `curl -s localhost:8080/healthz` |
| Run in Docker | `docker compose up --build` |
| Re-render the tracker | `make tracker` |

## Using a real model locally

Only with synthetic or approved data. In `.env`: `READINESS_LLM_PROVIDER=gemini` (or `anthropic`),
`READINESS_ALLOW_LLM_EGRESS=true`, the key in `GEMINI_API_KEY` / `ANTHROPIC_API_KEY`, then
`uv sync --extra gcp` (or `--extra anthropic`) and `readiness assess ... --llm-judge`.
Without `READINESS_ALLOW_LLM_EGRESS=true` the run fails with a `PermissionError` by design.

## Cloud sources locally

`uv sync --extra gcp`, `gcloud auth application-default login`, then `readiness assess gs://bucket/prefix`
or `readiness assess gdrive://<folder id or URL>` (Drive read-only scope).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `PermissionError: LLM egress is disabled` | intended; set the flag only after the provider checklist |
| `Unknown profile` | file name in `config/profiles/` must equal the id |
| Check always `NO EVIDENCE` | signals are matched as whole words, case-insensitive; test with `readiness redact` to see what the text looks like after redaction |
| `ModuleNotFoundError: google` | install the extra: `uv sync --extra gcp` |
