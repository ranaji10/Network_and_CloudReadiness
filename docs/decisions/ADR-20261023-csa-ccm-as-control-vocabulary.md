# CSA Cloud Controls Matrix v4.1 is the control vocabulary

Status: accepted
Date: 2026-10-23

## Context
V1 already used CCM/CAIQ questions for discovery. Checks need a shared vocabulary that clients and
auditors recognise, and discovery questions need standard wording.

## Decision
Every check carries `ccm:` ids from CCM v4.1 (`I&S`, `IAM`, `LOG` and so on). The catalog is generated
from the CSA spreadsheets in `reference/` into `src/readiness/data/ccm_v4.1.json` and shipped with
the package. Discovery items quote CAIQ questions for the mapped controls.

## Consequences
- Reports map to a framework clients may already be assessed against.
- The CSA licence terms for redistribution must be confirmed before commercial release (PRD open
  question).
- Agentic-AI checks stretch the vocabulary; some map loosely and may later reference ISO 42001.
