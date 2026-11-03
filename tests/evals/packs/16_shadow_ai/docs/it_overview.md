# Quartz Badger Media - IT Overview (SYNTHETIC)

- Identity: Google Workspace SSO; MFA enforced for all users.
- Network: office firewall with default deny inbound; staff VLAN and guest wifi; VPN for remote work.
- Logging: Cloud Logging with 30 days retention; no SIEM; EDR on laptops; monthly patching cadence.
- Backups: managed database backup, retention 14 days; no restore test.
- Encryption: TLS 1.2 everywhere; encryption at rest by the provider.
- Containers on Cloud Run with a GitHub Actions CI/CD pipeline; Terraform for the project setup.
