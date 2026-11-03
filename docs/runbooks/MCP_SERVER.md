# Runbook: the MCP server (Claude Code, Claude Desktop and other MCP clients)

`readiness mcp` runs a [Model Context Protocol](https://modelcontextprotocol.io) server on stdio so an
analyst can run assessments from a chat client without the HTTP API. It is a thin wrapper over the same
pipeline as the CLI and the ADK agent (AGT-04, `docs/decisions/ADR-20261023-adk-wrapper-kept-thin.md`):
same scores, same redaction, same egress policy.

## Install

```bash
uv sync --extra mcp            # from a checkout
pip install "readiness[mcp] @ git+https://github.com/<owner>/<repo>@<tag>"   # as a package
```

Without the extra, `readiness mcp` exits 1 with `install it with: uv sync --extra mcp`.

## Register in Claude Code

```bash
claude mcp add readiness -e READINESS_WORKSPACE_DIR=$PWD/workspace -- uv run readiness mcp
```

Run it from the repository root (so `uv run` finds the project) or replace `uv run readiness` with the
absolute path of the installed `readiness` script. Claude Desktop and other clients take the same command
in their MCP configuration (`command: uv`, `args: ["run", "readiness", "mcp"]`, plus `env`).

Then, in Claude Code: "assess ./data/<folder> with the security_only profile" calls
`run_readiness_assessment`; the model reads the summary and can open `report.md` under `report_dir`.

## Tools

| Tool | Arguments | Returns |
|---|---|---|
| `run_readiness_assessment` | `source_uri` (folder, `gs://`, `s3://`, `gdrive://`), `profile` (default `default`) | compact summary: `run_id`, `report_dir`, `overall_score`, `evidence_coverage`, per-domain scores and grades, up to 10 `top_actions`, up to 15 `discovery` questions, `warnings` |
| `list_profiles` | none | profile ids, names, domain weights, target providers |
| `list_checks` | `domain` (optional) | check id, title, points, pillar, CCM ids, discovery question |

Responses are summaries, never the full report: the client reads `report.md` / `report.json` from
`report_dir` when it needs the detail. Document content is redacted before scoring and never returned.

## Environment variables that matter

| Variable | Why |
|---|---|
| `READINESS_WORKSPACE_DIR` | where `report.md`, `report.json` and `audit.jsonl` are written (`<dir>/<tenant>/<run id>/`). Unset, the tool writes under the system temp directory. |
| `READINESS_LLM_PROVIDER` | stays `mock` (the default). Switching to a real model also needs `READINESS_ALLOW_LLM_EGRESS=true` and is an operator decision, see `docs/security/GUARDRAILS.md`. |
| `READINESS_REDACTION_MODE`, `READINESS_TENANT_ID`, `READINESS_CONFIG_DIR` | as for the CLI; a `.env` in the working directory is read too. |

Cloud sources (`gs://`, `s3://`, `gdrive://`) need the matching extra (`--extra gcp` / `--extra aws`) and
credentials in the server's environment, exactly as for `readiness assess`.

## Security notes

- The transport is stdio: the server is a child process of the client and listens on no port.
- The server has no authentication of its own; it runs with the permissions of the user who started it.
  Do not expose it over a network transport without the API's bearer-token layer in front.
- Logs go to stderr (stdout is the protocol channel) and carry metadata only, never document content.
