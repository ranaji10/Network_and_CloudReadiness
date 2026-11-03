# Tin Lantern Software - Security Policy (SYNTHETIC)

- Every internet ingress is behind a next-generation firewall with default deny and a quarterly firewall rule review.
- MFA is enforced for all users and administrators through Okta SSO (SAML); FIDO2 keys for admins.
- Encryption in transit TLS 1.2 or TLS 1.3 only; encryption at rest with AES-256; keys in Cloud KMS (CMEK).
- Remote access only via WireGuard VPN or the zero trust proxy, both with MFA.
- Centralised logging in Splunk SIEM with 12 months log retention; Suricata intrusion detection; EDR everywhere.
- Weekly vulnerability scan with Nessus; 14 day patching cadence; yearly penetration test.
- Incident response plan with a tabletop exercise every year.
- Backups immutable and offsite, restore test quarterly, RPO 1h, RTO 4h.
- Segmentation: DMZ, app, data and management VLAN with a bastion host; micro-segmentation in the cluster.
- Service accounts in Secret Manager with key rotation; least privilege RBAC and quarterly access review.
