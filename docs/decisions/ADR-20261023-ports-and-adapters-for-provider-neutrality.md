# Ports and adapters for provider neutrality

Status: accepted
Date: 2026-10-23

## Context
V1 was a Google Agent Platform workflow and V1.1 was ADK code; both were tied to Google Drive, Vertex
AI and one personal GCP account. The product must run on GCP today, possibly AWS or on-premises
later, and move between Google accounts without a rewrite.

## Decision
The core (`src/readiness`) depends only on four protocols in `readiness/ports`: `DocumentSource`,
`LLMProvider`, `BlobStore`, `SecretStore`. Concrete implementations live in `readiness/adapters`
and import cloud SDKs lazily. `adapters/registry.py` is the only module that maps a provider name
to an adapter, driven entirely by `Settings` (environment variables).

## Consequences
- Switching account, region or cloud is an environment and Terraform change, never a code change.
- A new provider is one adapter per port plus a registry entry; nothing else moves.
- Cloud SDKs are optional extras, so the core installs and tests offline.
- The ADK agent is one more adapter on top of the pipeline, not the pipeline itself.
