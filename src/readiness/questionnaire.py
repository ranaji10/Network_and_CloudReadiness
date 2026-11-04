"""Questionnaire round trip (tracker AGT-03): the V1 "assisted discovery" flow.

A report lists *discovery* items (CAIQ questions) for every check that no document covered. The client
answers them; the answers are stored as one Markdown document in the tenant workspace
(`<workspace>/<tenant>/answers/<run_id>-<timestamp>.md`) and the assessment is re-run with
`include_answers=true`, which ingests that folder as a second source (`source: answers`) so coverage and
scores rise.

Answers are client-confidential documents like any other: same extraction, redaction and scoring, same
tenant prefix, purged by `readiness tenant purge`. Only counts reach the audit log.

The stored file keeps the check title and the questions for the human reader, but the rule engine scores
only the answer bodies (`evidence_text`): titles and CAIQ questions quote the very words the checks look
for, so scoring them verbatim would turn "no" into evidence."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from readiness.config import Settings
from readiness.guardrails.audit import AuditLog
from readiness.models import DocumentRef
from readiness.scoring.catalog import caiq_questions
from readiness.scoring.profiles import CheckDef, load_domain
from readiness.tenancy import validate_tenant_id

ANSWERS_DIR = "answers"
MARKER = "# Questionnaire answers"
_RUN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_CHECK_RE = re.compile(r"^[A-Z]{2,4}-[A-Z0-9]{2,6}-\d{1,3}$")
_SECTION_RE = re.compile(r"^## (?P<id>[A-Z]{2,4}-[A-Z0-9]{2,6}-\d{1,3})\b.*$", re.M)
_ANSWER_HEADER = "Answer:"


def validate_run_id(run_id: str) -> str:
    run_id = run_id.strip()
    if not _RUN_RE.match(run_id):
        raise ValueError("run id must be 1-64 chars of letters, digits, '_' or '-'")
    return run_id


class QuestionnaireAnswer(BaseModel):
    """One answered discovery item. `question` is optional: the question as shown in the report."""

    check_id: str
    answer: str = Field(min_length=1, max_length=20_000)
    question: str = Field(default="", max_length=2_000)

    @field_validator("check_id")
    @classmethod
    def _check_id(cls, v: str) -> str:
        v = v.strip().upper()
        if not _CHECK_RE.match(v):
            raise ValueError(f"invalid check id {v!r} (expected e.g. NS-PER-02)")
        return v

    @field_validator("answer", "question")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class QuestionnaireAnswers(BaseModel):
    """An answer set submitted by the client for the discovery items of one assessment run."""

    run_id: str
    answers: list[QuestionnaireAnswer] = Field(min_length=1, max_length=500)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("run_id")
    @classmethod
    def _run_id(cls, v: str) -> str:
        return validate_run_id(v)

    @property
    def check_ids(self) -> list[str]:
        return sorted({a.check_id for a in self.answers})


class StoredAnswers(BaseModel):
    """What a caller gets back after storing: metadata only, never the answer text."""

    run_id: str
    document_id: str
    document_name: str
    path: str
    answers: int
    checks: list[str]


def all_checks(config_dir: Path) -> dict[str, CheckDef]:
    """Every check of every scoring domain, by id (a questionnaire can span domains and profiles)."""
    out: dict[str, CheckDef] = {}
    for path in sorted((config_dir / "scoring").glob("*.yaml")):
        for pillar in load_domain(config_dir, path.stem).pillars:
            for check in pillar.checks:
                out[check.id] = check
    return out


def answers_dir(settings: Settings) -> Path:
    return Path(settings.workspace_dir) / validate_tenant_id(settings.tenant_id) / ANSWERS_DIR


def render_answers(answers: QuestionnaireAnswers, checks: dict[str, CheckDef]) -> str:
    """The stored Markdown: one section per answered check, questions quoted for the reader."""
    lines = [
        MARKER,
        "",
        f"Answers to the discovery questions of assessment run `{answers.run_id}`, "
        f"submitted {answers.submitted_at:%Y-%m-%d %H:%M UTC}. "
        "One section per check; only the text under `Answer:` is scored as evidence.",
    ]
    for a in answers.answers:
        check = checks[a.check_id]
        lines += ["", f"## {a.check_id} {check.title}", ""]
        if check.ccm:
            lines.append(f"CCM controls: {', '.join(check.ccm)}")
        questions = [a.question] if a.question else []
        questions += [q for q in caiq_questions(check.ccm)[:6] if q != a.question]
        if questions:
            lines.append("")
            lines.append("Questions:")
            lines.extend(f"> {q}" for q in questions)
        lines += ["", _ANSWER_HEADER, "", a.answer]
    return "\n".join(lines) + "\n"


def is_answers_document(text: str) -> bool:
    return text.lstrip().startswith(MARKER + "\n") or text.strip() == MARKER


def evidence_text(text: str) -> tuple[str, int]:
    """Only the answer bodies of a stored answers document, each prefixed with its check id.

    Returns (text, number of answers). Anything outside an `Answer:` block (title, CCM ids, quoted
    questions) is dropped so the rule engine never scores our own wording."""
    parts: list[str] = []
    sections = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(sections):
        end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        body = text[m.end() : end]
        _, sep, answer = body.partition(f"\n{_ANSWER_HEADER}\n")
        if not sep:
            continue
        answer = answer.strip()
        if answer:
            parts.append(f"{m.group('id')}: {answer}")
    return "\n\n".join(parts), len(parts)


def store_answers(answers: QuestionnaireAnswers, settings: Settings) -> StoredAnswers:
    """Write the answers document under the tenant workspace and log counts to the run's audit file.

    Raises ValueError for check ids that exist in no scoring domain."""
    checks = all_checks(Path(settings.config_dir))
    unknown = [c for c in answers.check_ids if c not in checks]
    if unknown:
        raise ValueError(f"unknown check id(s): {', '.join(unknown)}")
    folder = answers_dir(settings)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{answers.run_id}-{answers.submitted_at:%Y%m%dT%H%M%S%f}.md"
    path = folder / name
    text = render_answers(answers, checks)
    path.write_text(text)
    doc_id = DocumentRef.make_id(f"file://{path.resolve()}")
    audit = AuditLog(
        Path(settings.workspace_dir) / settings.tenant_id / answers.run_id / "audit.jsonl",
        answers.run_id,
        settings.tenant_id,
    )
    audit.event(
        "questionnaire.stored",
        doc=doc_id,
        answers=len(answers.answers),
        checks=len(answers.check_ids),
        chars=len(text),
    )
    return StoredAnswers(
        run_id=answers.run_id,
        document_id=doc_id,
        document_name=name,
        path=str(path),
        answers=len(answers.answers),
        checks=answers.check_ids,
    )


def parse_answer_file(data: Any, run_id: str | None = None) -> QuestionnaireAnswers:
    """Accept the YAML/JSON shapes the CLI and agents produce: a list of answers, or a mapping with
    `answers` (and optionally `run_id`). An explicit `run_id` argument wins over the file."""
    if isinstance(data, list):
        data = {"answers": data}
    if not isinstance(data, dict):
        raise ValueError("answers must be a list of {check_id, answer} or a mapping with an 'answers' key")
    payload = {"answers": data.get("answers", []), "run_id": run_id or data.get("run_id", "")}
    return QuestionnaireAnswers.model_validate(payload)
