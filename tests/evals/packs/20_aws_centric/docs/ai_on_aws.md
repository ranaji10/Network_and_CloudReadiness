# Juniper Owl Fintech - AI on AWS (SYNTHETIC)

- Model access through Bedrock and SageMaker; a model registry and MLOps pipelines; agent framework with function calling
  and MCP tool servers; workflows orchestrated with Step Functions.
- Core systems expose REST APIs (OpenAPI) through the API gateway with OAuth2, rate limit, quota and API logging.
- Vector search on OpenSearch with embeddings for RAG over the knowledge base.
- Governance: responsible AI policy, AI risk assessment with DPIA, human-in-the-loop approval gate for payment actions,
  model inventory with model card and model owner, vendor assessment with zero data retention terms.
- Agent security: IAM role per agent with least privilege and short-lived credentials; Secrets Manager; prompt injection
  guardrails with content filter and DLP; OpenTelemetry tracing and an audit trail in CloudTrail; evaluation with a golden set
  and red team exercises before release.
- Network and access for staff: MFA enforced for all users (FIDO2 for admins), least privilege, quarterly access review,
  zero trust access for remote staff; micro-segmentation in EKS; incident response plan with a tabletop exercise yearly;
  vulnerability scan weekly and a 14 day patching cadence; penetration test annually; intrusion detection with GuardDuty and EDR.
