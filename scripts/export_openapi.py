"""Export the HTTP API schema to docs/api/openapi.json so the contract is versioned with the code.

Usage: uv run python scripts/export_openapi.py          # write
       uv run python scripts/export_openapi.py --check  # exit 1 if the committed file is stale"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "api" / "openapi.json"


def render() -> str:
    from readiness.api.app import app

    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != content:
            print("docs/api/openapi.json is stale: run `make openapi`")
            return 1
        print("openapi export up to date")
        return 0
    OUT.write_text(content)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
