# Copperfield Marine Insurance - Application Portfolio (SYNTHETIC)

| Application | Business criticality | Application owner | Dependencies | Database |
|---|---|---|---|---|
| Claims | tier 1 | claims IT | Policy Admin, Document store | SQL Server 2019, database size 1.5 TB |
| Policy Admin | mission critical | underwriting IT | Rating engine | Oracle 19c, 900 GB |
| Document store | tier 2 | workplace IT | File shares (SMB, 30 TB, 4k IOPS) | none |
| Intranet | tier 3 | workplace IT | none | MySQL 8 |

- Containerisation: the rating engine already runs in Docker with a CI/CD pipeline; a Kubernetes pilot is planned.
- Data classification: policyholder personal data is confidential; data residency must stay in-country (regulator rule).
- Backup policy: nightly, retention period 90 days, snapshot weekly; archive of closed claims for 10 years.
