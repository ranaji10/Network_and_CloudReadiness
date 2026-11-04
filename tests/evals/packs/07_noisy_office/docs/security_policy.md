# Blue Teacup Catering - Information Security Policy (SYNTHETIC)

- Identity provider: Google Workspace with SSO; MFA enforced for all users via passkey.
- Firewall: a FortiGate at the office edge with default deny inbound rules; rule review twice a year.
- Remote access through WireGuard VPN with MFA.
- Logging: central syslog server with 6 months log retention; EDR on laptops.
- Patching cadence: monthly; vulnerability scan quarterly with Nessus.
- Backups: nightly backup to offsite cloud storage, restore test yearly, RPO 24h.
- Encryption: TLS 1.2 minimum; disk encryption on all laptops.
- Incident response plan reviewed annually with a tabletop exercise.
