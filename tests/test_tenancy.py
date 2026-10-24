import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from readiness.adapters.storage.local import LocalBlobStore
from readiness.cli import app
from readiness.tenancy import export_tenant, purge_tenant, read_manifest, tenant_keys


def _seed(root: Path) -> LocalBlobStore:
    store = LocalBlobStore(root)
    store.put("acme/run1/report.json", b'{"a":1}')
    store.put("acme/run1/report.md", b"# acme")
    store.put("acme/run2/audit.jsonl", b"{}\n")
    store.put("globex/run9/report.json", b'{"g":1}')
    return store


def test_local_store_list_and_delete_guard_root(tmp_path: Path):
    store = _seed(tmp_path / "s")
    assert tenant_keys(store, "acme") == ["acme/run1/report.json", "acme/run1/report.md", "acme/run2/audit.jsonl"]
    assert list(store.list("globex/")) == ["globex/run9/report.json"]
    assert list(store.list("nope/")) == []
    store.delete("acme/run2/audit.jsonl")
    assert not (tmp_path / "s" / "acme" / "run2").exists()  # empty folders are removed
    assert (tmp_path / "s" / "acme" / "run1").exists()
    import pytest

    with pytest.raises(PermissionError):
        store.delete("../outside")


def test_export_contains_only_the_tenant(tmp_path: Path):
    store = _seed(tmp_path / "s")
    out = tmp_path / "acme.zip"
    manifest = export_tenant({"reports": store}, "acme", out)
    assert manifest["file_count"] == 3 and manifest["tenant_id"] == "acme"
    names = set(zipfile.ZipFile(out).namelist())
    assert names == {
        "reports/acme/run1/report.json",
        "reports/acme/run1/report.md",
        "reports/acme/run2/audit.jsonl",
        "manifest.json",
    }
    assert all(f["sha256"] for f in manifest["files"])
    assert read_manifest(out)["file_count"] == 3
    assert json.loads(out.with_suffix(".manifest.json").read_text())["tenant_id"] == "acme"


def test_purge_is_dry_run_by_default_and_spares_other_tenants(tmp_path: Path):
    store = _seed(tmp_path / "s")
    planned = purge_tenant({"reports": store}, "acme")
    assert len(planned["reports"]) == 3 and store.exists("acme/run1/report.json")
    done = purge_tenant({"reports": store}, "acme", dry_run=False)
    assert len(done["reports"]) == 3
    assert tenant_keys(store, "acme") == []
    assert store.exists("globex/run9/report.json")


def test_tenant_id_validation(tmp_path: Path):
    import pytest

    store = _seed(tmp_path / "s")
    for bad in ("", "../x", "a/b", "x" * 70):
        with pytest.raises(ValueError):
            tenant_keys(store, bad)


def test_cli_export_and_purge(tmp_path: Path, monkeypatch):
    ws = tmp_path / "ws"
    _seed(ws)  # pipeline-style workspace: <ws>/<tenant>/<run>/...
    _seed(ws / "reports")  # local provider reports store: <ws>/reports/<tenant>/<run>/...
    monkeypatch.setenv("READINESS_PROVIDER", "local")
    monkeypatch.setenv("READINESS_WORKSPACE_DIR", str(ws))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    r = runner.invoke(app, ["tenant", "export", "acme", "--out", str(tmp_path / "out.zip")])
    assert r.exit_code == 0, r.output
    names = zipfile.ZipFile(tmp_path / "out.zip").namelist()
    assert "workspace/acme/run1/report.json" in names and "reports/acme/run1/report.json" in names
    assert not any("globex" in n for n in names)
    r = runner.invoke(app, ["tenant", "purge", "acme"])
    assert r.exit_code == 0 and "dry run" in r.output and (ws / "acme" / "run1" / "report.json").exists()
    r = runner.invoke(app, ["tenant", "purge", "acme", "--yes"])
    assert r.exit_code == 0 and "deleted 6 object(s)" in r.output, r.output
    assert not (ws / "acme").exists() and not (ws / "reports" / "acme").exists()
    assert (ws / "globex" / "run9" / "report.json").exists()
