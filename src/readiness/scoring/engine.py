"""Deterministic evidence-based scoring, optionally refined by an LLM judge.

Two numbers per domain, deliberately kept apart:
* score    (0-100): posture, from checks that are met/partially met.
* coverage (0-100): how many checks had *any* evidence. This is the V1 "confidence score": low coverage
  means "we need more documents or answers", not "the client is insecure"."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from readiness.models import CheckResult, CheckStatus, DomainScore, Evidence, ExtractedDocument, PillarScore
from readiness.ports import LLMProvider
from readiness.scoring.profiles import CheckDef, DomainDef, PillarDef, Profile


@dataclass
class _Hit:
    doc: ExtractedDocument
    signal: str
    snippet: str


def _find(doc_text: str, signal: str, window: int = 80) -> str | None:
    rx = re.compile(signal if any(ch in signal for ch in r"\[]().*+?|") else r"\b" + re.escape(signal) + r"\b", re.I)
    m = rx.search(doc_text)
    if not m:
        return None
    a, b = max(0, m.start() - window), min(len(doc_text), m.end() + window)
    return " ".join(doc_text[a:b].split())


def evaluate_check(
    check: CheckDef, docs: list[ExtractedDocument], profile: Profile, include_snippets: bool
) -> tuple[CheckStatus, float, list[Evidence], str]:
    pool = [d for d in docs if d.is_relevant and (not check.doc_classes or d.classification in check.doc_classes)]
    if not pool:  # fall back to all relevant docs: classification is heuristic
        pool = [d for d in docs if d.is_relevant]
    hits: list[_Hit] = []
    strong = False
    negative = False
    for d in pool:
        for s in check.negative_signals:
            snip = _find(d.text, s)
            if snip:
                negative = True
                hits.append(_Hit(d, f"NEGATIVE:{s}", snip))
        for s in check.strong_signals:
            snip = _find(d.text, s)
            if snip:
                strong = True
                hits.append(_Hit(d, s, snip))
        for s in check.signals:
            snip = _find(d.text, s)
            if snip:
                hits.append(_Hit(d, s, snip))
    distinct = {h.signal for h in hits if not h.signal.startswith("NEGATIVE:")}
    evidence = [
        Evidence(
            doc_id=h.doc.ref.id,
            doc_name=h.doc.ref.name,
            snippet=h.snippet if include_snippets else "",
            signal=h.signal,
        )
        for h in hits[:8]
    ]
    if negative and profile.rules.negative_overrides:
        return CheckStatus.NOT_MET, 0.6, evidence, "Explicit negative statement found in evidence."
    if strong or len(distinct) >= profile.rules.met_min_signals:
        return (
            CheckStatus.MET,
            0.7,
            evidence,
            f"{len(distinct)} distinct signal(s) found across {len({h.doc.ref.id for h in hits})} document(s).",
        )
    if distinct:
        return CheckStatus.PARTIAL, 0.5, evidence, "Weak evidence: a single signal was found."
    return CheckStatus.UNKNOWN, 0.3, [], "No evidence found in the supplied documents."


class JudgeVerdict(BaseModel):
    check_id: str
    status: CheckStatus
    confidence: float = Field(ge=0, le=1)
    rationale: str = ""
    evidence_doc: str = ""


class JudgeBatch(BaseModel):
    verdicts: list[JudgeVerdict]


JUDGE_SYSTEM = (
    "You are a cloud and network security assessor. For each control check, decide from the evidence "
    "whether it is met, partial, not_met, or unknown (no evidence). Be conservative: unknown beats guessing. "
    "Return one verdict per check id."
)


def llm_refine(
    pillar: PillarDef,
    results: list[CheckResult],
    docs: list[ExtractedDocument],
    llm: LLMProvider,
    profile: Profile,
) -> list[CheckResult]:
    """Ask the LLM about the whole pillar at once; override rule verdicts when it is confident."""
    checks = {c.id: c for c in pillar.checks}
    relevant = [d for d in docs if d.is_relevant]
    budget = max(2000, 60000 // max(1, len(relevant)))
    corpus = "\n\n".join(f'<document name="{d.ref.name}">\n{d.text[:budget]}\n</document>' for d in relevant)
    questions = "\n".join(f"- {r.check_id}: {checks[r.check_id].question or checks[r.check_id].title}" for r in results)
    prompt = f"Checks:\n{questions}\n\nEvidence:\n{corpus}"
    batch = llm.generate_structured(JUDGE_SYSTEM, prompt, JudgeBatch)
    by_id = {v.check_id: v for v in batch.verdicts}
    out = []
    for r in results:
        v = by_id.get(r.check_id)
        if v and v.confidence >= profile.rules.llm_override_min_confidence and v.status != CheckStatus.UNKNOWN:
            r = r.model_copy(
                update={
                    "status": v.status,
                    "confidence": v.confidence,
                    "rationale": f"LLM: {v.rationale}"[:500],
                    "judged_by": "llm",
                    "points": _points(checks[r.check_id], v.status, profile),
                }
            )
        out.append(r)
    return out


def _points(check: CheckDef, status: CheckStatus, profile: Profile) -> float:
    if status == CheckStatus.MET:
        return check.points
    if status == CheckStatus.PARTIAL:
        return round(check.points * profile.rules.partial_points_ratio, 2)
    return 0.0


def grade(score: float, thresholds: dict[str, float]) -> str:
    if score >= thresholds.get("grade_a", 85):
        return "A"
    if score >= thresholds.get("grade_b", 70):
        return "B"
    if score >= thresholds.get("grade_c", 50):
        return "C"
    return "D"


def score_domain(
    domain: DomainDef,
    docs: list[ExtractedDocument],
    profile: Profile,
    llm: LLMProvider | None = None,
    include_snippets: bool = False,
) -> DomainScore:
    pillars: list[PillarScore] = []
    for p in domain.pillars:
        results: list[CheckResult] = []
        for c in p.checks:
            status, conf, evidence, why = evaluate_check(c, docs, profile, include_snippets)
            results.append(
                CheckResult(
                    check_id=c.id,
                    title=c.title,
                    pillar_id=p.id,
                    domain_id=domain.id,
                    status=status,
                    points=_points(c, status, profile),
                    max_points=c.points,
                    confidence=conf,
                    evidence=evidence,
                    rationale=why,
                    ccm_controls=c.ccm,
                )
            )
        if llm is not None:
            results = llm_refine(p, results, docs, llm, profile)
        covered = sum(1 for r in results if r.status != CheckStatus.UNKNOWN)
        pillars.append(
            PillarScore(
                pillar_id=p.id,
                name=p.name,
                weight=p.weight,
                points=sum(r.points for r in results),
                max_points=p.max_points,
                coverage=covered / len(results) if results else 0.0,
                checks=results,
            )
        )
    total_w = sum(p.weight for p in pillars) or 1.0
    score = 100 * sum(p.weight * p.ratio for p in pillars) / total_w
    coverage = 100 * sum(p.weight * p.coverage for p in pillars) / total_w
    return DomainScore(
        domain_id=domain.id,
        name=domain.name,
        score=round(score, 1),
        coverage=round(coverage, 1),
        grade=grade(score, profile.thresholds),
        pillars=pillars,
        thresholds=profile.thresholds,
    )


def composite(domain_scores: list[DomainScore], profile: Profile) -> tuple[float, float]:
    w = {d.id: d.weight for d in profile.domains}
    total = sum(w.get(d.domain_id, 0) for d in domain_scores) or 1.0
    s = sum(w.get(d.domain_id, 0) * d.score for d in domain_scores) / total
    c = sum(w.get(d.domain_id, 0) * d.coverage for d in domain_scores) / total
    return round(s, 1), round(c, 1)
