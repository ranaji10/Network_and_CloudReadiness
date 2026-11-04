# Verdigris Clinic Network - Security Standard (SYNTHETIC)

- Firewall at every clinic (small FortiGate units) managed centrally; rule review not scheduled.
- Identity: Google Workspace SSO; MFA enforced for all staff.
- Access: least privilege for clinical systems; access review happens when staff leave.
- Logging: Windows event logs collected on a central syslog box; no SIEM, log retention 90 days.
- Patching cadence: monthly through the RMM tool.
- Encryption: TLS 1.2 on the patient portal; laptops have disk encryption.
- Backups: nightly backup to a cloud bucket; RPO 24h; no restore test documented.
