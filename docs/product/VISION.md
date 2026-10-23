# Vision

## The problem

Most small and mid-sized businesses already hold the evidence of how secure and cloud-ready they
are: network diagrams, policies, audit reports, inventories, contracts, memos. That evidence sits in
folders nobody reads end to end. A consultant spends days reading it before they can say anything
useful, and the output is a slide deck that cannot be re-run when the documents change.

## What this tool does

It reads a business's existing documents (a local folder, a cloud bucket or a Google Drive folder),
scores them against configurable control frameworks, and produces a report with:

- a **posture score** per area (network security, cloud readiness, agentic-AI readiness),
- an **evidence coverage** figure that says how much of the picture the documents actually cover,
- a prioritised list of **actions**, each with GCP, AWS, open-source and process options,
- a list of **discovery questions** (CSA CAIQ wording) for the gaps where nothing was found.

The same engine runs from a command line, an HTTP API and a chat agent, so the report is the same
whichever surface a user picks.

## Who it is for

| User | What they get |
|---|---|
| Consultancies and managed service providers | A repeatable first-day assessment they can run per client, with the client's data never leaving the agreed boundary |
| Internal IT and security teams | A self-service readiness check before a cloud or AI programme, re-runnable every quarter |
| Cloud and AI vendors or partners | A neutral scoring frame that shows where their products fit, without the tool being a sales deck |

## Principles

1. **Provider neutral.** Every cloud or model dependency sits behind a port. Switching account, region,
   cloud or model is an environment change, not a code change. Recommendations always list more than
   one provider.
2. **Evidence first; coverage separate from posture.** A missing document is "no evidence", never
   "control absent". The report shows both numbers so nobody mistakes a thin document set for a weak
   organisation.
3. **Confidential by default.** The tool runs fully offline unless egress is explicitly enabled.
   Secrets are always masked, identifiers are pseudonymised before any model call, logs hold hashes
   and counts rather than content, and client data never enters version control.
4. **Configuration over code.** Pillars, checks, weights, signals, control mappings and product
   options are YAML. A domain expert can tune the scoring without touching Python.
5. **Multi-agent friendly.** Small modules with clear ownership, one tracker file per epic, date-based
   decision records, and a CI gate that any contributor (human or agent) can run locally. Several
   people and several agents work on it in parallel without stepping on each other.

## Non-goals

- Not a vulnerability scanner or a live configuration auditor. It reads documents, not systems.
- Not a replacement for a formal audit. Scores are planning inputs, not certifications.
- Not a single-cloud migration accelerator. The GCP migration profile exists, but so do the others.
- Not a generic document search tool. Everything it extracts is in service of a score and a plan.

## How we will know it works

- An analyst can run an assessment on a client folder in under ten minutes and hand over the report.
- Re-running on an updated folder shows the score move for the right reasons.
- No client identifier or secret has ever appeared in a log, a commit or a model prompt.
- A second contributor (or agent) can pick up a tracker story cold and ship it in one PR.
