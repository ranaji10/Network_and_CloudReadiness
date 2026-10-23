"""Domain models shared by every layer. Keep these provider-neutral and serialisable."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class DocClass(StrEnum):
    """Coarse document classes. Used for sufficiency (coverage) scoring and for skipping noise."""

    ARCHITECTURE = "architecture"
    NETWORK = "network"
    SECURITY_POLICY = "security_policy"
    COMPLIANCE_AUDIT = "compliance_audit"
    INVENTORY = "inventory"
    DATA_STORAGE = "data_storage"
    IDENTITY = "identity"
    BACKUP_DR = "backup_dr"
    CONTRACT_LICENSE = "contract_license"
    AI_ML = "ai_ml"
    OPERATIONS = "operations"
    IRRELEVANT = "irrelevant"


class DocumentRef(BaseModel):
    """Pointer to a source document. Never carries content; content stays in ExtractedDocument."""

    id: str
    name: str
    uri: str
    source: str  # local | gcs | s3 | gdrive
    mime: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None

    @staticmethod
    def make_id(uri: str) -> str:
        return hashlib.sha256(uri.encode()).hexdigest()[:16]


class ExtractedDocument(BaseModel):
    ref: DocumentRef
    text: str
    classification: DocClass = DocClass.IRRELEVANT
    classification_confidence: float = 0.0
    truncated: bool = False
    extraction_error: str | None = None

    @property
    def is_relevant(self) -> bool:
        return self.classification != DocClass.IRRELEVANT and bool(self.text.strip())


class CheckStatus(StrEnum):
    MET = "met"
    PARTIAL = "partial"
    NOT_MET = "not_met"
    UNKNOWN = "unknown"  # no evidence either way -> drives discovery questions, not blame


class Evidence(BaseModel):
    doc_id: str
    doc_name: str
    snippet: str = ""  # empty unless settings.include_evidence_snippets
    signal: str


class CheckResult(BaseModel):
    check_id: str
    title: str
    pillar_id: str
    domain_id: str
    status: CheckStatus
    points: float
    max_points: float
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = []
    rationale: str = ""
    ccm_controls: list[str] = []
    judged_by: str = "rules"  # rules | llm


class PillarScore(BaseModel):
    pillar_id: str
    name: str
    weight: float
    points: float
    max_points: float
    coverage: float  # 0..1 fraction of checks with any evidence
    checks: list[CheckResult]

    @property
    def ratio(self) -> float:
        return self.points / self.max_points if self.max_points else 0.0


class DomainScore(BaseModel):
    domain_id: str
    name: str
    score: float  # 0..100 posture
    coverage: float  # 0..100 evidence coverage (the V1 "confidence score" concept)
    grade: str
    pillars: list[PillarScore]
    thresholds: dict[str, float] = {}


class RecommendationOption(BaseModel):
    provider: str  # gcp | aws | oss | process
    product: str
    note: str = ""
    url: str | None = None


class Recommendation(BaseModel):
    id: str
    check_id: str
    domain_id: str
    pillar_id: str
    title: str
    rationale: str
    priority: float  # higher first
    effort: str  # S | M | L
    impact: str  # low | medium | high
    kind: str  # action | discovery
    options: list[RecommendationOption] = []
    caiq_questions: list[str] = []
    ccm_controls: list[str] = []


class RedactionSummary(BaseModel):
    mode: str
    counts: dict[str, int] = {}


class AssessmentReport(BaseModel):
    id: str
    tenant_id: str
    created_at: datetime = Field(default_factory=utcnow)
    profile: str
    profile_version: str
    tool_version: str
    documents: list[DocumentRef]
    document_classes: dict[str, str] = {}
    domains: list[DomainScore]
    overall_score: float
    overall_coverage: float
    recommendations: list[Recommendation]
    redaction: RedactionSummary
    llm_provider: str
    warnings: list[str] = []
    extra: dict[str, Any] = {}
