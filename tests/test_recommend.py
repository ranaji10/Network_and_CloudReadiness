"""Recommendation engine: product-family merge (REC-06) and the priority math it builds on."""

from readiness.config import DEFAULT_CONFIG_DIR
from readiness.models import CheckResult, CheckStatus, DomainScore, PillarScore, Recommendation, RecommendationOption
from readiness.recommend.engine import (
    NO_OPTION_WITHIN_CEILING,
    family_key,
    load_catalog,
    merge_by_family,
    recommend,
    within_cost_ceiling,
)
from readiness.scoring.profiles import load_profile


def _with_ceiling(profile_id: str, band: str | None):
    profile = load_profile(DEFAULT_CONFIG_DIR, profile_id)
    return profile.model_copy(update={"rules": profile.rules.model_copy(update={"max_cost_band": band})})


def _check(cid: str, title: str, status: CheckStatus, points: float, max_points: float, ccm: list[str]) -> CheckResult:
    return CheckResult(
        check_id=cid,
        title=title,
        pillar_id="identity",
        domain_id="network_security",
        status=status,
        points=points,
        max_points=max_points,
        confidence=0.6,
        ccm_controls=ccm,
    )


def _identity_domain() -> DomainScore:
    """NS-IAM-01 NOT_MET and NS-IAM-02 PARTIAL both prefer the `gcp:cloud-identity` family; NS-IAM-04
    (secret manager) does not; NS-IAM-03 is UNKNOWN and must stay a discovery item."""
    checks = [
        _check("NS-IAM-01", "Central identity provider / SSO", CheckStatus.NOT_MET, 0, 5, ["IAM-01"]),
        _check("NS-IAM-02", "MFA enforced", CheckStatus.PARTIAL, 2, 4, ["IAM-14", "IAM-01"]),
        _check("NS-IAM-03", "Least privilege", CheckStatus.UNKNOWN, 0, 4, ["IAM-05"]),
        _check("NS-IAM-04", "Secrets in a manager", CheckStatus.NOT_MET, 0, 4, ["IAM-04"]),
    ]
    pillar = PillarScore(
        pillar_id="identity", name="Identity", weight=25, points=2, max_points=17, coverage=0.75, checks=checks
    )
    return DomainScore(
        domain_id="network_security", name="Network security", score=12, coverage=75, grade="D", pillars=[pillar]
    )


def test_family_key_uses_tag_then_normalised_product():
    assert (
        family_key(RecommendationOption(provider="gcp", product="Cloud Identity", family="Cloud-Identity "))
        == "gcp:cloud-identity"
    )
    assert family_key(RecommendationOption(provider="aws", product="  AWS   Backup ")) == "aws:aws backup"
    assert family_key(RecommendationOption(provider="gcp", product="X")) != family_key(
        RecommendationOption(provider="aws", product="X")
    )


def test_actions_sharing_a_family_merge_into_one():
    profile = load_profile(DEFAULT_CONFIG_DIR, "default")
    assert profile.rules.dedupe_by_product is True
    recs = recommend([_identity_domain()], profile, DEFAULT_CONFIG_DIR)
    actions = [r for r in recs if r.kind == "action"]
    assert [r.id for r in actions] == ["A-NS-IAM-01", "A-NS-IAM-04"]
    merged = actions[0]
    # priority: NS-IAM-01 loses 5 -> base 50 x high 1.5 x M 1.0 = 75; NS-IAM-02 loses 2 -> base 20 x 1.5 x S 1.2 = 36
    assert merged.priority == 111.0
    assert merged.family == "gcp:cloud-identity"
    assert merged.closes_check_ids == ["NS-IAM-01", "NS-IAM-02"]
    assert merged.closes_titles == ["Central identity provider / SSO", "MFA enforced"]
    assert merged.check_id == "NS-IAM-01" and merged.title == load_catalog(DEFAULT_CONFIG_DIR)["NS-IAM-01"].title
    assert merged.effort == "M" and merged.impact == "high"  # max of (M, S) and (high, high)
    assert merged.ccm_controls == ["IAM-01", "IAM-14"]  # union, first-seen order
    assert merged.options[0].provider == "gcp"
    single = actions[1]
    assert single.closes_check_ids == ["NS-IAM-04"] and single.family == "gcp:secret-manager"
    discovery = [r for r in recs if r.kind == "discovery"]
    assert [r.check_id for r in discovery] == ["NS-IAM-03"] and discovery[0].closes_check_ids == []


