# Nimbus Orchard Holdings - AI Governance and Agent Platform (SYNTHETIC)

## Policy and risk
- Responsible AI policy and generative AI policy approved by the board; AI governance board meets monthly.
- Every AI use case passes an AI risk assessment (NIST AI RMF based) and a DPIA when personal data is involved.
- Consequential agent actions require a human-in-the-loop approval gate; every agent has a kill switch.
- Model inventory with a model card and a model owner for each model and agent (AI register).
- Vendor due diligence: data processing agreement (DPA) with zero data retention and no training on our data.

## Platform and integration
- Managed platform: Vertex AI with Gemini through Model Garden; agents are built with the ADK and hosted on Agent Engine.
- Tool protocols: MCP (model context protocol) servers and function calling; workflows orchestrate multi-step jobs.
- Core systems expose REST APIs described with OpenAPI and emit events on Pub/Sub; Apigee is the API gateway with
  OAuth2, rate limit and quota policies and API logging.
- Inference runs on Cloud Run with autoscaling; batch jobs use GPU nodes on Kubernetes.

## Agent security and operations
- Agents run under dedicated service accounts with workload identity and least privilege; tokens are short-lived credentials.
- Secrets stay in Secret Manager; secret scanning blocks any commit with a key.
- Prompt injection defences: Model Armor content filter, Sensitive Data Protection (DLP) and output filtering guardrails.
- Observability: OpenTelemetry tracing, an audit log of every tool call and LLM observability dashboards with token usage.
- Evaluation: a golden set regression test and red team exercise gate every release (quality gate).
