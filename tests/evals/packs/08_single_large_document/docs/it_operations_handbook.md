# Granite Heron Utilities - IT Operations Handbook (SYNTHETIC)

This handbook is the single reference for the IT estate of Granite Heron Utilities, a regional water utility.
It is reviewed every year by the head of IT and the information security officer (secops@example.org).

## 1. Network architecture
The network diagram and topology are maintained in the drawing tool and exported here. The estate spans two
data centres, twelve depots and the control centre. Security zones: a DMZ for public services, an application
zone, a database zone, an OT zone for SCADA and a management network. Each zone is a VLAN with its own subnet;
the IP plan reserves 10.0.0.0/12 for sites and 10.64.0.0/12 for the cloud VPC design so the ranges are
non-overlapping. CIDR allocations per site are listed in the address plan appendix. Routing between zones
passes a stateful firewall; the OT zone is additionally protected by a data diode. Micro-segmentation is a
roadmap item, not in place today.

Perimeter: a Check Point next-generation firewall cluster protects every internet ingress with default deny
rules and a documented allow list. Firewall rule review is performed every six months. The customer portal is
behind Cloudflare WAF with DDoS protection. Remote access uses the Cisco IPsec VPN with MFA; a zero trust
pilot is planned for next year. Administrative access goes through a bastion host on the management VLAN and
engineers use privileged access workstations. Wireless: corporate wifi uses WPA2-Enterprise with 802.1X and a
guest network is isolated on its own VLAN. Connectivity: dual ISP uplinks with BGP failover; the data centres
are linked by redundant dark fibre; a Partner Interconnect of 1 Gbps to the cloud region is in procurement
with a latency target of 10 ms. DNS is split-horizon; certificates come from an internal PKI (certificate
authority) with manual renewals.

## 2. Identity and access
Active Directory is the identity provider with single sign-on (SSO) through SAML for SaaS applications and
Entra for Microsoft 365. MFA is enforced for all users; administrators use hardware key authenticators.
Least privilege is applied through RBAC profiles; an access review runs every quarter and a privileged access
management tool brokers admin sessions with just-in-time elevation. Service accounts are documented in the
CMDB and stored in a secrets manager; credential rotation is yearly, with a project to move to 90 days.
Identity federation to the cloud is planned through directory sync with Entra.

## 3. Detection and response
Logs are centralised in the Microsoft Sentinel SIEM with syslog and agent collectors; log retention is 12
months hot and 7 years cold. Intrusion detection: Suricata sensors on the DMZ and OT boundaries and EDR on
every endpoint; traffic inspection on the OT zone is passive. Vulnerability management: Qualys vulnerability
scan monthly; patch management cycle 30 days, 7 days for critical CVE findings; an annual penetration test.
The incident response plan is exercised through a tabletop exercise every year and each security incident has a
post-incident report. Security monitoring in the cloud will use Security Command Center and Cloud Audit Log
exports into the SIEM.

## 4. Data protection and resilience
Encryption in transit is TLS 1.2 minimum; encryption at rest uses AES-256 disk encryption for databases and
file servers; the cloud design mandates Cloud KMS with customer-managed keys (CMEK). Backups run nightly with
weekly offsite copies on immutable storage (object lock); RPO is 24 hours and RTO 12 hours for business
systems; a restore test happens every quarter and the disaster recovery plan is tested annually. Backup policy
and retention period (35 days daily, 12 months monthly, archive 7 years) are documented in the data
retention schedule.

## 5. Compute inventory and applications
The server inventory in the CMDB lists 140 virtual machines on VMware with vCPU, RAM and OS version for each:
Windows Server 2019 and 2022, RHEL 8, Ubuntu 22.04. The application portfolio records dependencies and
business criticality (tier 1 for billing and SCADA, tier 2 for the rest) with an application owner for every
application. Containers: the customer portal runs on Docker with a CI/CD pipeline; Kubernetes experience is
limited to a pilot. Utilization data comes from the monitoring data in vRealize, used as a performance baseline
for right-sizing.

## 6. Data and storage
Databases: SQL Server 2019 (database size 3 TB, billing), PostgreSQL 14 (GIS, 600 GB), Oracle 19c (asset
management, 1.2 TB). File shares: 60 TB on SMB and NFS from a NAS; the SAN provides 15k IOPS for the billing
database. Data classification has four levels (public, internal, confidential, restricted) and data residency is
in-country by regulation; personal data (PII) of customers falls under the privacy act.

## 7. Compliance and cloud security baseline
Compliance obligations: ISO 27001 certification, the national critical infrastructure regulation and NIST CSF
alignment; a SOC 2 report is requested from major vendors. The cloud security baseline follows the CIS
Benchmark and the provider's landing zone guidance with organization policy constraints; a well-architected
review is part of every project gate.

## 8. Cost, licensing and operations
Licence inventory: every enterprise agreement and support contract with renewal date is tracked; Windows and
SQL Server licences are eligible for BYOL. The cost baseline (TCO) records capex depreciation and annual opex per
system. Cloud cost governance: a FinOps owner is nominated, a tagging policy with labels per cost center and
budget alert thresholds are defined. Operations maturity: Terraform (infrastructure as code) for the cloud
foundation, Ansible for configuration, a CI/CD pipeline on GitLab, monitoring with Zabbix and Grafana and a
runbook per service. Skills: a training plan with cloud certification targets and a cloud centre of
excellence (CCoE) of six engineers.

## 9. AI and automation
A data catalogue exists in the GIS team only (data owner per layer, metadata). Analytical data lives in a SQL
Server data warehouse loaded by SSIS ETL jobs. Unstructured content sits in the document management system
with full-text search; no vector search. Data quality checks are manual. Core systems expose REST APIs with
Swagger documentation and an API gateway (Kong) with API key management and rate limit policies. There is no
managed AI platform yet; an AI policy (acceptable use of AI) was approved last year and an AI risk assessment
template exists. Any automation that changes SCADA set points requires dual control and human approval. The
service accounts used by automation have least privilege scopes and an audit trail in the SIEM. No agent
evaluation practice exists today.
