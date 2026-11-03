# Ironvale Mutual Savings Bank - Security Operations Runbook (SYNTHETIC)

- Centralised logging into the Splunk SIEM with syslog collectors; log retention 24 months; 24x7 monitoring.
- Vulnerability scan weekly with Nessus; patch management cycle of 30 days, 7 days for critical CVE items;
  annual penetration test by an external firm.
- Incident response plan with incident playbook per scenario; tabletop exercise every six months;
  post-incident review for every security incident.
- Encryption: TLS 1.2 minimum in transit, AES-256 disk encryption at rest for all database servers.
