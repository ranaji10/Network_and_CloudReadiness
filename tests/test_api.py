import io
import sys

from fastapi.testclient import TestClient
from pypdf import PdfReader

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
    pdf = client.get(f"/assessments/{run_id}/report.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"] == f'attachment; filename="report-{run_id}.pdf"'
    assert pdf.content.startswith(b"%PDF")
    assert run_id in PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
    assert client.get("/assessments/nope/report.pdf").status_code == 404
    monkeypatch.setitem(sys.modules, "fpdf", None)  # deployment without the `pdf` extra
    r = client.get(f"/assessments/{run_id}/report.pdf")
    assert r.status_code == 501 and "uv sync --extra pdf" in r.json()["detail"]
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
    assert client.get(f"/assessments/{run_id}/report.pdf", headers=globex).status_code == 404
    assert client.get(f"/assessments/{run_id}/report.pdf", headers=acme).status_code == 200
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


def test_share_safe_flag_on_api(settings, fixtures_dir):
    """GRD-09: `share_safe` on the sync, upload and async paths; default behaviour untouched."""
    api_module.app.dependency_overrides[api_module.settings_dep] = lambda: settings
    client = TestClient(api_module.app)
    src = f"file://{fixtures_dir / 'synthetic_acme'}"
    r = client.post("/assessments", json={"source_uri": src, "profile": "security_only", "share_safe": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["redaction"]["mode"] == "mask" and body["redaction"]["share_safe"] is True
    assert body["documents"] and all(d["name"].startswith("doc-") for d in body["documents"])
    assert "security_policy.md" not in r.text and "network_architecture.md" not in r.text
    md = client.get(f"/assessments/{body['id']}/report.md").text
    assert "Rendered share-safe" in md and "security_policy.md" not in md
    files = [
        (
            "files",
            (
                "security_policy.md",
                (fixtures_dir / "synthetic_acme" / "security_policy.md").read_bytes(),
                "text/markdown",
            ),
        )
    ]
    r = client.post("/assessments/upload?profile=security_only&share_safe=true", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["documents"][0]["name"].startswith("doc-") and "security_policy.md" not in r.text
    r = client.post("/jobs", json={"source_uri": src, "profile": "security_only", "share_safe": True})
    job = client.get(f"/jobs/{r.json()['id']}").json()
    assert job["status"] == "done"
    assert client.get(f"/assessments/{job['report_id']}").json()["redaction"]["share_safe"] is True
    r = client.post("/jobs/upload?profile=security_only&share_safe=true", files=files)
    job = client.get(f"/jobs/{r.json()['id']}").json()
    assert client.get(f"/assessments/{job['report_id']}").json()["documents"][0]["name"].startswith("doc-")
    # default path is unchanged
    r = client.post("/assessments", json={"source_uri": src, "profile": "security_only"})
    assert r.json()["redaction"]["mode"] == "pseudonymize" and r.json()["redaction"]["share_safe"] is False
    assert any(d["name"] == "security_policy.md" for d in r.json()["documents"])


def test_answers_round_trip_and_rerun(settings, fixtures_dir):
    """AGT-03: store answers for a run, re-run with them included, coverage rises; uploads need a re-upload."""
    import shutil

    api_module.app.dependency_overrides[api_module.settings_dep] = lambda: settings
    client = TestClient(api_module.app)
    src = f"file://{fixtures_dir / 'synthetic_acme'}"
    base = client.post("/assessments", json={"source_uri": src, "profile": "security_only"}).json()
    run_id = base["id"]
    body = {"answers": [{"check_id": "NS-PER-02", "answer": "Public apps are behind a WAF with DDoS protection."}]}
    assert client.post("/assessments/nope/answers", json=body).status_code == 404
    assert client.post("/assessments/..%2Fx/answers", json=body).status_code in (400, 404)
    bad = client.post(f"/assessments/{run_id}/answers", json={"answers": [{"check_id": "NS-NOPE-99", "answer": "x"}]})
    assert bad.status_code == 400 and "unknown check" in bad.text
    assert client.post(f"/assessments/{run_id}/answers", json={"answers": []}).status_code == 422
    r = client.post(f"/assessments/{run_id}/answers", json=body)
    assert r.status_code == 200, r.text
    stored = r.json()
    assert stored["answers"] == 1 and stored["checks"] == ["NS-PER-02"] and "path" not in stored
    assert "WAF" not in r.text  # metadata only comes back
    assert (settings.workspace_dir / "reports" / "test" / "answers" / stored["document_name"]).exists()
    assert (settings.workspace_dir / "test" / "answers" / stored["document_name"]).exists()

    assert client.post("/assessments/nope/rerun").status_code == 404
    rr = client.post(f"/assessments/{run_id}/rerun")
    assert rr.status_code == 200, rr.text
    rep = rr.json()
    assert rep["profile"] == "security_only" and rep["overall_coverage"] > base["overall_coverage"]
    assert rep["extra"]["answers_included"] == 1 and any(d["source"] == "answers" for d in rep["documents"])
    assert rep["id"] != run_id and client.get(f"/assessments/{rep['id']}").status_code == 200

    files = [
        ("files", ("policy.md", (fixtures_dir / "synthetic_acme" / "security_policy.md").read_bytes(), "text/markdown"))
    ]
    up = client.post("/assessments/upload?profile=security_only", files=files).json()
    gone = client.post(f"/assessments/{up['id']}/rerun")
    assert gone.status_code == 409 and "include_answers=true" in gone.text
    up2 = client.post("/assessments/upload?profile=security_only&include_answers=true", files=files).json()
    assert up2["extra"]["answers_included"] == 1 and up2["overall_coverage"] > up["overall_coverage"]

    # the reports store holds the durable copy: a fresh workspace (another instance) still sees the answers
    shutil.rmtree(settings.workspace_dir / "test" / "answers")
    rr2 = client.post(f"/assessments/{run_id}/rerun", json={"profile": "default"})
    assert rr2.status_code == 200 and rr2.json()["extra"]["answers_included"] == 1
    assert rr2.json()["profile"] == "default"
    job = client.post("/jobs", json={"source_uri": src, "profile": "security_only", "include_answers": True}).json()
    done = client.get(f"/jobs/{job['id']}").json()
    assert done["status"] == "done"
    assert client.get(f"/assessments/{done['report_id']}").json()["extra"]["answers_included"] == 1
    api_module.app.dependency_overrides.clear()
