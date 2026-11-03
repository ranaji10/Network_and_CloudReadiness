# Meadowlark Health Partners - Security Controls Summary (SYNTHETIC)

- Perimeter: Palo Alto next-generation firewall pair, default deny, firewall rule review quarterly; Cloudflare WAF with DDoS protection.
- Remote access: zero trust access (ZTNA) with MFA; legacy VPN retired.
- Segmentation: DMZ, clinical VLAN, admin VLAN, medical device VLAN, management network with bastion hosts.
- Identity: Okta SSO (SAML); MFA for everyone with FIDO2 keys for admins; least privilege RBAC; quarterly access review;
  service accounts in a secrets manager with key rotation.
- Detection: Sentinel SIEM with 12 months log retention; IDS (Zeek) and EDR; weekly vulnerability scan (Qualys);
  patching cadence 14 days for critical CVE; annual penetration test.
- Incident response plan with a tabletop exercise twice a year.
- Encryption: TLS 1.2 minimum, AES-256 at rest, Cloud KMS CMEK for cloud workloads.
- Backups immutable and offsite; RPO 4h, RTO 8h; restore test quarterly; disaster recovery exercise annually.
