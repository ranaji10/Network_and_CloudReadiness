"""AGT-03: answers to discovery questions are stored per tenant and raise coverage on re-run."""

import json
from pathlib import Path

import pytest

from readiness.adapters.storage.local import LocalBlobStore
from readiness.models import CheckStatus, DocClass
from readiness.pipeline import run_assessment
from readiness.questionnaire import (
    QuestionnaireAnswers,
    all_checks,
    evidence_text,
    is_answers_document,
    parse_answer_file,
    render_answers,
    store_answers,
)
from readiness.tenancy import purge_tenant


def _checks(report):
    return {c.check_id: c for d in report.domains for p in d.pillars for c in p.checks}


def _discovery(report):
    return {r.check_id: r for r in report.recommendations if r.kind == "discovery"}


def test_round_trip_raises_coverage_and_scores(settings, fixtures_dir):
    src = f"file://{fixtures_dir / 'synthetic_acme'}"
    base, _ = run_assessment(src, settings, "default")
    disc = _discovery(base)
    assert {"NS-PER-02", "CR-SEC-01"} <= set(disc)
    assert _checks(base)["NS-PER-02"].status == CheckStatus.UNKNOWN

    answers = parse_answer_file(
        [
            {
                "check_id": "NS-PER-02",
                "question": disc["NS-PER-02"].caiq_questions[0],
                "answer": "Yes: public apps sit behind a WAF with DDoS protection. Owner: netops@acme-widgets.example",
            },
            {"check_id": "cr-sec-01", "answer": "We hold SOC 2 Type II and ISO 27001 certification."},
        ],
        base.id,
    )
    stored = store_answers(answers, settings)
    path = Path(stored.path)
    assert path.parent == settings.workspace_dir / "test" / "answers" and path.name.startswith(base.id)
    assert stored.answers == 2 and stored.checks == ["CR-SEC-01", "NS-PER-02"]
    text = path.read_text()
    assert text.startswith("# Questionnaire answers") and "## NS-PER-02" in text and "## CR-SEC-01" in text
    assert disc["NS-PER-02"].caiq_questions[0] in text  # kept for the reader

    # the audit log of the answered run records counts only, never the answer text
    audit_path = settings.workspace_dir / "test" / base.id / "audit.jsonl"
    audit = [json.loads(line) for line in audit_path.read_text().splitlines()]
    ev = next(e for e in audit if e["event"] == "questionnaire.stored")
    assert ev["answers"] == 2 and ev["checks"] == 2 and ev["doc"] == stored.document_id
    assert all("SOC 2" not in json.dumps(e) and "netops" not in json.dumps(e) for e in audit)

    # without the flag the answers are not read
    again, _ = run_assessment(src, settings, "default")
    assert again.overall_coverage == base.overall_coverage and len(again.documents) == len(base.documents)

    rerun, md = run_assessment(src, settings, "default", include_answers=True)
    assert rerun.overall_coverage > base.overall_coverage
    assert rerun.overall_score > base.overall_score
    checks = _checks(rerun)
    assert checks["NS-PER-02"].status == CheckStatus.MET and checks["CR-SEC-01"].status == CheckStatus.MET
    assert {e.doc_id for e in checks["NS-PER-02"].evidence} == {stored.document_id}
    assert {"NS-PER-02", "CR-SEC-01"}.isdisjoint(_discovery(rerun))
    doc = next(d for d in rerun.documents if d.id == stored.document_id)
    assert doc.source == "answers" and rerun.document_classes[doc.id] == DocClass.QUESTIONNAIRE
    assert rerun.extra["answers_included"] == 2 and rerun.extra["answer_documents"] == 1
    assert "2 questionnaire answer(s) from 1 answer document(s)" in md
    assert "netops@acme-widgets.example" not in md  # answers are redacted like every other document
    rerun_audit = settings.workspace_dir / "test" / rerun.id / "audit.jsonl"
    events = [json.loads(line) for line in rerun_audit.read_text().splitlines()]
    assert any(e["event"] == "answers.ingested" and e["answers"] == 2 for e in events)


