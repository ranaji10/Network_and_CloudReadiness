from readiness.guardrails.redaction import Redactor

GKEY = "AIza" + "Sy" + "F" * 33  # built at runtime so no key-shaped string is committed
SAMPLE = f"""host db-01.acme.internal at 10.10.0.5 and 10.10.0.6; again 10.10.0.5
email ops@acme-widgets.example password = Sup3rSecretValue1
key {GKEY} token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sflKxwRJSMeKKF2QT4fwpMeJf36POk6yJVadQssw5c
-----BEGIN RSA PRIVATE KEY-----
MIIabc
-----END RSA PRIVATE KEY-----
"""


def test_pseudonymize_is_stable_and_masks_secrets():
    r = Redactor.from_config("pseudonymize")
    out = r.redact(SAMPLE)
    assert "Sup3rSecretValue1" not in out and "AIzaSy" not in out and "PRIVATE KEY-----\nMIIabc" not in out
    assert "eyJhbGciOiJIUzI1NiJ9" not in out
    assert "10.10.0.5" not in out and out.count("<ip-01>") == 2 and "<ip-02>" in out
    assert "ops@acme-widgets.example" not in out and "<email-01>" in out
    assert r.mapping["<ip-01>"] == "10.10.0.5"
    assert r.summary()["ipv4"] == 3


def test_mask_mode_has_no_mapping():
    r = Redactor.from_config("mask")
    out = r.redact(SAMPLE)
    assert "[REDACTED:ip]" in out and not r.mapping


def test_off_mode_still_masks_secrets():
    r = Redactor.from_config("off")
    out = r.redact(SAMPLE)
    assert "10.10.0.5" in out  # identifiers kept
    assert "Sup3rSecretValue1" not in out and "[REDACTED:credential]" in out
