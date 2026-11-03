# The assessor runs outside the client's network, with no client-side footprint

Status: accepted
Date: 2026-11-03

## Context
Prospective clients asked whether the tool has to be deployed inside their network. A tool that
must be installed on their hosts, joined to their network or given a VPN tunnel triggers a full
third-party security review and is often refused outright.

Nothing in the engine needs that access. The vision already states "it reads documents, not
systems" and the PRD lists live scanning as out of scope, but neither was recorded as a boundary
that future work must respect, and nothing in CI stopped a well-meaning contributor from adding a
"quick host check" or an SSH-based inventory source.

## Decision
The assessor is an **outside-the-network** tool with **zero footprint** on client systems. Fully
functional, nothing is lost by this: every feature in the roadmap works on documents.

- **Where it runs**: on the operator's own infrastructure (laptop, container, Cloud Run, Agent
  Engine) or on a cloud account the client owns. Never on a client host, never joined to a client
  network, never through a VPN or a site-to-site tunnel into the client.
- **How client documents reach it** (the only two paths):
  1. **Push**: the client, or the analyst holding the pack, uploads files to the API/UI or places
     them on a folder the operator controls.
  2. **Pull, read-only, from a cloud document store the client shares**: a Google Drive folder
     (`drive.readonly` scope), a GCS prefix or an S3 prefix, using credentials the client grants
     to a single identity and can revoke at any time.
- **What it never does**: no port scans, no host or service discovery, no SSH/WinRM/SNMP/LDAP/SMB
  sessions, no agent or collector installed on the client side, no reading of live cloud account
  configuration, no inbound connection from the client network to the tool and no outbound
  connection from the tool into the client network.
- **Enforced in CI** by `scripts/check_no_system_access.py` (in `make check`, Cloud Build and
  GitHub Actions): no scanning, remote-access or protocol-client library in the dependencies or the
  lock file; no raw `socket`/`subprocess` use under `src/readiness`; source schemes limited to
  `file`, `gs`, `s3`, `gdrive`; no network tooling installed in the runtime image.
- **Documented for clients** in `docs/security/DEPLOYMENT_POSTURE.md`, written to be handed to a
  client security team as is.

## Consequences
- A client review becomes a data-sharing question (which documents, through which channel, with
  which retention), not an infrastructure question. The client keeps a single revocable grant.
- Anything that needs to *observe* the client's environment (live configuration audit, vulnerability
  scanning, agent-based inventory) is out of scope for this product. A future "live evidence"
  capability would need a superseding ADR, a new CI allow-list and a separate client consent flow.
- New document sources must be document stores reached with client-granted read-only credentials
  (SharePoint/OneDrive, Box, Confluence export, ...) and must be added to the allow-list in the CI
  check together with the registry.
- Discovery questions remain the way to fill gaps the documents do not cover; the questionnaire
  round trip (AGT-03) gains weight on the roadmap because it is the only "live" input we accept.
