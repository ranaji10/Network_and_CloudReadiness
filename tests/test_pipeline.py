import json

import pytest

from readiness.models import CheckStatus
from readiness.pipeline import run_assessment
from readiness.scoring.profiles import load_profile


def test_end_to_end_offline(settings, fixtures_dir):
    report, md = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "default")
    assert report.llm_provider == "none"
    assert len(report.documents) == 6  # README + 5 docs
    assert report.document_classes
    assert 0 < report.overall_score <= 100 and 0 < report.overall_coverage <= 100
    ns = next(d for d in report.domains if d.domain_id == "network_security")
    assert ns.score >= 60, md  # synthetic policy is deliberately strong
    assert any(r.kind == "discovery" for r in report.recommendations)
    assert any(r.kind == "action" for r in report.recommendations)
    # guardrails: secrets and identifiers from the fixtures never reach the report
    assert "Sup3rSecretValue1" not in md and "AIzaSy" not in md and "10.10.0.1" not in md
    assert "netops@acme-widgets.example" not in md
    assert report.redaction.counts.get("generic_credential_assignment", 0) >= 1
    out = settings.workspace_dir / "test" / report.id
    assert (out / "report.md").exists() and (out / "report.json").exists() and (out / "audit.jsonl").exists()
    audit = [json.loads(line) for line in (out / "audit.jsonl").read_text().splitlines()]
    assert audit[0]["event"] == "run.start" and audit[-1]["event"] == "run.end"
    assert all("Sup3rSecretValue1" not in json.dumps(e) for e in audit)
    assert (out / "pseudonym_mapping.local.json").exists()


def test_negative_signal_marks_not_met(settings, fixtures_dir):
    report, _ = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "default")
    ai = next(d for d in report.domains if d.domain_id == "agentic_ai_readiness")
    checks = {c.check_id: c for p in ai.pillars for c in p.checks}
    assert checks["AI-GOV-03"].status in (CheckStatus.MET, CheckStatus.PARTIAL)  # human-in-the-loop memo


def test_profiles_change_weighting(settings, fixtures_dir):
    a, _ = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "security_only")
    b, _ = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "gcp_migration")
    assert [d.domain_id for d in a.domains] == ["network_security"]
    assert b.recommendations[0].options == [] or b.recommendations[0].options[0].provider in (
        "gcp",
        "process",
    )


@pytest.mark.parametrize("profile_id", ["healthcare", "finance", "public_sector"])
def test_industry_profiles_run_offline(settings, fixtures_dir, profile_id):
    profile = load_profile(settings.config_dir, profile_id)
    report, md = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, profile_id)
    assert report.llm_provider == "none" and report.profile == profile_id
    assert [d.domain_id for d in report.domains] == [d.id for d in profile.domains]
    assert 0 < report.overall_score <= 100 and 0 < report.overall_coverage <= 100
    assert len(report.recommendations) <= profile.max_recommendations
    # the profile's pillar emphasis reaches the scored pillars and therefore the report
    for dom in report.domains:
        overrides = profile.pillar_weight_overrides.get(dom.domain_id, {})
        for pillar in dom.pillars:
            if pillar.pillar_id in overrides:
                assert pillar.weight == overrides[pillar.pillar_id], (profile_id, dom.domain_id, pillar.pillar_id)
                assert f"{pillar.name} (weight {pillar.weight:g})" in md
    assert "Sup3rSecretValue1" not in md and "10.10.0.1" not in md


def test_finance_profile_demands_more_corroboration(settings, fixtures_dir):
    """Three distinct signals are needed for a PASS under finance, so it can never score above default."""
    default, _ = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "default")
    finance, _ = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "finance")
    ns_default = next(d for d in default.domains if d.domain_id == "network_security")
    ns_finance = next(d for d in finance.domains if d.domain_id == "network_security")
    met = lambda dom: {c.check_id for p in dom.pillars for c in p.checks if c.status == CheckStatus.MET}  # noqa: E731
    assert met(ns_finance) <= met(ns_default)


def test_llm_judge_uses_guarded_mock(settings, fixtures_dir):
    from readiness.adapters.llm.mock import MockLLM

    mock = MockLLM(
        canned={
            "JudgeBatch": {
                "verdicts": [{"check_id": "NS-PER-01", "status": "not_met", "confidence": 0.9, "rationale": "x"}]
            }
        }
    )
    s = settings.model_copy(update={"use_llm_judge": True})
    report, _ = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", s, "security_only", llm=mock)
    assert report.llm_provider == "mock" and mock.calls
    assert all("untrusted client data" in system for system, _ in mock.calls)
    assert all("10.10.0.1" not in prompt and "Sup3rSecretValue1" not in prompt for _, prompt in mock.calls)
    c = next(c for p in report.domains[0].pillars for c in p.checks if c.check_id == "NS-PER-01")
    assert c.status == CheckStatus.NOT_MET and c.judged_by == "llm"


def test_share_safe_report_hides_names_and_pseudonyms(settings, fixtures_dir):
    """GRD-09: a share-safe run masks (never pseudonymises), drops snippets and replaces document names with
    opaque labels everywhere in the report; the label-to-name map lives only in audit.jsonl."""
    import re

    s = settings.model_copy(update={"share_safe": True, "include_evidence_snippets": True})  # snippets forced off
    report, md = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", s, "default")
    out = settings.workspace_dir / "test" / report.id
    rendered = md + (out / "report.json").read_text() + (out / "report.md").read_text()
    assert f"tenant `{s.tenant_id}`" not in md and "tenant `withheld`" in md
    fixture_names = {p.name for p in (fixtures_dir / "synthetic_acme").iterdir()}
    assert len(fixture_names) == 6
    assert not any(name in rendered for name in fixture_names)
    assert report.redaction.mode == "mask" and report.redaction.share_safe
    label = re.compile(r"doc-[0-9a-f]{6}")
    assert all(label.fullmatch(d.name) and d.uri == f"share-safe://{d.name}" for d in report.documents)
    evidence = [e for d in report.domains for p in d.pillars for c in p.checks for e in c.evidence]
    assert evidence and all(e.snippet == "" and label.fullmatch(e.doc_name) for e in evidence)
    assert "10.10.0.1" not in rendered and "netops@acme-widgets.example" not in rendered
    assert not re.search(r"<(ip|email|host|phone|aws-account)-\d\d>", rendered)  # no reversible tokens
    assert not (out / "pseudonym_mapping.local.json").exists()
    assert "Rendered share-safe" in md and 0 < report.overall_score <= 100
    audit = [json.loads(line) for line in (out / "audit.jsonl").read_text().splitlines()]
    assert audit[0]["event"] == "run.start" and audit[0]["share_safe"] is True and audit[0]["redaction"] == "mask"
    labels = [e for e in audit if e["event"] == "doc.share_safe_label"]
    assert {e["name"] for e in labels} == fixture_names
    assert {e["label"] for e in labels} == {d.name for d in report.documents}
    assert {e["doc"] for e in labels} == {d.id for d in report.documents}


def test_egress_guardrail_blocks_real_provider(settings):
    import pytest

    from readiness.adapters.registry import make_llm

    s = settings.model_copy(update={"llm_provider": "gemini", "allow_llm_egress": False})
    with pytest.raises(PermissionError):
        make_llm(s)