def test_rule_off_keeps_one_action_per_check():
    profile = load_profile(DEFAULT_CONFIG_DIR, "default")
    profile = profile.model_copy(update={"rules": profile.rules.model_copy(update={"dedupe_by_product": False})})
    actions = [r for r in recommend([_identity_domain()], profile, DEFAULT_CONFIG_DIR) if r.kind == "action"]
    assert [r.id for r in actions] == ["A-NS-IAM-01", "A-NS-IAM-04", "A-NS-IAM-02"]
    assert [r.priority for r in actions] == [75.0, 60.0, 36.0]  # NS-IAM-04 loses 4: 40 x 1.5 x 1.0
    assert all(r.closes_check_ids == [r.check_id] for r in actions)


def test_family_follows_provider_preference():
    """With oss first the preferred option changes, and so does the family that drives the merge."""
    profile = load_profile(DEFAULT_CONFIG_DIR, "security_only")  # target_providers: [oss, gcp, aws]
    actions = [r for r in recommend([_identity_domain()], profile, DEFAULT_CONFIG_DIR) if r.kind == "action"]
    assert actions[0].family == "oss:keycloak" and actions[0].closes_check_ids == ["NS-IAM-01", "NS-IAM-02"]


def test_max_recommendations_applies_after_merge():
    profile = load_profile(DEFAULT_CONFIG_DIR, "default").model_copy(update={"max_recommendations": 1})
    recs = recommend([_identity_domain()], profile, DEFAULT_CONFIG_DIR)
    assert len(recs) == 1 and recs[0].closes_check_ids == ["NS-IAM-01", "NS-IAM-02"]


def test_merge_by_family_handles_optionless_and_nested_members():
    def rec(cid: str, prio: float, options: list[RecommendationOption], **kw) -> Recommendation:
        return Recommendation(
            id=f"A-{cid}",
            check_id=cid,
            domain_id="d",
            pillar_id="p",
            title=f"Fix {cid}",
            rationale="",
            priority=prio,
            effort=kw.get("effort", "S"),
            impact=kw.get("impact", "low"),
            kind="action",
            options=options,
            closes_check_ids=kw.get("closes", [cid]),
            closes_titles=kw.get("titles", [cid]),
        )

    shared = [RecommendationOption(provider="gcp", product="Product A")]
    a = rec("X-1", 1.0, shared, effort="L")
    b = rec("X-2", 5.0, shared, impact="high", closes=["X-2", "X-9"], titles=["two", "nine"])
    c = rec("X-3", 2.0, [])  # no options: never merged
    out = {r.id: r for r in merge_by_family([a, b, c])}
    assert set(out) == {"A-X-2", "A-X-3"}
    m = out["A-X-2"]
    assert m.priority == 6.0 and m.effort == "L" and m.impact == "high"
    assert m.closes_check_ids == ["X-2", "X-9", "X-1"] and m.closes_titles == ["two", "nine", "X-1"]
    assert out["A-X-3"].closes_check_ids == ["X-3"] and out["A-X-3"].family == ""


def test_merge_keeps_the_lead_options_cost_band():
    """REC-04: a merged action shows the lead member's options, so the band printed is the lead option's,
    not the band of the lower-priority member it absorbed."""
    profile = load_profile(DEFAULT_CONFIG_DIR, "default")
    catalog = load_catalog(DEFAULT_CONFIG_DIR)
    lead_band = catalog["NS-IAM-01"].options[0].cost_band  # gcp Cloud Identity as IdP
    member_band = catalog["NS-IAM-02"].options[0].cost_band  # gcp 2-Step Verification on it
    assert lead_band == "medium" and member_band == "none"  # the two really differ, so the test means something
    merged = next(r for r in recommend([_identity_domain()], profile, DEFAULT_CONFIG_DIR) if r.id == "A-NS-IAM-01")
    assert merged.closes_check_ids == ["NS-IAM-01", "NS-IAM-02"]
    assert merged.options[0].cost_band == lead_band
    assert all(o.cost_band for o in merged.options)


