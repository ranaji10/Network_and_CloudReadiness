# Copperfield Marine Insurance - Security Brief (SYNTHETIC)

- Perimeter: Check Point firewall pair; WAF (Imperva) for the customer portal; IPsec VPN with MFA.
- Identity: Active Directory, SSO through SAML, MFA for all users, quarterly access review, least privilege.
- Detection: Splunk SIEM with 12 months log retention; IDS sensors; monthly vulnerability scan; patching cadence 30 days.
- Resilience: backup nightly, offsite, restore test yearly; RPO 24h, RTO 24h.
- Encryption: TLS 1.2 minimum; encryption at rest on the SAN.