def test_titles_and_questions_are_not_scored(settings, fixtures_dir):
    """The stored file quotes the check title and the CAIQ questions, which contain the very signals the
    check looks for; a negative answer must stay 'no evidence'."""
    src = f"file://{fixtures_dir / 'synthetic_acme'}"
    store_answers(
        parse_answer_file([{"check_id": "NS-PER-02", "answer": "No, nothing of that kind is in place."}], "run1"),
        settings,
    )
    report, _ = run_assessment(src, settings, "security_only", include_answers=True)
    assert _checks(report)["NS-PER-02"].status == CheckStatus.UNKNOWN
    assert report.extra["answers_included"] == 1


def test_evidence_text_keeps_only_answer_bodies(settings):
    checks = all_checks(settings.config_dir)
    answers = QuestionnaireAnswers.model_validate(
        {
            "run_id": "abc123",
            "answers": [{"check_id": "NS-PER-02", "question": "Shown question?", "answer": "Behind a WAF."}],
        }
    )
    md = render_answers(answers, checks)
    assert is_answers_document(md) and "Shown question?" in md and checks["NS-PER-02"].title in md
    text, n = evidence_text(md)
    assert n == 1 and text == "NS-PER-02: Behind a WAF."
    assert "Shown question?" not in text and "DDoS" not in text
    assert not is_answers_document("# Network diagram\n") and evidence_text("no sections") == ("", 0)


def test_answers_copied_into_a_source_folder_are_still_parsed(settings, tmp_path):
    checks = all_checks(settings.config_dir)
    answers = parse_answer_file([{"check_id": "NS-DET-02", "answer": "An IDS and an IPS inspect traffic."}], "r1")
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "answers.md").write_text(render_answers(answers, checks))
    report, _ = run_assessment(f"file://{folder}", settings, "security_only")
    assert list(report.document_classes.values()) == [DocClass.QUESTIONNAIRE]
    assert _checks(report)["NS-DET-02"].status == CheckStatus.MET


def test_validation(settings):
    with pytest.raises(ValueError, match="unknown check id"):
        store_answers(parse_answer_file([{"check_id": "NS-NOPE-99", "answer": "x"}], "run1"), settings)
    with pytest.raises(ValueError, match="invalid check id"):
        parse_answer_file([{"check_id": "../etc/passwd", "answer": "x"}], "run1")
    with pytest.raises(ValueError, match="run id"):
        parse_answer_file([{"check_id": "NS-PER-02", "answer": "x"}], "../other")
    with pytest.raises(ValueError):
        parse_answer_file([], "run1")  # at least one answer
    with pytest.raises(ValueError):
        parse_answer_file("not a list", "run1")
    parsed = parse_answer_file({"run_id": "from-file", "answers": [{"check_id": "ns-per-02", "answer": " ok "}]})
    assert parsed.run_id == "from-file" and parsed.answers[0].check_id == "NS-PER-02"
    assert parsed.answers[0].answer == "ok"


def test_include_answers_without_stored_answers_warns(settings, fixtures_dir):
    report, _ = run_assessment(
        f"file://{fixtures_dir / 'synthetic_acme'}", settings, "security_only", include_answers=True
    )
    assert report.extra["answers_included"] == 0 and report.extra["answer_documents"] == 0
    assert any("no questionnaire answers are stored" in w for w in report.warnings)


def test_answers_live_under_the_tenant_and_are_purged(settings):
    stored = store_answers(parse_answer_file([{"check_id": "NS-PER-02", "answer": "waf"}], "run1"), settings)
    ws = LocalBlobStore(settings.workspace_dir)
    planned = purge_tenant({"workspace": ws}, "test")["workspace"]
    assert f"test/answers/{stored.document_name}" in planned and Path(stored.path).exists()
    purge_tenant({"workspace": ws}, "test", dry_run=False)
    assert not Path(stored.path).exists() and not (settings.workspace_dir / "test").exists()
