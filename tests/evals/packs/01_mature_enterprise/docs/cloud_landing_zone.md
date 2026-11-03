# Nimbus Orchard Holdings - Cloud Landing Zone Standard (SYNTHETIC)

## Foundations
- Landing zone built from the Security Foundations blueprint; organization policy constraints and CIS Benchmark
  controls form the security baseline.
- Identity federation: Cloud Identity synchronised from Okta (directory sync, SAML); workloads use workload identity.
- VPC design uses the reserved 10.100.0.0/14 address space from the IP plan, so ranges are non-overlapping with
  on-premises RFC 1918 subnets.
- Key management: Cloud KMS with customer-managed keys (CMEK) for every data service; HSM-backed keys for the ledger.
- Security monitoring: Security Command Center (CSPM) findings and Cloud Audit Log entries stream into Cloud Logging
  and onward to the SIEM.

## Operations
- Everything is Terraform (infrastructure as code) delivered through a CI/CD pipeline on GitHub Actions and Cloud Build.
- Workloads run as containers on GKE (Kubernetes) with Helm charts; some services use Cloud Run with autoscaling.
- Observability with Prometheus and Grafana; every service has a runbook and an SRE on-call rota.
- Utilization data: a monthly capacity report with CPU usage and peak load feeds the right-sizing review.

## Cost and licensing
- FinOps owner in the platform team; a tagging policy with mandatory labels, budget alert thresholds per
  cost center and monthly showback.
- Cost baseline: the current TCO model records capex (hardware amortization) and opex (annual cost of licences).
- Licence inventory lists every enterprise agreement with renewal date and BYOL eligibility.
- Skills: a cloud center of excellence (CCoE) runs a training plan; 30 engineers hold a cloud certification.
