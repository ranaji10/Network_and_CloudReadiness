import re

import pytest
from pydantic import ValidationError

from readiness.config import DEFAULT_CONFIG_DIR
from readiness.recommend.engine import load_catalog
from readiness.scoring.catalog import control
from readiness.scoring.profiles import (
    Profile,
    ProfileRules,
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


def test_every_catalog_option_has_docs_link_and_limitation_note():
    """REC-03 catalog contract (see the header comment of config/recommendations/catalog.yaml):
    product options (gcp / aws / oss) link to official documentation over https; every option has a note
    of at most 220 characters with a sizing hint and a sentence starting "Wrong when"; a process option
    may have url null only when its note says "no authoritative reference". REC-04 adds `cost_band`: every
    option has one of none / low / medium / high, every process option is `none`, and no note or product
    quotes a price (bands are indicative, never a quote)."""
    catalog = load_catalog(DEFAULT_CONFIG_DIR)
    seen = 0
    bands: set[str] = set()
    price = re.compile(r"(\$\s?\d|\d\s?(usd|eur|gbp)\b|\d\s?(/|per)\s?(month|user|seat))", re.I)
    for e in catalog.values():
        for o in e.options:
            seen += 1
            where = f"{e.check_id} {o.provider}"
            assert o.provider in ("gcp", "aws", "oss", "process"), f"{where}: unknown provider"
            assert o.note.strip(), f"{where}: note is empty"
            assert len(o.note) <= 220, f"{where}: note is {len(o.note)} characters, limit is 220"
            assert "wrong when" in o.note.lower(), f"{where}: note has no 'Wrong when ...' sentence"
            if o.provider == "process" and o.url is None:
                assert "no authoritative reference" in o.note.lower(), f"{where}: null url not explained"
            else:
                assert o.url and o.url.startswith("https://"), f"{where}: missing https documentation url"
            assert o.cost_band in ("none", "low", "medium", "high"), f"{where}: missing or unknown cost_band"
            bands.add(o.cost_band)
            if o.provider == "process":
                assert o.cost_band == "none", f"{where}: process options have no recurring cost"
            assert not price.search(o.note) and not price.search(o.product), f"{where}: no prices in the catalog"
    assert seen >= 150, "catalog unexpectedly small"
    assert bands == {"none", "low", "medium", "high"}, f"expected every band to be used, got {sorted(bands)}"


def test_cost_band_is_validated_and_optional():
    from readiness.models import RecommendationOption

    assert RecommendationOption(provider="gcp", product="X").cost_band is None  # older catalogs still load
    assert RecommendationOption(provider="gcp", product="X", cost_band="high").cost_band == "high"
    with pytest.raises(ValidationError):
        RecommendationOption(provider="gcp", product="X", cost_band="cheap")
    assert ProfileRules().max_cost_band is None
    assert ProfileRules(max_cost_band="low").max_cost_band == "low"
    with pytest.raises(ValidationError):
        ProfileRules(max_cost_band="free")


def test_unknown_profile_field_is_rejected():
    import pytest
    from pydantic import ValidationError

    from readiness.scoring.profiles import Profile

    base = {"id": "x", "name": "x", "version": "1", "domains": [{"id": "network_security", "weight": 100}]}
    Profile.model_validate(base)
    with pytest.raises(ValidationError):
        Profile.model_validate({**base, "pillar_weight_override": {}})
