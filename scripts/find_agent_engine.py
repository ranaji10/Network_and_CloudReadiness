"""Print the id of the newest Agent Runtime (reasoning engine) instance with a given display name, or
nothing if none exists. Used by cloudbuild.yaml so a build never creates a duplicate instance when
`_AGENT_ENGINE_ID` is not pinned yet.

Usage: uv run python scripts/find_agent_engine.py --project <id> --region <region> --display-name <name>"""

from __future__ import annotations

import argparse
import sys


def pick(engines: list[dict], display_name: str) -> str:
    """Newest matching instance id, or '' when there is none."""
    matches = [e for e in engines if e.get("displayName") == display_name and e.get("name")]
    if not matches:
        return ""
    newest = max(matches, key=lambda e: e.get("createTime", ""))
    return newest["name"].rsplit("/", 1)[1]


def list_engines(project: str, region: str) -> list[dict]:
    import google.auth
    import google.auth.transport.requests
    import httpx

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())
    url = f"https://{region}-aiplatform.googleapis.com/v1/projects/{project}/locations/{region}/reasoningEngines"
    out: list[dict] = []
    token = None
    while True:
        params = {"pageSize": 100, **({"pageToken": token} if token else {})}
        r = httpx.get(url, headers={"Authorization": f"Bearer {creds.token}"}, params=params, timeout=60)
        r.raise_for_status()
        body = r.json()
        out.extend(body.get("reasoningEngines", []))
        token = body.get("nextPageToken")
        if not token:
            return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--region", required=True)
    ap.add_argument("--display-name", required=True)
    a = ap.parse_args()
    print(pick(list_engines(a.project, a.region), a.display_name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
