# Kestrel Stack Inc - Network Notes (SYNTHETIC)

- The VPC is a flat network: one subnet per region, no segmentation between dev, staging and prod.
- Developers reach nodes directly; SSH open to the internet on the dev node pool is a known issue.
- There is no firewall policy beyond the defaults and no WAF in front of the public API.
- MFA is not enforced for the shared ops account used by the on-call engineer; it is a shared admin account.
- No SIEM; logs stay in Cloud Logging for 30 days. No intrusion detection.
- TLS 1.2 everywhere; encryption at rest is the provider default.
