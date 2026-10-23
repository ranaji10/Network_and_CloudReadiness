from fastapi.testclient import TestClient

from readiness.api import app as api_module


def test_api_roundtrip(settings, fixtures_dir, monkeypatch):
    api_module.app.dependency_overrides[api_module.settings_dep] = lambda: settings
    client = TestClient(api_module.app)
    assert client.get("/healthz").json()["status"] == "ok"
    ui = client.get("/")
    assert ui.status_code == 200 and "<title>Readiness Assessor</title>" in ui.text
    r = client.post(
        "/assessments", json={"source_uri": f"file://{fixtures_dir / 'synthetic_acme'}", "profile": "default"}
    )
    assert r.status_code == 200, r.text
    run_id = r.json()["id"]
    assert client.get(f"/assessments/{run_id}").status_code == 200
    md = client.get(f"/assessments/{run_id}/report.md").text
    assert md.startswith("# Network, Cloud")
    files = [
        (
            "files",
            (
                "policy.md",
                (fixtures_dir / "synthetic_acme" / "security_policy.md").read_bytes(),
                "text/markdown",
            ),
        )
    ]
    r = client.post("/assessments/upload?profile=security_only", files=files)
    assert r.status_code == 200 and r.json()["domains"][0]["domain_id"] == "network_security"
    api_module.app.dependency_overrides.clear()


def test_api_requires_token_when_enabled(settings):
    s = settings.model_copy(update={"auth_disabled": False, "api_token": "t0ken"})
    api_module.app.dependency_overrides[api_module.settings_dep] = lambda: s
    client = TestClient(api_module.app)
    assert client.get("/profiles").status_code == 401
    assert client.get("/profiles", headers={"Authorization": "Bearer t0ken"}).status_code == 200
    api_module.app.dependency_overrides.clear()
