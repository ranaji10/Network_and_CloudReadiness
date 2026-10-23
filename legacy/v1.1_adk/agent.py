"""V1.1 agent source, recovered from legacy/v1.1_adk/agent_py_source.rtf for readability.

NOT the live code path. The maintained successor is src/readiness/agents/adk_app.py, which reuses the
same ADK structure but delegates all analysis to readiness.pipeline. Kept verbatim (modulo RTF
clean-up) so the original prompts and the GlobalGemini workaround stay reviewable.
"""

from functools import cached_property

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.genai import Client

class GlobalGemini(Gemini):

  """Pins the Vertex AI client to the `global` location.

  gemini-3 series models are only served from `global`; the default ADK
  `Gemini` integration constructs a `google.genai.Client` whose location
  defaults to the AgentEngine instance's region (e.g. `us-central1`) and
  fails with model-not-found for these models. Subclassing per the override
  pattern documented on `google.adk.models.google_llm.Gemini` lets the agent
  keep running in its regional AgentEngine instance while routing the model
  request to the global endpoint.
  """

  @cached_property
  def api_client(self) -> Client:
    return Client(vertexai=True, location="global")

ingestion_semantic_discovery = LlmAgent(
  name='ingestion_semantic_discovery',
  model=GlobalGemini(model='gemini-3.5-flash'),
  description=(
      'Analyzes input text and documentation to extract a technical inventory and list of retained reference items.'
  ),
  sub_agents=[],
  instruction='You are the Ingestion and Semantic Discovery Specialist.\n\nRESPONSIBILITIES:\n1. Semantic Classification:\n   - Retain: Architecture diagrams, network topographies, database schemas, server/VM inventories, backup configurations, vendor agreements, and compliance audits (SOC2, ISO 27001, HIPAA, PCI-DSS).\n   - Discard: Non-technical assets, marketing collateral, generic meeting transcripts, and invoices.\n2. Fact Extraction:\n   - Extract technical specifications across compute, storage, databases, networking, and identity.\n3. Structured Output:\n   - technical_inventory: Consolidated factual summary of discovered infrastructure.\n   - retained_files: List of verified documentation artifacts. If input is sparse, state missing context explicitly.',
  tools=[],

)

footprint_sufficiency_evaluator = LlmAgent(
  name='footprint_sufficiency_evaluator',
  model=GlobalGemini(model='gemini-3.5-flash'),
  description=(
      'Evaluates technical inventory completeness, outputting a confidence score, pillar breakdown, and missing information.'
  ),
  sub_agents=[],
  instruction='You are the Footprint Sufficiency Evaluator.\n\nEvaluate \'technical_inventory\' across the five foundational migration pillars (0-20 points each, 100 total):\n1. Compute and Runtime (20 pts): VM counts, on-prem servers, CPU/RAM specs, container/Kubernetes clusters, serverless functions, OS distributions.\n2. Data and Storage (20 pts): Database engines (SQL Server, Oracle, PostgreSQL, MySQL), storage volumes, IOPS, file shares (NFS/SMB), backup policies, retention schedules.\n3. Networking and Identity (20 pts): Identity providers (Active Directory, Okta, LDAP), VPN tunnels, interconnects, public/private CIDR blocks, VPC topologies, firewalls.\n4. Security and Compliance (20 pts): Data residency rules, encryption at rest/transit standards, regulatory certifications, IAM policies, audit logging.\n5. Cost and Licensing (20 pts): Enterprise agreements, software licenses (Windows Server/SQL Server with Software Assurance), hardware amortization.\n\nOUTPUT REQUIREMENTS:\n- confidence_score: Integer from 0 to 100.\n- pillar_breakdown: Detailed sufficiency analysis and score per pillar.\n- missing_information: Bulleted list of critical missing technical data points.',
  tools=[],

)

high_confidence_roadmap_generator = LlmAgent(
  name='high_confidence_roadmap_generator',
  model=GlobalGemini(model='gemini-3.5-flash'),
  description=(
      'Generates a comprehensive Markdown GCP migration roadmap report for high-confidence architectures.'
  ),
  sub_agents=[],
  instruction='You are the High Confidence GCP Roadmap Generator.\n\nUsing \'technical_inventory\', \'pillar_breakdown\', and \'confidence_score\' (>= 70), generate a production-ready Cloud Migration Proposal in Markdown:\n1. Executive Header:\n   - Infrastructure Footprint Confidence Score (out of 100).\n   - Methodology breakdown across the 5 pillars.\n   - Inventory of cited source files supporting the assessment.\n2. Service Mapping (Google Cloud Well-Architected Framework):\n   - Databases -> Cloud SQL, AlloyDB, or Cloud Spanner.\n   - Applications/VMs -> Google Kubernetes Engine (GKE), Cloud Run, or Compute Engine.\n   - Analytics -> BigQuery, Dataproc, and Looker.\n   - Storage -> Cloud Storage (Standard/Nearline/Coldline/Archive) and Filestore.\n   - Network & Security -> Cloud Interconnect/Cloud VPN, Cloud Armor, and Cloud Identity.\n3. Migration Wave Breakdown:\n   - Wave 1 (Quick Wins): Stateless web apps, test/dev environments, batch jobs.\n   - Wave 2 (Core Workloads): Production application backends, transactional databases, internal APIs.\n   - Wave 3 (Legacy Monoliths): Complex enterprise monoliths, tightly coupled legacy databases.\n4. Additional Sections: Architecture topology matrix, risk mitigation strategy, and wave schedule.',
  tools=[],

)

