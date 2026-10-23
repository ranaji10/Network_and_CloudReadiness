"""The assessment pipeline. One function, `run_assessment`, wires the ports together:

    source -> extract -> classify -> redact -> score (rules [+ LLM]) -> recommend -> report

It is the same code path for the CLI, the HTTP API and the ADK agent, so behaviour cannot drift
between surfaces."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import structlog

from readiness import __version__
from readiness.adapters.registry import make_llm, make_source
from readiness.config import Settings
from readiness.guardrails.audit import AuditLog
from readiness.guardrails.policy import GuardedLLM
from readiness.guardrails.redaction import Redactor
from readiness.ingestion.classify import classify
from readiness.ingestion.extract import extract_text
from readiness.models import AssessmentReport, DocClass, ExtractedDocument, RedactionSummary
from readiness.ports import DocumentSource, LLMProvider
from readiness.recommend.engine import recommend
from readiness.report.markdown import render
from readiness.scoring.engine import composite, score_domain
from readiness.scoring.profiles import load_domains, load_profile

log = structlog.get_logger()


def ingest(source: DocumentSource, settings: Settings, audit: AuditLog) -> list[ExtractedDocument]:
    docs: list[ExtractedDocument] = []
    for ref in source.list():
        try:
            raw = source.read(ref)
        except Exception as exc:  # noqa: BLE001
            audit.event("doc.read_error", doc=ref.id, error=type(exc).__name__)
            docs.append(ExtractedDocument(ref=ref, text="", extraction_error=f"read: {type(exc).__name__}"))
            continue
        text, truncated, err = extract_text(ref.name, raw, settings.max_text_chars)
        cls, conf = classify(ref.name, text) if text else (DocClass.IRRELEVANT, 0.0)
        docs.append(
            ExtractedDocument(
                ref=ref,
                text=text,
                classification=cls,
                classification_confidence=conf,
                truncated=truncated,
                extraction_error=err,
            )
        )
        audit.event("doc.ingested", doc=ref.id, chars=len(text), cls=str(cls), truncated=truncated, error=err or "")
    return docs


def run_assessment(
    source_uri: str,
    settings: Settings,
    profile_id: str | None = None,
    llm: LLMProvider | None = None,
    write_outputs: bool = True,
) -> tuple[AssessmentReport, str]:
    """Returns (report, markdown). Writes report.json / report.md / audit.jsonl into the workspace."""
    run_id = uuid.uuid4().hex[:12]
    profile = load_profile(settings.config_dir, profile_id or settings.default_profile)
    domains = load_domains(settings.config_dir, profile)
    out_dir = Path(settings.workspace_dir) / settings.tenant_id / run_id
    audit = AuditLog(out_dir / "audit.jsonl" if write_outputs else None, run_id, settings.tenant_id)
    audit.event("run.start", profile=profile.id, source_scheme=source_uri.split("://")[0], llm=settings.llm_provider)

    redactor = Redactor.from_config(settings.redaction_mode)
    source = make_source(source_uri, settings)
    docs = ingest(source, settings, audit)
    warnings: list[str] = []
    if not any(d.is_relevant for d in docs):
        warnings.append("No relevant documents were found; every check is 'no evidence'.")

    # Redact before anything can leave the process. Scoring runs on redacted text too, so a report
    # can never contain an identifier the redaction policy would have hidden from the model.
    for d in docs:
        d.text = redactor.redact(d.text)

    judge: GuardedLLM | None = None
    if settings.use_llm_judge:
        judge = GuardedLLM(llm or make_llm(settings), settings, redactor, audit)

    scores = [score_domain(dom, docs, profile, judge, settings.include_evidence_snippets) for dom in domains]
    overall, coverage = composite(scores, profile)
    recs = recommend(scores, profile, settings.config_dir)
    report = AssessmentReport(
        id=run_id,
        tenant_id=settings.tenant_id,
        profile=profile.id,
        profile_version=profile.version,
        tool_version=__version__,
        documents=[d.ref for d in docs],
        document_classes={d.ref.id: str(d.classification) for d in docs},
        domains=scores,
        overall_score=overall,
        overall_coverage=coverage,
        recommendations=recs,
        redaction=RedactionSummary(mode=settings.redaction_mode, counts=redactor.summary()),
        llm_provider=(judge.name if judge else "none"),
        warnings=warnings + [f"{d.ref.name}: {d.extraction_error}" for d in docs if d.extraction_error],
    )
    md = render(report)
    if write_outputs:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.json").write_text(report.model_dump_json(indent=1))
        (out_dir / "report.md").write_text(md)
        if settings.redaction_mode == "pseudonymize" and settings.provider == "local" and redactor.mapping:
            # Reverse mapping stays local-only, never uploaded. Lets an analyst de-pseudonymise on site.
            (out_dir / "pseudonym_mapping.local.json").write_text(json.dumps(redactor.mapping, indent=1))
    audit.event("run.end", score=overall, coverage=coverage, docs=len(docs), recs=len(recs))
    log.info(
        "assessment.done",
        run=run_id,
        score=overall,
        coverage=coverage,
        out=str(out_dir) if write_outputs else "",
    )
    return report, md
