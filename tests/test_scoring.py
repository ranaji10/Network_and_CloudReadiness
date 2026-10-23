from readiness.config import DEFAULT_CONFIG_DIR
from readiness.models import CheckStatus, DocClass, DocumentRef, ExtractedDocument
from readiness.scoring.engine import composite, evaluate_check, score_domain
from readiness.scoring.profiles import CheckDef, load_domain, load_profile

STRONG_POLICY = (
    "mfa sso okta siem splunk firewall waf ddos vlan dmz backup rpo rto tls 1.2 kms vpn zero trust bastion ids "
    "edr nessus patch management incident response tabletop least privilege rbac access review secret manager "
    "key rotation 802.1x guest wifi network diagram cidr redundant failover"
)


def _doc(name, text, cls=DocClass.NETWORK):
    return ExtractedDocument(
        ref=DocumentRef(id=name, name=name, uri=f"file:///{name}", source="local"),
        text=text,
        classification=cls,
    )


def test_evaluate_check_states():
    profile = load_profile(DEFAULT_CONFIG_DIR, "default")
    chk = CheckDef(
        id="X-1",
        title="t",
        signals=["firewall", "waf"],
        strong_signals=["next-generation firewall"],
        negative_signals=["no firewall"],
    )
    assert evaluate_check(chk, [_doc("a", "nothing here")], profile, False)[0] == CheckStatus.UNKNOWN
    assert evaluate_check(chk, [_doc("a", "we have a firewall")], profile, False)[0] == CheckStatus.PARTIAL
    assert evaluate_check(chk, [_doc("a", "firewall and waf")], profile, False)[0] == CheckStatus.MET
    assert evaluate_check(chk, [_doc("a", "a next-generation firewall")], profile, False)[0] == CheckStatus.MET
    assert (
        evaluate_check(chk, [_doc("a", "there is no firewall, only a waf")], profile, False)[0] == CheckStatus.NOT_MET
    )


def test_snippets_only_when_requested():
    profile = load_profile(DEFAULT_CONFIG_DIR, "default")
    chk = CheckDef(id="X-1", title="t", signals=["firewall"])
    _, _, ev, _ = evaluate_check(chk, [_doc("a", "the firewall is here")], profile, False)
    assert ev and ev[0].snippet == ""
    _, _, ev, _ = evaluate_check(chk, [_doc("a", "the firewall is here")], profile, True)
    assert "firewall" in ev[0].snippet


def test_domain_scores_and_composite():
    profile = load_profile(DEFAULT_CONFIG_DIR, "default")
    dom = load_domain(DEFAULT_CONFIG_DIR, "network_security")
    empty = score_domain(dom, [], profile)
    assert empty.score == 0 and empty.coverage == 0 and empty.grade == "D"
    good = score_domain(
        dom,
        [_doc("p", STRONG_POLICY, DocClass.SECURITY_POLICY)],
        profile,
    )
    assert good.score > empty.score and good.coverage > 50
    s, c = composite([empty, good], profile)
    assert 0 <= s <= 100 and 0 <= c <= 100