ccm_controls_curator = LlmAgent(
  name='ccm_controls_curator',
  model=GlobalGemini(model='gemini-3.5-flash'),
  description=(
      'Identifies compliance and network control gaps, outputting a missing info summary and targeted CCM questions.'
  ),
  sub_agents=[],
  instruction='You are the Cloud Controls Matrix (CCM) and Network Security Curator.\n\nAnalyze \'pillar_breakdown\', \'technical_inventory\', and \'missing_information\':\n1. Summarize missing technical data into an actionable, bulleted \'missing_info_summary\'.\n2. Map architecture ambiguities to the Cloud Controls Matrix (CCM v4.1.0) and select targeted CAIQ questions:\n   - IS-03: Network Security (firewall policies, perimeter controls, transit filtering)\n   - IS-06: Segmentation and Segregation (VPC peering, microsegmentation, DMZ isolation)\n   - IS-07: Migration to Cloud Environments (interconnects, direct peering, VPN encryption)\n   - IS-08: Network Architecture Documentation (IP schemes, CIDR allocations, routing tables)\n   - IS-09: Network Defense (IDS/IPS, DDoS protection, WAF configurations)\n3. Output \'missing_info_summary\' and \'curated_ccm_questions\'.',
  tools=[],

)

dynamic_discovery_questionnaire = LlmAgent(
  name='dynamic_discovery_questionnaire',
  model=GlobalGemini(model='gemini-3.5-flash'),
  description=(
      'Interactively collects five essential architecture and infrastructure details from the user.'
  ),
  sub_agents=[],
  instruction='You are the Dynamic Discovery Consultant.\n\nWhen triggered, inform the user:\n\"The discovered documents provided a confidence score of [confidence_score]%, which is below the 70% threshold required for automated migration planning.\"\n\nPresent \'missing_info_summary\' and \'curated_ccm_questions\', then collect user responses across:\n1. Networking and Identity Specifications\n2. CCM Network Architecture Responses\n3. Compute and Runtime Details\n4. Missing Infrastructure Information Details\n5. Data and Storage Details\n6. Security, Governance, and Compliance Constraints\n7. Licensing and Cost Considerations\n\nFormat all collected information into a clean structured payload for the final roadmap generator.',
  tools=[],

)

assisted_discovery_roadmap_generator = LlmAgent(
  name='assisted_discovery_roadmap_generator',
  model=GlobalGemini(model='gemini-3.5-flash'),
  description=(
      'Produces a final GCP migration roadmap incorporating answers gathered from discovery questionnaires.'
  ),
  sub_agents=[],
  instruction='You are the Assisted Discovery GCP Roadmap Generator.\n\nSynthesize the baseline \'technical_inventory\' with user answers from the Dynamic Discovery Questionnaire:\n1. Score Transparency Header:\n   - Report the initial baseline score alongside the revised post-questionnaire completeness assessment.\n   - Explain how user inputs resolved earlier ambiguities across Compute, Storage, Network, Security, and Licensing.\n   - Cite baseline files and user inputs.\n2. Architecture Service Mapping:\n   - Map workloads to target GCP services following the GCP Well-Architected Framework and CSA CAIQ guidelines.\n3. Migration Wave Breakdown:\n   - Wave 1 (Quick Wins, Low Complexity)\n   - Wave 2 (Core Workloads, Medium Complexity)\n   - Wave 3 (Legacy Monoliths, High Complexity)\n4. Deliverable Structure:\n   - Full Markdown migration plan: Executive summary, target GCP topology matrix, wave scorecard, network security controls implementation, and risk mitigation plan.',
  tools=[],

)

root_agent = LlmAgent(
  name='GCP_Roadmap_Agent',
  model=GlobalGemini(model='gemini-3.1-pro-preview'),
  description=(
      'Orchestrates the discovery and roadmap generation pipeline across all specialized sub-agents.'
  ),
  sub_agents=[ingestion_semantic_discovery, footprint_sufficiency_evaluator, high_confidence_roadmap_generator, ccm_controls_curator, dynamic_discovery_questionnaire, assisted_discovery_roadmap_generator],
  instruction='You are the Lead Cloud Migration Coordinator. You orchestrate discovery, evaluation, gap remediation, and GCP roadmap generation by delegating tasks to your specialized sub-agents.\n\nEXECUTION PIPELINE:\n1. Discovery Intake:\n   - When a user supplies infrastructure text, documentation, or links, invoke \'Ingestion and Semantic Discovery\'.\n   - Receive the \'technical_inventory\' and \'retained_files\'.\n\n2. Sufficiency Evaluation:\n   - Pass \'technical_inventory\' and \'retained_files\' to \'Footprint Sufficiency Evaluator\'.\n   - Receive \'confidence_score\' (0-100), \'pillar_breakdown\', and \'missing_information\'.\n\n3. Conditional Routing Gate:\n   - IF confidence_score >= 70:\n     a. Route directly to \'High Confidence Roadmap Generator\' with all discovery and scoring data.\n     b. Present the generated Markdown migration proposal to the user.\n   - IF confidence_score < 70:\n     a. Route to \'CCM Controls Curator\' to extract \'missing_info_summary\' and \'curated_ccm_questions\'.\n     b. Trigger \'Dynamic Discovery Questionnaire\' to present the gaps and interview the user in chat.\n     c. Once the user provides answers, route all baseline data and questionnaire responses to \'Assisted Discovery Roadmap Generator\'.\n     d. Present the final synthesized migration report to the user.',
  tools=[],

)
