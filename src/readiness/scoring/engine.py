"""Deterministic evidence-based scoring, optionally refined by an LLM judge.

Two numbers per domain, deliberately kept apart:
* score    (0-100): posture, from checks that are met/partially met.
* coverage (0-100): how many checks had *any* evidence. This is the V1 "confidence score": low coverage
  means "we need more documents or answers", not "the client is insecure".

LLM judge cost controls (LLM-06), all deterministic and configured from `Settings`:
* pre-selection: a pillar is judged on the documents that matched at least one of its checks' signals,
  ranked by the number of distinct signal hits (`rank_documents`), at most `judge_max_docs_per_pillar` of
  them (`0` sends every relevant document, the pre-LLM-06 behaviour);
* batching: the selected documents are cut to an even share of `judge_batch_chars` (never below
  `MIN_DOC_CHARS`) and sent in one call when they fit, otherwise in as few calls as possible, each within
  `judge_batch_chars`; verdicts from several batches are merged, the most confident non-unknown one wins;
* cacheable prefix: the system prompt for a pillar is `JUDGE_SYSTEM` plus the pillar's check list (the
  guardrail layer appends the untrusted-data preamble), so it is byte-identical for every batch of that
  pillar and for every run, and providers that cache prompt prefixes (Anthropic `cache_control`) can reuse
  it. Document text only ever appears in the user turn, after the cached prefix."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from pydantic import BaseModel, Field

from readiness.guardrails.policy import wrap_untrusted
from readiness.models import (
    CheckResult,
    CheckStatus,
    DocClass,
    DomainScore,
    Evidence,
    ExtractedDocument,
    PillarScore,
)
from readiness.ports import LLMProvider
from readiness.scoring.profiles import CheckDef, DomainDef, PillarDef, Profile

DEFAULT_JUDGE_MAX_DOCS = 8  # documents per pillar sent to the judge; 0 = every relevant document
DEFAULT_JUDGE_BATCH_CHARS = 60_000  # evidence characters per judge call
MIN_DOC_CHARS = 2000  # a selected document is never cut shorter than this


@dataclass
class _Hit:
    doc: ExtractedDocument
    signal: str
    snippet: str


@lru_cache(maxsize=4096)
def compile_signal(signal: str) -> re.Pattern[str]:
    """The one signal convention used everywhere (checks, wave planning): a signal containing any of
    `\\ [ ] ( ) . * + ? |` is a regular expression, anything else is a whole case-insensitive word or phrase."""
    return re.compile(signal if any(ch in signal for ch in r"\[]().*+?|") else r"\b" + re.escape(signal) + r"\b", re.I)


def _find(doc_text: str, signal: str, window: int = 80) -> str | None:
    rx = compile_signal(signal)
    m = rx.search(doc_text)
    if not m:
        return None
    a, b = max(0, m.start() - window), min(len(doc_text), m.end() + window)
    return " ".join(doc_text[a:b].split())


def candidate_pool(check: CheckDef, docs: list[ExtractedDocument]) -> list[ExtractedDocument]:
    """The documents a check is evaluated against: relevant ones of its `doc_classes`, or every relevant one
    when the filter leaves nothing (classification is heuristic). Questionnaire answers (AGT-03) are addressed
    to specific checks, so they are searched by every check regardless of its `doc_classes` filter."""
    pool = [
        d
        for d in docs
        if d.is_relevant
        and (
            not check.doc_classes or d.classification in check.doc_classes or d.classification == DocClass.QUESTIONNAIRE
        )
    ]
    if not any(d.classification != DocClass.QUESTIONNAIRE for d in pool):
        pool = [d for d in docs if d.is_relevant]
    return pool


def evaluate_check(
    check: CheckDef, docs: list[ExtractedDocument], profile: Profile, include_snippets: bool
) -> tuple[CheckStatus, float, list[Evidence], str]:
    pool = candidate_pool(check, docs)
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


def rank_documents(pillar: PillarDef, docs: list[ExtractedDocument]) -> list[tuple[ExtractedDocument, int]]:
    """Relevance of each document to a pillar: the number of distinct (check, signal) pairs it matches across
    the pillar's checks (weak, strong and negative signals alike, each check searched on its own candidate
    pool). Documents with no hit are left out. The order is deterministic (most hits first, then document name,
    then id), so the same pack always sends the same documents to the model."""
    hits: dict[str, int] = {}
    by_id: dict[str, ExtractedDocument] = {}
    for check in pillar.checks:
        signals = check.negative_signals + check.strong_signals + check.signals
        for d in candidate_pool(check, docs):
            n = sum(1 for s in signals if compile_signal(s).search(d.text))
            if n:
                hits[d.ref.id] = hits.get(d.ref.id, 0) + n
                by_id.setdefault(d.ref.id, d)
    return sorted(((by_id[i], n) for i, n in hits.items()), key=lambda t: (-t[1], t[0].ref.name, t[0].ref.id))


def select_documents(pillar: PillarDef, docs: list[ExtractedDocument], max_docs: int) -> list[ExtractedDocument]:
    """The documents the judge sees for a pillar: the `max_docs` best-ranked ones, or every relevant document
    in source order (the pre-LLM-06 behaviour) when `max_docs` is 0 or negative."""
    if max_docs <= 0:
        return [d for d in docs if d.is_relevant]
    return [d for d, _ in rank_documents(pillar, docs)[:max_docs]]


def judge_prompts(
    pillar: PillarDef,
    results: list[CheckResult],
    docs: list[ExtractedDocument],
    max_docs: int = DEFAULT_JUDGE_MAX_DOCS,
    batch_chars: int = DEFAULT_JUDGE_BATCH_CHARS,
) -> tuple[str, list[str]]:
    """(system prompt, one evidence prompt per batch) for a pillar.

    The system prompt carries everything static (`JUDGE_SYSTEM` and the check list), so it is byte-identical
    across batches and runs; the evidence prompts carry only `<document>` blocks of redacted text. Each selected
    document is cut to an even share of `batch_chars` (at least `MIN_DOC_CHARS`); the blocks are then packed in
    rank order into batches of at most `batch_chars` characters (a block longer than that is a batch on its own).
    A pillar with no matching document still gets one short prompt saying so, so that the model answers `unknown`
    from no evidence rather than guessing."""
    checks = {c.id: c for c in pillar.checks}
    questions = "\n".join(f"- {r.check_id}: {checks[r.check_id].question or checks[r.check_id].title}" for r in results)
    system = f"{JUDGE_SYSTEM}\n\nChecks:\n{questions}"
    selected = select_documents(pillar, docs, max_docs)
    if not selected:
        return system, ["Evidence:\n(no document matched any signal of these checks)"]
    budget = max(MIN_DOC_CHARS, batch_chars // len(selected))
    batches: list[list[str]] = []
    size = 0
    for d in selected:
        block = wrap_untrusted(d.ref.name, d.text[:budget])
        if batches and size + len(block) + 2 <= batch_chars:
            batches[-1].append(block)
            size += len(block) + 2
        else:
            batches.append([block])
            size = len(block)
    return system, ["Evidence:\n" + "\n\n".join(b) for b in batches]


def _better(new: JudgeVerdict, old: JudgeVerdict | None) -> bool:
    """Merge rule for verdicts on the same check from different batches: a verdict beats `unknown`, then the
    more confident one wins."""
    if old is None:
        return True
    new_unknown, old_unknown = new.status == CheckStatus.UNKNOWN, old.status == CheckStatus.UNKNOWN
    if new_unknown != old_unknown:
        return old_unknown
    return new.confidence > old.confidence


def llm_refine(
    pillar: PillarDef,
    results: list[CheckResult],
    docs: list[ExtractedDocument],
    llm: LLMProvider,
    profile: Profile,
    max_docs: int = DEFAULT_JUDGE_MAX_DOCS,
    batch_chars: int = DEFAULT_JUDGE_BATCH_CHARS,
) -> list[CheckResult]:
    """Ask the LLM about the whole pillar (one call per evidence batch, normally a single one) and override
    rule verdicts when it is confident. `judge_prompts` decides what is sent."""
    checks = {c.id: c for c in pillar.checks}
    system, prompts = judge_prompts(pillar, results, docs, max_docs, batch_chars)
    by_id: dict[str, JudgeVerdict] = {}
    for prompt in prompts:
        batch = llm.generate_structured(system, prompt, JudgeBatch)
        for v in batch.verdicts:
            if _better(v, by_id.get(v.check_id)):
                by_id[v.check_id] = v
    out = []
    for r in results:
        verdict = by_id.get(r.check_id)
        if (
            verdict
            and verdict.confidence >= profile.rules.llm_override_min_confidence
            and verdict.status != CheckStatus.UNKNOWN
        ):
            r = r.model_copy(
                update={
                    "status": verdict.status,
                    "confidence": verdict.confidence,
                    "rationale": f"LLM: {verdict.rationale}"[:500],
                    "judged_by": "llm",
                    "points": _points(checks[r.check_id], verdict.status, profile),
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
    judge_max_docs: int = DEFAULT_JUDGE_MAX_DOCS,
    judge_batch_chars: int = DEFAULT_JUDGE_BATCH_CHARS,
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
            results = llm_refine(p, results, docs, llm, profile, judge_max_docs, judge_batch_chars)
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
