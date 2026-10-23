# Acme Widgets – Information Security Policy (SYNTHETIC)

- All staff use Okta SSO; MFA is enforced for all users and admins use hardware keys (FIDO2).
- Least privilege and role-based access (RBAC); quarterly access review by system owners.
- Logs ship to a central Splunk SIEM with 12 months log retention.
- Vulnerability scans run weekly with Nessus; critical patches within 14 days (patching cadence documented).
- Encryption at rest (AES-256) for all databases and encryption in transit TLS 1.2 minimum.
- Incident response plan exists; a tabletop exercise is held annually.
- Backups nightly to offsite storage with immutable object lock; RPO 24h, RTO 8h; restore test twice a year.
- Service accounts use the HashiCorp Vault secret manager with key rotation every 90 days.
