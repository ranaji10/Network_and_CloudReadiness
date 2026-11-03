"""Fail if the package could reach into a client's systems.

The assessor reads documents, never systems (docs/product/VISION.md, ADR-20261103-outside-the-client-network).
Clients let it run outside their network precisely because nothing in it can scan, log in to or probe a
host. This check keeps that true as the code grows:

1. No scanning, remote-access or protocol-client library in `pyproject.toml` or `uv.lock`.
2. No import of such a library, nor of raw `socket` / `subprocess`, anywhere under `src/readiness`.
3. Document sources stay document stores: the schemes `adapters/registry.py` dispatches on must be in the
   allow-list below (extend it, and the ADR, when a new read-only document store is added).
4. No network tooling installed into the container image.

Usage: uv run python scripts/check_no_system_access.py  (exit 1 on findings)"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Distribution names (as they appear in pyproject / uv.lock) that scan, probe or open sessions to hosts.
FORBIDDEN_PACKAGES: frozenset[str] = frozenset(
    {
        "scapy", "python-nmap", "nmap", "pysnmp", "pysnmp-lextudio", "ldap3", "python-ldap",
        "paramiko", "asyncssh", "fabric", "netmiko", "napalm", "ncclient", "pywinrm", "pypsrp",
        "impacket", "smbprotocol", "pysmb", "wmi", "dnspython", "masscan", "python-masscan",
        "pyshark", "pcapy", "pypcap", "telnetlib3", "ssh2-python", "pexpect",
    }
)  # fmt: skip

# Top-level module names that must not be imported under src/readiness.
FORBIDDEN_MODULES: frozenset[str] = frozenset(
    {
        "socket", "subprocess", "telnetlib", "ftplib", "smtplib", "poplib", "imaplib", "nntplib",
        "scapy", "nmap", "pysnmp", "ldap3", "ldap", "paramiko", "asyncssh", "fabric", "netmiko", "napalm",
        "ncclient", "winrm", "pypsrp", "impacket", "smbprotocol", "smbclient", "smb", "wmi", "dns",
        "masscan", "pyshark", "pcapy", "pcap", "telnetlib3", "ssh2", "pexpect",
    }
)  # fmt: skip

# Document-store schemes the registry may dispatch on. Anything else (http, ssh, smb, ...) is a change
# of posture and needs a superseding ADR.
ALLOWED_SOURCE_SCHEMES: frozenset[str] = frozenset({"file", "gs", "s3", "gdrive"})

# apt/apk packages that would turn the runtime image into a scanner or a jump host.
FORBIDDEN_IMAGE_TOOLS: frozenset[str] = frozenset(
    {"nmap", "masscan", "netcat", "netcat-openbsd", "netcat-traditional", "nc", "telnet", "openssh-client",
     "openssh-server", "ssh", "snmp", "ldap-utils", "smbclient", "tcpdump", "hping3", "iputils-ping", "traceroute"}
)  # fmt: skip

IMPORT_RX = re.compile(
    r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import\b|import\s+([A-Za-z_][\w.]*(?:\s*,\s*[A-Za-z_][\w.]*)*))"
)
SCHEME_RX = re.compile(r"""scheme\s*==\s*["']([a-z0-9+.\-]+)["']""")
APT_RX = re.compile(r"\b(?:apt-get|apt|apk)\s+(?:install|add)\b([^&\n]*)")


def _dependency_names_from_pyproject(text: str) -> set[str]:
    data = tomllib.loads(text)
    specs: list[str] = list(data.get("project", {}).get("dependencies", []))
    for extra in data.get("project", {}).get("optional-dependencies", {}).values():
        specs.extend(extra)
    for group in data.get("dependency-groups", {}).values():
        specs.extend(s for s in group if isinstance(s, str))
    names: set[str] = set()
    for spec in specs:
        m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._\-]*)", spec)
        if m:
            names.add(m.group(1).lower().replace("_", "-"))
    return names


def _package_names_from_lock(text: str) -> set[str]:
    data = tomllib.loads(text)
    return {str(p.get("name", "")).lower().replace("_", "-") for p in data.get("package", [])}


def _imports_in(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = IMPORT_RX.match(line)
        if not m:
            continue
        names = [m.group(1)] if m.group(1) else [n.strip() for n in m.group(2).split(",")]
        for name in names:
            found.append((lineno, name.split(".")[0]))
    return found


def check_dependencies(pyproject_text: str, lock_text: str | None) -> list[str]:
    findings: list[str] = []
    for name in sorted(_dependency_names_from_pyproject(pyproject_text) & FORBIDDEN_PACKAGES):
        findings.append(f"pyproject.toml: forbidden dependency '{name}' (scans, probes or logs in to hosts)")
    if lock_text is not None:
        for name in sorted(_package_names_from_lock(lock_text) & FORBIDDEN_PACKAGES):
            findings.append(f"uv.lock: forbidden package '{name}' pulled in (directly or transitively)")
    return findings


def check_source_file(rel: str, text: str) -> list[str]:
    return [
        f"{rel}:{lineno}: forbidden import '{module}' (no sockets, shell-outs or host sessions in the package)"
        for lineno, module in _imports_in(text)
        if module in FORBIDDEN_MODULES
    ]


def check_registry_schemes(rel: str, text: str) -> list[str]:
    return [
        f"{rel}: source scheme '{scheme}' is not a document store; allowed: {sorted(ALLOWED_SOURCE_SCHEMES)}"
        for scheme in SCHEME_RX.findall(text)
        if scheme not in ALLOWED_SOURCE_SCHEMES
    ]


def check_image(rel: str, text: str) -> list[str]:
    findings: list[str] = []
    for m in APT_RX.finditer(text):
        for token in re.findall(r"[A-Za-z0-9.+\-]+", m.group(1)):
            if token in FORBIDDEN_IMAGE_TOOLS:
                findings.append(f"{rel}: network tool '{token}' installed into the runtime image")
    return findings


def main() -> int:
    findings: list[str] = []
    lock = ROOT / "uv.lock"
    findings += check_dependencies((ROOT / "pyproject.toml").read_text(), lock.read_text() if lock.exists() else None)
    for path in sorted((ROOT / "src" / "readiness").rglob("*.py")):
        findings += check_source_file(path.relative_to(ROOT).as_posix(), path.read_text(errors="ignore"))
    registry = ROOT / "src" / "readiness" / "adapters" / "registry.py"
    findings += check_registry_schemes(registry.relative_to(ROOT).as_posix(), registry.read_text())
    for image in sorted(ROOT.glob("Dockerfile*")):
        findings += check_image(image.name, image.read_text(errors="ignore"))
    if findings:
        print("System-access check FAILED. The assessor reads documents, never systems (see ADR-20261103):")
        print("\n".join(findings))
        return 1
    print("system-access check: ok (no scanning, remote-access or host-session capability)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
