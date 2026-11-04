# Halcyon Pebble Co-op - IT Summary (SYNTHETIC)

## Network and security
- A firewall protects the office; the online shop uses Cloudflare.
- Remote access via VPN. Office LAN is split into a staff VLAN and a guest wifi network.
- Identity: Microsoft Entra with SSO; MFA enforced for all users.
- Logs are collected in Elastic; vulnerability scan twice a year; incident response plan exists.
- Encryption at rest on the database server; backups nightly with offsite copy, RPO 24h.

## Cloud and data
- Server inventory kept as a VM list (vCPU, RAM, OS version) in a spreadsheet.
- Applications: shop, ERP and warehouse; a dependency map is being drawn.
- Databases: PostgreSQL 14 and MySQL 8; 6 TB of files on a NAS (SMB).
- Data classification policy approved; GDPR compliance programme in place.
- Some Docker use for the shop; CI/CD through GitHub Actions; no infrastructure as code.
- Licences tracked in a spreadsheet with renewal date; no TCO model; no FinOps owner.

## AI
- A data warehouse on BigQuery; a data catalog project has started with data owner assignments.
- An LLM pilot (Gemini) for product descriptions; an AI policy is in draft; human approval of every generated text.
- Core systems expose REST APIs; no API gateway.
- The pilot runs under a service account; secrets in Secret Manager; no evaluation set yet.
