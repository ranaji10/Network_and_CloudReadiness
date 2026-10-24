import json
from pathlib import Path

import yaml

from readiness.adapters.llm.mock import MockLLM
from readiness.config import DEFAULT_CONFIG_DIR
from readiness.guardrails.audit import AuditLog
from readiness.guardrails.policy import GuardedLLM, estimate_cost_usd, load_pricing
from readiness.guardrails.redaction import Redactor
from readiness.models import LLMUsage
from readiness.pipeline import run_assessment
from readiness.scoring.engine import JudgeBatch
from readiness.scoring.profiles import load_domains, load_profile


def test_mock_records_deterministic_usage():
    mock = MockLLM()
    mock.generate_structured("sys", "p" * 400, JudgeBatch)
    assert mock.last_usage is not None
    assert mock.last_usage.provider == "mock" and mock.last_usage.model == "mock-1"
    assert mock.last_usage.input_tokens == (3 + 400) // 4 and mock.last_usage.output_tokens == 50
    assert mock.last_usage.total_tokens == mock.last_usage.input_tokens + 50


def test_guarded_llm_accumulates_usage_and_audits_numbers_only(settings, tmp_path: Path):
    audit = AuditLog(tmp_path / "audit.jsonl", "run", "test")
    g = GuardedLLM(MockLLM(), settings, Redactor.from_config("mask"), audit)
    for _ in range(3):
        g.generate_structured("sys", "secret text password = Sup3rSecretValue1", JudgeBatch)
    assert g.usage_total.calls == 3
    assert g.usage_total.output_tokens == 150 and g.usage_total.input_tokens > 0
    ok_events = [e for e in audit.events if e["event"] == "llm.ok"]
    assert len(ok_events) == 3
    assert {"model", "input_tokens", "output_tokens"} <= set(ok_events[0])
    assert all("Sup3rSecretValue1" not in json.dumps(e) for e in audit.events)
    assert g.estimated_cost_usd is None  # mock-1 has no pricing entry
    assert g.usage_summary()["calls"] == 3


def test_pipeline_reports_usage_per_run(settings, fixtures_dir):
    s = settings.model_copy(update={"use_llm_judge": True})
    report, md = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", s, "default", llm=MockLLM())
    usage = report.extra["llm_usage"]
    profile = load_profile(DEFAULT_CONFIG_DIR, "default")
    n_pillars = sum(len(d.pillars) for d in load_domains(DEFAULT_CONFIG_DIR, profile))
    assert usage["calls"] == n_pillars and usage["provider"] == "mock"
    assert usage["input_tokens"] > 0 and usage["output_tokens"] == 50 * n_pillars
    assert usage["estimated_cost_usd"] is None
    assert "Model usage:" in md and "cost not estimated" in md
    audit = [
        json.loads(line)
        for line in (settings.workspace_dir / "test" / report.id / "audit.jsonl").read_text().splitlines()
    ]
    end = audit[-1]
    assert end["event"] == "run.end" and end["llm_calls"] == n_pillars
    assert end["input_tokens"] == usage["input_tokens"] and end["output_tokens"] == usage["output_tokens"]


def test_no_usage_block_without_llm(settings, fixtures_dir):
    report, md = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "security_only")
    assert "llm_usage" not in report.extra and "Model usage:" not in md


def test_pricing_table_and_cost_estimate():
    pricing = load_pricing(DEFAULT_CONFIG_DIR)
    raw = yaml.safe_load((DEFAULT_CONFIG_DIR / "llm_pricing.yaml").read_text())
    for model, entry in raw["models"].items():
        assert model in pricing
        assert float(entry["input_per_million_usd"]) >= 0 and float(entry["output_per_million_usd"]) >= 0
        assert entry["currency"] == "USD" and entry["as_of"]
    opus = LLMUsage(provider="anthropic", model="claude-opus-5-5", input_tokens=1_000_000, output_tokens=100_000)
    assert estimate_cost_usd(opus, pricing) == 4.0 + 2.0
    assert estimate_cost_usd(LLMUsage(provider="x", model="unknown-model"), pricing) is None
    assert estimate_cost_usd(opus, {"claude-opus-5-5": {"input_per_million_usd": "bad"}}) is None
