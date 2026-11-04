"""The outside-the-network posture (ADR-20261103) is enforced by scripts/check_no_system_access.py."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("check_no_system_access", Path("scripts/check_no_system_access.py"))
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_repo_passes_the_check():
    assert mod.main() == 0


def test_forbidden_dependency_is_flagged():
    pyproject = '[project]\nname = "x"\ndependencies = ["pydantic>=2", "paramiko>=3"]\n'
    lock = '[[package]]\nname = "scapy"\nversion = "2.6"\n'
    findings = mod.check_dependencies(pyproject, lock)
    assert any("paramiko" in f for f in findings)
    assert any("scapy" in f for f in findings)
    assert mod.check_dependencies('[project]\nname = "x"\ndependencies = ["httpx>=0.27"]\n', None) == []


def test_forbidden_import_is_flagged():
    text = "import socket\nfrom paramiko import SSHClient\nimport os, subprocess\nfrom readiness import models\n"
    findings = mod.check_source_file("src/readiness/x.py", text)
    assert [f.split("'")[1] for f in findings] == ["socket", "paramiko", "subprocess"]


def test_non_document_scheme_is_flagged():
    text = 'if scheme == "file":\n    pass\nif scheme == "ssh":\n    pass\n'
    assert len(mod.check_registry_schemes("registry.py", text)) == 1
    assert mod.check_registry_schemes("registry.py", 'if scheme == "gdrive":\n') == []


def test_network_tool_in_image_is_flagged():
    text = "RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates nmap \\\n && rm -rf /x\n"
    assert any("nmap" in f for f in mod.check_image("Dockerfile", text))
    assert mod.check_image("Dockerfile", "RUN apt-get install -y ca-certificates\n") == []
