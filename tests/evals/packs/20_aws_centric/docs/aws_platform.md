# Juniper Owl Fintech - AWS Platform Standard (SYNTHETIC)

- Accounts follow the AWS landing zone pattern with SCP guardrails and CIS Benchmark checks; well-architected reviews
  per workload.
- Identity federation: Okta to IAM Identity Center with SAML; IAM roles for workloads; no long-lived keys.
- Network: VPC design with private subnets per tier; Network Firewall at every internet ingress with default deny;
  AWS Shield and a WAF in front of the public API; Direct Connect (10 Gbps, latency 4 ms) plus site-to-site VPN;
  address space 10.16.0.0/12 non-overlapping with the office CIDR; Route 53 for DNS with ACM certificates.
- Security monitoring: GuardDuty, Security Hub (CSPM) and CloudTrail into the SIEM (Splunk) with 12 months log retention.
- Encryption: KMS with customer-managed keys for every data store; TLS 1.2 minimum; encryption at rest everywhere.
- Secrets: Secrets Manager with key rotation every 30 days; service accounts replaced by IAM roles.
- Compute: EKS (Kubernetes) with Helm and Docker images built by a CI/CD pipeline (GitHub Actions); Terraform
  infrastructure as code; Datadog observability; runbook per service; autoscaling groups and spot capacity for batch.
- Data: PostgreSQL 15 on RDS (database size 2 TB), Redshift data warehouse, Glue Catalog with data owner tags and data
  classification; object storage with object lock for immutable backup; backup policy retention period 35 days; RPO 1h, RTO 2h,
  restore test quarterly, multi-AZ for every tier.
- Compliance: PCI DSS, SOC 2 Type II, GDPR; data residency per region.
- Cost: FinOps owner, tagging policy, budget alert per account, cost allocation tags; TCO model with monthly cost reports;
  licence inventory with renewal date; training plan with AWS certification targets.
