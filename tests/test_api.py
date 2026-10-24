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


def test_per_tenant_tokens_scope_reports(settings, fixtures_dir):
    s = settings.model_copy(
        update={"auth_disabled": False, "tenant_tokens": {"acme": "tok-acme", "globex": "tok-globex"}}
    )
    api_module.app.dependency_overrides[api_module.settings_dep] = lambda: s
    client = TestClient(api_module.app)
    acme = {"Authorization": "Bearer tok-acme"}
    globex = {"Authorization": "Bearer tok-globex"}
    r = client.post(
        "/assessments",
        json={"source_uri": f"file://{fixtures_dir / 'synthetic_acme'}", "profile": "security_only"},
        headers=acme,
    )
    assert r.status_code == 200 and r.json()["tenant_id"] == "acme"
    run_id = r.json()["id"]
    assert client.get(f"/assessments/{run_id}", headers=acme).status_code == 200
    assert client.get(f"/assessments/{run_id}", headers=globex).status_code == 404  # other tenant cannot see it
    assert client.get(f"/assessments/{run_id}", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert (settings.workspace_dir / "reports" / "acme" / run_id / "report.json").exists()
    api_module.app.dependency_overrides.clear()


def test_async_job_roundtrip(settings, fixtures_dir):
    api_module.app.dependency_overrides[api_module.settings_dep] = lambda: settings
    client = TestClient(api_module.app)  # runs background tasks before returning the response
    r = client.post(
        "/jobs", json={"source_uri": f"file://{fixtures_dir / 'synthetic_acme'}", "profile": "security_only"}
    )
    assert r.status_code == 202 and r.json()["status"] == "queued"
    job = client.get(f"/jobs/{r.json()['id']}").json()
    assert job["status"] == "done" and job["report_id"]
    assert client.get(f"/assessments/{job['report_id']}").status_code == 200
    bad = client.post("/jobs", json={"source_uri": "file:///definitely/not/here"}).json()
    assert client.get(f"/jobs/{bad['id']}").json()["status"] == "failed"
    files = [
        ("files", ("policy.md", (fixtures_dir / "synthetic_acme" / "security_policy.md").read_bytes(), "text/markdown"))
    ]
    r = client.post("/jobs/upload?profile=security_only", files=files)
    assert r.status_code == 202 and client.get(f"/jobs/{r.json()['id']}").json()["status"] == "done"
    assert client.get("/jobs/nope").status_code == 404
    api_module.app.dependency_overrides.clear()
