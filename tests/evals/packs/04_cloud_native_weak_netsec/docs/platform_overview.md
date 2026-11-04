# Kestrel Stack Inc - Platform Overview (SYNTHETIC)

## Runtime
- All services run as containers on GKE (Kubernetes) with Helm; batch jobs on Cloud Run with autoscaling.
- Terraform (infrastructure as code) in a GitHub Actions CI/CD pipeline; Prometheus and Grafana observability;
  a runbook per service and an SRE rotation.
- Utilization is tracked in a monthly capacity report (CPU usage, peak load) used for right-sizing.

## Cloud foundations
- Landing zone from the security foundations blueprint with organization policy guardrails and CIS Benchmark scans.
- Identity federation through Cloud Identity with directory sync from Google Workspace; workload identity for pods.
- Cloud KMS with CMEK on every bucket and database; Security Command Center (CSPM) plus Cloud Audit Log and
  Cloud Logging for monitoring.
- Cloud DNS for all zones; certificates automated with Let's Encrypt (ACME).
- Hybrid connectivity: Cloud VPN site-to-site to the office, 500 Mbps bandwidth, latency 12 ms.

## Data
- PostgreSQL 15 (database version pinned, database size 300 GB) and object storage for assets (12 TB).
- Data classification: public / internal / confidential; personal data (PII) stays in the EU region (data residency).
- Backup policy: automated snapshot every 6 hours, retention period 30 days.
- BigQuery data warehouse fed by an ETL data pipeline; data catalog in Dataplex with data owner per dataset.

## Cost
- FinOps owner, labels enforced by a tagging policy, budget alert per project, cost allocation by cost center.
- Current cost baseline tracked monthly (monthly cost dashboard, opex only).
- Licence list with renewal date for every subscription; training plan with cloud certification goals.
- Compliance: SOC 2 Type I in progress; GDPR applies.
