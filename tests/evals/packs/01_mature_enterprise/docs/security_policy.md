# Nimbus Orchard Holdings - Information Security Policy (SYNTHETIC)

Approved by the security steering group. Applies to all staff and contractors.

## Identity and access
- Central identity provider: Okta with SAML / OIDC single sign-on (SSO) for every business application.
- MFA is enforced for all users; administrators must use FIDO2 hardware keys.
- Least privilege by design, role-based access (RBAC); quarterly access review by system owners and
  privileged access management with just-in-time elevation.
- Service accounts and machine credentials live in Secret Manager with 90-day key rotation; workload identity
  replaces long-lived keys wherever possible.

## Detection and response
- All security logs ship to the Chronicle SIEM; log retention is 13 months and alerts are monitored 24x7.
- Intrusion detection with Suricata sensors on every zone boundary plus EDR on all endpoints; packet mirroring
  feeds the network sensors.
- Vulnerability scans run weekly with Qualys; the patching cadence is 14 days for critical CVE findings.
  An external penetration test is commissioned every year.
- The incident response plan is exercised through a tabletop exercise twice a year; every security incident
  gets a post-incident review.

## Data protection and resilience
- Encryption in transit requires TLS 1.2 or TLS 1.3; encryption at rest uses AES-256 with keys in Cloud KMS (CMEK).
- Backups run nightly to an offsite, immutable object lock bucket; RPO 4 hours, RTO 8 hours; a restore test is
  performed quarterly as part of the disaster recovery exercise.

## Compliance
- The organisation holds SOC 2 Type II and ISO 27001 certification; GDPR applies to EU customer personal data (PII).
- Data classification levels: public, internal, confidential, restricted; data residency for EU data is the EU region.
