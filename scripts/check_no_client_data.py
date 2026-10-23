"""Fail if anything that looks like client material is about to be committed.

Rules:
1. Directories that hold assessment inputs/outputs (data/, workspace/, uploads/, reports/) must not be tracked.
2. Sample / fixture folders must carry a README that declares the content SYNTHETIC.
3. No file larger than 10 MB outside reference/ and legacy/ (real client doc dumps are big; configs are not).
4. No pseudonym mapping files, .env files, key files or terraform variable files anywhere in the index.

Usage: uv run python scripts/check_no_client_data.py"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_DIRS = ("data/", "workspace/", "uploads/", "reports/")
FORBIDDEN_NAMES = ("pseudonym_mapping", ".env", ".tfvars", ".tfstate", "service-account", "-credentials", "backend.")
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks")
ALLOWED_NAME_SUFFIX = (".example",)
SAMPLE_DIRS = ("samples/", "tests/fixtures/")
MAX_BYTES = 10 * 1024 * 1024
BIG_OK_PREFIXES = ("reference/", "legacy/")


def tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [f for f in out.split("\0") if f]


def main() -> int:
    problems: list[str] = []
    files = tracked()
    for rel in files:
        if rel.startswith(FORBIDDEN_DIRS):
            problems.append(f"{rel}: assessment data directory must not be committed")
        name = Path(rel).name
        if any(tok in name for tok in FORBIDDEN_NAMES) and not name.endswith(ALLOWED_NAME_SUFFIX):
            problems.append(f"{rel}: looks like a secret / local-only file")
        if name.endswith(FORBIDDEN_SUFFIXES):
            problems.append(f"{rel}: key material must never be committed")
        p = ROOT / rel
        if p.is_file() and not rel.startswith(BIG_OK_PREFIXES) and p.stat().st_size > MAX_BYTES:
            problems.append(f"{rel}: {p.stat().st_size // 1024 // 1024} MB file outside reference/ or legacy/")
    for sample_root in SAMPLE_DIRS:
        depth = len(Path(sample_root).parts)
        subdirs = {Path(f).parts[depth] for f in files if f.startswith(sample_root) and len(Path(f).parts) > depth + 1}
        for sub in subdirs:
            readme = ROOT / sample_root / sub / "README.md"
            if not readme.exists() or "SYNTHETIC" not in readme.read_text(errors="ignore"):
                problems.append(f"{sample_root}{sub}/: needs a README.md stating the content is SYNTHETIC")
    if problems:
        print("Client-data check FAILED:")
        print("\n".join(problems))
        return 1
    print("client-data check: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
