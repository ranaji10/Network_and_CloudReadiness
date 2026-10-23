"""Fail if tracked files contain account-specific identifiers.

Migration between Google accounts / projects / clouds must be an *environment* change, never a code
change. This check keeps project ids, bucket names, e-mails, billing accounts and personal handles out
of version control. Allowed: placeholders (REPLACE-..., <project>, PROJECT_ID) and example files.

Usage: uv run python scripts/check_portability.py  (exit 1 on findings)"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "gcp project id in code",
        re.compile(
            r"\b(?:projects/|--project[= ]|project_id\s*=\s*\")(?!REPLACE|\$|\{|<|PROJECT)[a-z][a-z0-9\-]{5,29}\b"
        ),
    ),
    ("gcs bucket literal", re.compile(r"gs://(?!REPLACE|\$|\{|<|bucket|example)[a-z0-9][a-z0-9\-_.]{2,}")),
    ("s3 bucket literal", re.compile(r"s3://(?!REPLACE|\$|\{|<|bucket|example)[a-z0-9][a-z0-9\-_.]{2,}")),
    ("service account e-mail", re.compile(r"[a-z0-9\-]+@[a-z0-9\-]+\.iam\.gserviceaccount\.com")),
    ("personal e-mail", re.compile(r"\b[A-Za-z0-9._%+\-]+@(?:gmail|googlemail|outlook|hotmail|yahoo)\.com\b")),
    ("billing account id", re.compile(r"\b[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}\b")),
    ("aws account id", re.compile(r"\barn:aws:[a-z0-9\-]+:[a-z0-9\-]*:\d{12}:")),
    ("drive folder id", re.compile(r"drive\.google\.com/drive/folders/(?!<)[A-Za-z0-9_\-]{20,}")),
]

ALLOW_FILES = {"scripts/check_portability.py"}
ALLOW_DIRS = ("legacy/", "reference/", "tests/fixtures/", ".git/")
ALLOW_SUFFIXES = (".example", ".png", ".pdf", ".xlsx", ".docx", ".rtf", ".json")


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ROOT / f for f in out.split("\0") if f]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOW_FILES or rel.startswith(ALLOW_DIRS) or rel.endswith(ALLOW_SUFFIXES) or not path.is_file():
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, rx in PATTERNS:
                if rx.search(line):
                    findings.append(f"{rel}:{lineno}: {label}: {line.strip()[:120]}")
    if findings:
        print("Portability check FAILED. Account-specific identifiers belong in .env / *.tfvars, not in git:")
        print("\n".join(findings))
        return 1
    print("portability check: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
