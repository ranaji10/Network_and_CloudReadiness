import pytest
from pydantic import ValidationError

from readiness.config import DEFAULT_CONFIG_DIR
from readiness.recommend.engine import load_catalog
from readiness.scoring.catalog import control
from readiness.scoring.profiles import (
    Profile,
    apply_pillar_weight_overrides,
    list_profiles,
    load_domain,
    load_domains,
    load_profile,
)

INDUSTRY_PROFILES = {"healthcare", "finance", "public_sector"}


def test_all_profiles_and_domains_load():
    profiles = list_profiles(DEFAULT_CONFIG_DIR)
    assert {p.id for p in profiles} >= {"default", "gcp_migration", "security_only"} | INDUSTRY_PROFILES
    for p in profiles:
        assert load_domains(DEFAULT_CONFIG_DIR, p)  # also validates every pillar_weight_overrides entry
        assert all(d.weight > 0 for d in p.domains), p.id
        assert p.thresholds["grade_a"] > p.thresholds["grade_b"] > p.thresholds["grade_c"], p.id


def test_profile_ids_match_file_names():
    for path in sorted((DEFAULT_CONFIG_DIR / "profiles").glob("*.yaml")):
        assert load_profile(DEFAULT_CONFIG_DIR, path.stem).id == path.stem


@pytest.mark.parametrize("profile_id", sorted(INDUSTRY_PROFILES))
def test_industry_profiles_state_their_compliance_emphasis(profile_id):
    p = load_profile(DEFAULT_CONFIG_DIR, profile_id)
    assert p.description and p.pillar_weight_overrides, "industry profiles must say what they stress"
    # every domain listed is weighted and every override is a positive pillar weight
    assert {d.id for d in p.domains} >= set(p.pillar_weight_overrides)
    for dom_id, pillars in p.pillar_weight_overrides.items():
        known = {pl.id for pl in load_domain(DEFAULT_CONFIG_DIR, dom_id).pillars}
        assert set(pillars) <= known, (profile_id, dom_id)
        assert all(w > 0 for w in pillars.values())


def test_industry_profiles_weight_their_domains_as_documented():
    hc = load_profile(DEFAULT_CONFIG_DIR, "healthcare")
    fin = load_profile(DEFAULT_CONFIG_DIR, "finance")
    pub = load_profile(DEFAULT_CONFIG_DIR, "public_sector")
    default = load_profile(DEFAULT_CONFIG_DIR, "default")
    top = {p.id: max(p.domains, key=lambda d: d.weight).id for p in (hc, fin, pub)}
    assert top == {
        "healthcare": "network_security",
        "finance": "network_security",
        "public_sector": "cloud_readiness",
    }
    # regulated sectors expect stronger evidence than the balanced profile
    for p in (hc, fin):
        assert p.thresholds["high_confidence_coverage"] > default.thresholds["high_confidence_coverage"]
        assert p.thresholds["grade_a"] > default.thresholds["grade_a"]
    assert fin.rules.met_min_signals > default.rules.met_min_signals
    # public sector stresses data residency and AI transparency
    assert pub.pillar_weight_overrides["cloud_readiness"]["data"] > 20
    assert pub.pillar_weight_overrides["agentic_ai_readiness"]["governance"] > 25


def test_pillar_weight_overrides_are_applied_by_load_domains():
    base = load_profile(DEFAULT_CONFIG_DIR, "default")
    assert load_domains(DEFAULT_CONFIG_DIR, base)[0].pillars[-1].weight == 10  # resilience default
    p = base.model_copy(update={"pillar_weight_overrides": {"network_security": {"resilience": 30}}})
    ns = next(d for d in load_domains(DEFAULT_CONFIG_DIR, p) if d.id == "network_security")
    weights = {pl.id: pl.weight for pl in ns.pillars}
    assert weights["resilience"] == 30
    assert weights["perimeter"] == 25, "unlisted pillars keep their configured weight"
    # the file on disk is untouched: loading the domain again yields the default
    assert load_domain(DEFAULT_CONFIG_DIR, "network_security").pillars[-1].weight == 10


def test_pillar_weight_overrides_reject_unknown_ids_and_bad_weights():
    base = load_profile(DEFAULT_CONFIG_DIR, "default")
    dom = load_domain(DEFAULT_CONFIG_DIR, "network_security")
    with pytest.raises(ValueError, match="unknown pillar"):
        apply_pillar_weight_overrides(dom, {"no_such_pillar": 5})
    with pytest.raises(ValueError, match="unknown pillar"):
        load_domains(
            DEFAULT_CONFIG_DIR, base.model_copy(update={"pillar_weight_overrides": {"network_security": {"x": 1}}})
        )
    raw = base.model_dump()
    with pytest.raises(ValidationError, match="not in domains"):
        Profile.model_validate({**raw, "pillar_weight_overrides": {"no_such_domain": {"perimeter": 5}}})
    with pytest.raises(ValidationError, match="must be > 0"):
        Profile.model_validate({**raw, "pillar_weight_overrides": {"network_security": {"perimeter": 0}}})


def test_every_check_has_catalog_entry_and_valid_ccm_ids():
    catalog = load_catalog(DEFAULT_CONFIG_DIR)
    for dom in ("network_security", "cloud_readiness", "agentic_ai_readiness"):
        d = load_domain(DEFAULT_CONFIG_DIR, dom)
        for p in d.pillars:
            assert p.weight > 0
            for c in p.checks:
                assert c.id in catalog, f"{c.id} has no recommendation"
                for cid in c.ccm:
                    assert control(cid), f"{c.id} references unknown CCM control {cid}"
                assert c.signals or c.strong_signals, f"{c.id} has no signals"
