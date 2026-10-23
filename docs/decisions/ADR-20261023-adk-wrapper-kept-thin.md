# The ADK agent is a thin wrapper over the pipeline

Status: accepted
Date: 2026-10-23

## Context
V1.1 put the whole workflow in ADK `LlmAgent` instructions, which tied the logic to Gemini and to
Agent Engine and made it impossible to test offline.

## Decision
`agents/adk_app.py` exposes one tool, `run_readiness_assessment`, that calls `pipeline.run_assessment`.
Prompts live in `agents/prompts.py`. The module imports ADK lazily and stays importable without it.
Any other agent framework (MCP server, Anthropic tool use) wraps the same function.

## Consequences
- Chat, CLI and API give identical scores.
- Agent Engine hosting continues the V1.1 path without owning the logic.
- Conversational flows such as the questionnaire round trip (AGT-03) are built on tool calls, not
  on prompt-embedded logic.