def test_within_cost_ceiling_orders_bands_and_keeps_unbanded_options():
    high = RecommendationOption(provider="gcp", product="X", cost_band="high")
    none = RecommendationOption(provider="process", product="Y", cost_band="none")
    unbanded = RecommendationOption(provider="oss", product="Z")
    assert within_cost_ceiling(high, None) and within_cost_ceiling(high, "high")
    assert not within_cost_ceiling(high, "medium") and not within_cost_ceiling(high, "none")
    assert within_cost_ceiling(none, "none") and within_cost_ceiling(unbanded, "none")


def test_max_cost_band_filters_options_and_keeps_the_finding():
    """NS-IAM-01 has gcp medium, aws low, oss low; NS-IAM-04 (secrets) is low on every provider."""
    profile = _with_ceiling("default", "low")
    actions = {r.id: r for r in recommend([_identity_domain()], profile, DEFAULT_CONFIG_DIR) if r.kind == "action"}
    sso = actions["A-NS-IAM-01"]
    assert [o.provider for o in sso.options] == ["aws", "oss"]  # gcp (medium) dropped, order kept
    assert all(o.cost_band == "low" for o in sso.options)
    # the preferred option changed, so the family (and the merge) follows the affordable option
    assert sso.family == "aws:iam-identity-center"
    assert NO_OPTION_WITHIN_CEILING not in sso.rationale
    assert len(actions["A-NS-IAM-04"].options) == 3  # nothing above low: untouched
    # a ceiling of none leaves SSO with no product: the action stays, with the reason in its rationale
    profile = _with_ceiling("default", "none")
    recs = recommend([_identity_domain()], profile, DEFAULT_CONFIG_DIR)
    sso = next(r for r in recs if r.id == "A-NS-IAM-01")
    assert sso.options == [] and sso.family == "" and sso.closes_check_ids == ["NS-IAM-01"]
    assert f"{NO_OPTION_WITHIN_CEILING} (profile `max_cost_band: none`)" in sso.rationale
    mfa = next(r for r in recs if r.id == "A-NS-IAM-02")  # 2-Step Verification is `none`, so it survives alone
    assert [o.cost_band for o in mfa.options] == ["none", "none", "none"]
    # the rule changes which options are listed, never a score or a priority
    unlimited = {
        r.id: r.priority for r in recommend([_identity_domain()], _with_ceiling("default", None), DEFAULT_CONFIG_DIR)
    }
    assert sso.priority == 75.0 and unlimited["A-NS-IAM-01"] == 111.0  # 111 = 75 + 36 merged without a ceiling


def test_public_sector_profile_sets_a_medium_ceiling_and_every_action_keeps_an_option():
    profile = load_profile(DEFAULT_CONFIG_DIR, "public_sector")
    assert profile.rules.max_cost_band == "medium"
    catalog = load_catalog(DEFAULT_CONFIG_DIR)
    for e in catalog.values():
        kept = [o for o in e.options if within_cost_ceiling(o, "medium") and o.provider in profile.target_providers]
        assert kept, f"{e.check_id}: every option is above the public_sector cost ceiling"


def test_catalog_family_tags_are_consistent():
    """A family tag must be shared by at least two entries of the same provider, otherwise it is a typo."""
    catalog = load_catalog(DEFAULT_CONFIG_DIR)
    seen: dict[str, set[str]] = {}
    for e in catalog.values():
        for o in e.options:
            if o.family:
                seen.setdefault(family_key(o), set()).add(e.check_id)
    assert seen, "expected at least one tagged family in the catalog"
    lonely = {k: v for k, v in seen.items() if len(v) < 2}
    assert not lonely, f"family tags used by a single entry: {lonely}"
