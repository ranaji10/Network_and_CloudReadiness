from readiness.config import DEFAULT_CONFIG_DIR
from readiness.recommend.engine import load_catalog
from readiness.scoring.catalog import control
from readiness.scoring.profiles import list_profiles, load_domain, load_domains


def test_all_profiles_and_domains_load():
    profiles = list_profiles(DEFAULT_CONFIG_DIR)
    assert {p.id for p in profiles} >= {"default", "gcp_migration", "security_only"}
    for p in profiles:
        assert load_domains(DEFAULT_CONFIG_DIR, p)


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
