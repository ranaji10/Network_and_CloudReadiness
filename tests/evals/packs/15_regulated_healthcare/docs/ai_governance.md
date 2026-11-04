# Meadowlark Health Partners - AI Governance Framework (SYNTHETIC)

- Responsible AI policy and acceptable use of AI approved by the ethics board; AI governance committee meets quarterly.
- AI risk assessment aligned to NIST AI RMF and ISO 42001; DPIA mandatory for any model touching PHI.
- Human-in-the-loop approval gate for every clinical suggestion; four-eyes review before a recommendation reaches a clinician.
- Model inventory with model card, model owner and an AI register of all pilots.
- Vendor terms: zero data retention and no training on patient data are contractual requirements (DPA).
- No managed AI platform has been selected yet; no vector search; integration APIs exist for the EHR (REST, FHIR, OpenAPI)
  behind an API gateway with OAuth2 and rate limit policies.
- Audit trail for every automated action in the SIEM; evaluation protocol (golden set, red team) defined but not yet run.
