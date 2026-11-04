# Nimbus Orchard Holdings - Data and Storage Overview (SYNTHETIC)

## Databases and storage
| Engine | Database version | Database size | Use |
|---|---|---|---|
| PostgreSQL | 15 | 800 GB | portal |
| MySQL | 8.0 | 120 GB | ERP integration |
| SQL Server | 2019 | 2 TB | finance |
- File shares: 40 TB on NFS and SMB from the NAS; the SAN delivers 20k IOPS for the databases.
- Object storage for archives; backup policy: daily snapshot, retention period 35 days, yearly archive for 7 years.

## Analytical platform
- BigQuery data warehouse loaded by Airflow pipelines and dbt; a governed data lake sits beside it.
- Data catalog in Dataplex with a data owner and data steward per domain, metadata and data classification tags.
- Data quality checks with Great Expectations and column-level lineage; every feed has a data contract.
- Unstructured content: documents are indexed with embeddings in pgvector for semantic search and RAG use cases,
  plus Vertex AI Search as the enterprise knowledge base.
