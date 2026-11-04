"""LLM-06: judge document pre-selection, batching and the cacheable prompt prefix.

The 100-document pack is SYNTHETIC, generated into `tmp_path` from a handful of templates with varied
signals; nothing is committed. The mock provider's usage numbers are proportional to prompt length, so the
saving is measured offline."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from readiness.adapters.llm.mock import MockLLM
from readiness.config import DEFAULT_CONFIG_DIR, Settings
from readiness.guardrails.policy import UNTRUSTED_PREAMBLE
from readiness.models import CheckStatus, DocClass, DocumentRef, ExtractedDocument
from readiness.pipeline import run_assessment
from readiness.scoring.engine import (
    JUDGE_SYSTEM,
    MIN_DOC_CHARS,
    JudgeVerdict,
    _better,
    judge_prompts,
    rank_documents,
    select_documents,
)
from readiness.scoring.profiles import CheckDef, PillarDef, load_domains, load_profile

# ---------------------------------------------------------------------------
# Synthetic pack: 10 relevant templates and 2 noise templates, 100 files, signals varied per file.
# ---------------------------------------------------------------------------

FILLER = (
    "This section describes operating procedures, responsibilities and review cadences for the platform team. "
    "Changes follow the change management process and are reviewed quarterly by the architecture board. "
) * 12

TEMPLATES = {
    "network_standard": (
        "# Network standard {i}\n\nThe network architecture uses a next-generation firewall at every ingress with "
        "{alt0}. VLAN segmentation separates the DMZ from the LAN; a management network with a jump host is "
        "out-of-band. Remote access is via VPN with WireGuard and MFA. Guest wifi runs on WPA3.\n\n{filler}"
    ),
    "security_policy": (
        "# Information security policy {i}\n\nThe policy mandates least privilege, RBAC and an access review every "
        "quarter. Encryption at rest and TLS 1.3 in transit. Incident response follows the IR plan with a tabletop "
        "exercise yearly. {alt1} Vulnerability scans run with Nessus and patch management is monthly.\n\n{filler}"
    ),
    "identity_standard": (
        "# Identity standard {i}\n\nActive Directory is federated with Okta for SSO; MFA is enforced for all users. "
        "Service accounts rotate credentials through a secret manager with key rotation every 90 days. "
        "Access recertification is done by data owners. {alt2}\n\n{filler}"
    ),
    "operations_runbook": (
        "# Operations runbook {i}\n\nMonitoring and logging feed a SIEM (Splunk) with intrusion detection sensors. "
        "On-call SRE rotation handles alerts; patching windows are weekly. Backup jobs are verified with a restore "
        "test; RPO is 4 hours and RTO is 8 hours. {alt3}\n\n{filler}"
    ),
    "cloud_landing_zone": (
        "# Cloud landing zone design {i}\n\nThe reference architecture defines a landing zone with organization "
        "policy, a CIS benchmark security baseline, Cloud KMS with CMEK and Security Command Center. Connectivity "
        "uses Interconnect and Cloud VPN; the CIDR address space follows RFC 1918. Terraform (infrastructure as "
        "code) deploys everything. {alt4}\n\n{filler}"
    ),
    "data_platform": (
        "# Data platform {i}\n\nDatabases: PostgreSQL and SQL Server, storage on NFS and SAN. A data catalog lists "
        "data owners; the data warehouse is BigQuery with lineage and data quality checks. Data classification and "
        "data residency rules are defined. Backup policy retention is 35 days. {alt5}\n\n{filler}"
    ),
    "ai_governance": (
        "# AI governance and agent platform {i}\n\nThe AI policy covers responsible AI and an AI risk assessment "
        "(DPIA). Agents run on Vertex AI with MCP tools and function calling; human in the loop approval gates "
        "exist. A model inventory and model cards are kept. Prompt injection testing, an evaluation golden set "
        "and OpenTelemetry tracing are in place. {alt6}\n\n{filler}"
    ),
    "inventory": (
        "hostname,os version,vcpu,ram,role\n"
        + "\n".join(f"srv-{{i}}-{n:02d},Windows Server 2019,4,16,application" for n in range(1, 30))
        + "\nserver inventory export {i} (cmdb)\n"
    ),
    "licensing": (
        "# Licences and costs {i}\n\nThe enterprise agreement covers Windows Server licences under software "
        "assurance. A TCO model compares capex and opex; FinOps tagging policy and cost allocation labels are "
        "defined. Training and certification budget covers cloud skills. {alt7}\n\n{filler}"
    ),
    "app_portfolio": (
        "# Application portfolio {i}\n\nThe application inventory lists dependencies for each system in the "
        "solution design. Workloads run on Kubernetes (GKE) and Cloud Run with autoscaling; APIs are exposed via "
        "an API gateway (Apigee) with rate limits and OpenAPI specs. CPU utilisation and peak load are tracked. "
        "{alt8}\n\n{filler}"
    ),
    "menu": "# Cafeteria menu week {i}\n\nMonday: soup. Tuesday: pasta. Wednesday: salad. Thursday: curry.\n",
    "newsletter": (
        "# Staff newsletter {i}\n\nThis month's newsletter celebrates the sports day and the marketing team's new "
        "press release. Meeting notes from the town hall are attached.\n"
    ),
}
ALTS = [
    ["Cloud Armor in front of public apps", "a WAF with DDoS protection", "default deny egress filters", ""],
    ["Security Hub and GuardDuty findings are triaged weekly.", "ISO 27001 certified.", "", "SOC 2 report available."],
    ["Workload identity federation is used for pipelines.", "", "Identity federation to Cloud Identity.", ""],
    ["Dual ISP uplinks give high availability with failover.", "", "Chronicle is being evaluated.", ""],
    ["A dependency map covers 40 applications.", "", "Route 53 and certificate automation.", ""],
    ["Vector embeddings for semantic search are stored in a vector store.", "", "Great Expectations validate.", ""],
    ["A data processing agreement with zero data retention is signed.", "", "DLP rules block exfiltration.", ""],
    ["Upskilling plan for 20 engineers.", "", "Ansible manages configuration.", ""],
    ["GraphQL and REST endpoints are catalogued.", "", "Serverless functions handle events.", ""],
]


def make_pack(folder: Path, count: int = 100) -> dict[str, str]:
    """Writes `count` synthetic files and returns name -> text."""
    folder.mkdir(parents=True, exist_ok=True)
    names = list(TEMPLATES)
    out: dict[str, str] = {}
    for i in range(count):
        kind = names[i % len(names)]
        alts = {f"alt{k}": ALTS[k][(i // len(names) + k) % len(ALTS[k])] for k in range(len(ALTS))}
        text = TEMPLATES[kind].format(i=i, filler=FILLER, **alts)
        name = f"{i:03d}_{kind}{'.csv' if kind == 'inventory' else '.md'}"
        (folder / name).write_text(text)
        out[name] = text
    return out


def _settings(tmp_path: Path, **overrides) -> Settings:
    return Settings(
        _env_file=None,
        provider="local",
        llm_provider="mock",
        use_llm_judge=True,
        workspace_dir=tmp_path / "ws",
        config_dir=DEFAULT_CONFIG_DIR,
        tenant_id="test",
        auth_disabled=True,
        **overrides,
    )


def _run(tmp_path: Path, docs: Path, **overrides):
    mock = MockLLM()
    report, _ = run_assessment(
        f"file://{docs}", _settings(tmp_path, **overrides), "default", llm=mock, write_outputs=False
    )
    return report, mock


def _summary(report) -> dict:
    return {
        "overall": (report.overall_score, report.overall_coverage),
        "checks": {c.check_id: c.status for d in report.domains for p in d.pillars for c in p.checks},
    }


DOC_TAG = re.compile(r'<document name="([^"]+)">')


def test_hundred_document_pack_halves_judge_cost(tmp_path: Path):
    """Acceptance for LLM-06: input tokens and judge calls drop by at least half against pre-selection off."""
    pack = tmp_path / "docs"
    texts = make_pack(pack)
    assert len(texts) == 100

    base_report, base_mock = _run(tmp_path, pack, judge_max_docs_per_pillar=0)
    report, mock = _run(tmp_path, pack)
    base, after = base_report.extra["llm_usage"], report.extra["llm_usage"]

    assert after["input_tokens"] <= 0.5 * base["input_tokens"], (after, base)
    assert after["calls"] <= 0.5 * base["calls"], (after, base)
    assert after["cache_read_input_tokens"] == 0 and after["cache_creation_input_tokens"] == 0  # mock has no cache
    # the mock returns no verdicts, so pre-selection cannot move a single score or status
    assert _summary(report) == _summary(base_report)
    assert report.overall_coverage > 0
    # with pre-selection every pillar fits one call; without it, every relevant document goes out in batches
    profile = load_profile(DEFAULT_CONFIG_DIR, "default")
    n_pillars = sum(len(d.pillars) for d in load_domains(DEFAULT_CONFIG_DIR, profile))
    assert after["calls"] == n_pillars and base["calls"] > n_pillars
    assert all(len(DOC_TAG.findall(prompt)) <= 8 for _, prompt in mock.calls)
    relevant = {d.name for d in report.documents if report.document_classes[d.id] != "irrelevant"}
    assert {name for _, prompt in base_mock.calls for name in DOC_TAG.findall(prompt)} == relevant
    assert len(relevant) > 60


def test_preselection_is_deterministic_and_sends_only_documents_with_hits(tmp_path: Path):
    pack = tmp_path / "docs"
    texts = make_pack(pack)
    _, first = _run(tmp_path, pack)
    _, second = _run(tmp_path, pack)
    assert [p for _, p in first.calls] == [p for _, p in second.calls]

    profile = load_profile(DEFAULT_CONFIG_DIR, "default")
    checks = {c.id: c for d in load_domains(DEFAULT_CONFIG_DIR, profile) for p in d.pillars for c in p.checks}
    for system, prompt in first.calls:
        pillar_checks = [checks[i] for i in re.findall(r"^- ([A-Z]+-[A-Z]+-\d+):", system, re.M)]
        assert pillar_checks
        names = DOC_TAG.findall(prompt)
        assert names, "a pillar with hits in this pack must receive documents"
        for name in names:
            text = texts[name]
            signals = [s for c in pillar_checks for s in c.signals + c.strong_signals + c.negative_signals]
            assert any(re.search(r"\b" + re.escape(s) + r"\b", text, re.I) for s in signals), (name, system[:80])
        assert "menu" not in prompt and "newsletter" not in prompt


def test_system_prompt_is_the_static_cacheable_prefix(tmp_path: Path):
    pack = tmp_path / "docs"
    make_pack(pack, count=24)
    _, mock = _run(tmp_path, pack)
    for system, prompt in mock.calls:
        assert system.startswith(JUDGE_SYSTEM) and "Checks:\n- " in system and system.endswith(UNTRUSTED_PREAMBLE)
        assert "<document name=" not in system  # never client text in the cached prefix
        assert prompt.startswith("Evidence:\n")
    # a pillar's prefix does not depend on the pack: another run with other documents produces the same systems
    other = tmp_path / "other"
    make_pack(other, count=5)
    _, mock2 = _run(tmp_path, other)
    assert [s for s, _ in mock.calls] == [s for s, _ in mock2.calls]


# ---------------------------------------------------------------------------
# Unit level: ranking, selection, batching and verdict merging
# ---------------------------------------------------------------------------


def _doc(name: str, text: str, cls: DocClass = DocClass.NETWORK) -> ExtractedDocument:
    return ExtractedDocument(
        ref=DocumentRef(id=name, name=name, uri=f"file:///{name}", source="local"),
        text=text,
        classification=cls,
        classification_confidence=0.9,
    )


PILLAR = PillarDef(
    id="perimeter",
    name="Perimeter",
    weight=25,
    checks=[
        CheckDef(id="X-1", title="Firewall", signals=["firewall", "ngfw"], negative_signals=["no firewall"]),
        CheckDef(id="X-2", title="WAF", signals=["waf", "ddos"], question="Is there a WAF?"),
    ],
)


def test_rank_documents_counts_distinct_hits_and_drops_zero_hit_docs():
    docs = [
        _doc("b_two", "a firewall and a waf"),
        _doc("a_two", "ngfw plus ddos protection"),
        _doc("one", "just a firewall"),
        _doc("none", "cafeteria menu"),
        _doc("neg", "there is no firewall here"),  # negative signal counts as a hit: the judge must see it
        _doc("empty", "", DocClass.NETWORK),
        _doc("noise", "firewall firewall firewall", DocClass.IRRELEVANT),
    ]
    ranked = rank_documents(PILLAR, docs)
    assert [(d.ref.name, n) for d, n in ranked] == [("a_two", 2), ("b_two", 2), ("neg", 2), ("one", 1)]
    assert [d.ref.name for d in select_documents(PILLAR, docs, 2)] == ["a_two", "b_two"]
    assert [d.ref.name for d in select_documents(PILLAR, docs, 0)] == ["b_two", "a_two", "one", "none", "neg"]


def test_judge_prompts_batch_within_budget_and_keep_check_list_in_system():
    from readiness.models import CheckResult

    results = [
        CheckResult(
            check_id=c.id,
            title=c.title,
            pillar_id="perimeter",
            domain_id="d",
            status=CheckStatus.UNKNOWN,
            points=0,
            max_points=5,
            confidence=0.3,
            rationale="",
        )
        for c in PILLAR.checks
    ]
    docs = [_doc(f"doc{i}", f"firewall {i} " + "x" * 5000) for i in range(6)]
    system, prompts = judge_prompts(PILLAR, results, docs, max_docs=0, batch_chars=9000)
    assert system == f"{JUDGE_SYSTEM}\n\nChecks:\n- X-1: Firewall\n- X-2: Is there a WAF?"
    # 6 documents, 9000 / 6 = 1500 < MIN_DOC_CHARS, so each is cut to 2000 (about 2,035 with its tag):
    # four fit in the first batch, the remaining two go in a second call
    assert len(prompts) == 2 and all(len(p) <= 9000 + len("Evidence:\n") for p in prompts)
    assert [len(DOC_TAG.findall(p)) for p in prompts] == [4, 2]
    assert all(len(block) <= MIN_DOC_CHARS + 40 for p in prompts for block in p.split("\n\n")[1:])
    # top-8 selection with the default budget: one batch
    _, one = judge_prompts(PILLAR, results, docs)
    assert len(one) == 1 and len(DOC_TAG.findall(one[0])) == 6
    # nothing selected: one short prompt that says so
    _, none = judge_prompts(PILLAR, results, [_doc("menu", "soup of the day")])
    assert none == ["Evidence:\n(no document matched any signal of these checks)"]


def test_verdict_merge_prefers_known_then_confident():
    met = JudgeVerdict(check_id="X-1", status=CheckStatus.MET, confidence=0.6)
    unknown = JudgeVerdict(check_id="X-1", status=CheckStatus.UNKNOWN, confidence=0.9)
    not_met = JudgeVerdict(check_id="X-1", status=CheckStatus.NOT_MET, confidence=0.8)
    assert _better(met, None) and _better(met, unknown) and not _better(unknown, met)
    assert _better(not_met, met) and not _better(met, not_met)


def test_batched_pillar_merges_verdicts_from_every_batch(tmp_path: Path):
    """With pre-selection off and a tiny batch budget, a pillar needs several calls; a verdict from any batch
    still reaches the result, and the guarded path is used for each call."""
    pack = tmp_path / "docs"
    make_pack(pack, count=12)
    mock = MockLLM(
        canned={"JudgeBatch": {"verdicts": [{"check_id": "NS-PER-01", "status": "not_met", "confidence": 0.9}]}}
    )
    s = _settings(tmp_path, judge_max_docs_per_pillar=0, judge_batch_chars=6000)
    report, _ = run_assessment(f"file://{pack}", s, "security_only", llm=mock, write_outputs=False)
    n_pillars = sum(len(d.pillars) for d in report.domains)
    assert report.extra["llm_usage"]["calls"] > n_pillars
    c = next(c for p in report.domains[0].pillars for c in p.checks if c.check_id == "NS-PER-01")
    assert c.status == CheckStatus.NOT_MET and c.judged_by == "llm"


@pytest.mark.parametrize("max_docs", [1, 3])
def test_max_docs_setting_caps_documents_per_call(tmp_path: Path, max_docs: int):
    pack = tmp_path / "docs"
    make_pack(pack, count=30)
    _, mock = _run(tmp_path, pack, judge_max_docs_per_pillar=max_docs)
    assert mock.calls and all(len(DOC_TAG.findall(prompt)) <= max_docs for _, prompt in mock.calls)
