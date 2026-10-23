from readiness.scoring.catalog import caiq_questions, control, load_catalog, search


def test_catalog_loaded():
    cat = load_catalog()
    assert cat["version"] == "4.1.0"
    assert len(cat["controls"]) > 190
    assert control("I&S-03")["domain_code"] == "I&S"


def test_caiq_questions_for_control():
    qs = caiq_questions(["IAM-14"])
    assert qs and qs[0].startswith("IAM-14.")


def test_search():
    assert any(c["id"] == "BCR-08" for c in search("backup"))
