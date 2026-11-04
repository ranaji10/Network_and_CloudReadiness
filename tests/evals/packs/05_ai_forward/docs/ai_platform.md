# Lumen Fox AI - Agent Platform Architecture (SYNTHETIC)

- Model access through Vertex AI (Gemini) and Bedrock for comparison; a model registry tracks every foundation model
  and fine-tune; MLOps pipelines retrain weekly.
- Agents are built with LangGraph and the ADK, speak MCP (model context protocol) to tools and use function calling;
  Agent Engine hosts them; workflows orchestrate long-running jobs.
- Core systems expose REST and GraphQL APIs with OpenAPI specs; events flow over Kafka and Pub/Sub.
- API gateway: Apigee with OAuth2, rate limit and quota policies and API logging.
- Inference is serverless on Cloud Run with autoscaling; GPU nodes on Kubernetes for batch embedding jobs.

## Data
- Data warehouse on BigQuery with dbt and Airflow; a lakehouse on Databricks for experiments.
- Data catalog with data owner and data classification for every table; lineage and data quality monitors.
- Vector search with pgvector and Vertex AI Search; embeddings refreshed nightly for RAG.
