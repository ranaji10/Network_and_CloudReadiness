"""Network security, cloud readiness and agentic-AI readiness assessor.

Architecture in one paragraph: documents come in through a *DocumentSource* port (local folder, GCS,
S3, Google Drive), are extracted to text, classified, passed through *guardrails* (redaction, egress
policy, audit), scored by a deterministic rule engine driven by YAML *scoring profiles* (optionally
refined by an *LLMProvider* port), mapped to *recommendations* from a provider-neutral catalog, and
rendered as a report. Nothing in the core imports a cloud SDK; adapters do, lazily.
"""

__version__ = "0.2.0"
