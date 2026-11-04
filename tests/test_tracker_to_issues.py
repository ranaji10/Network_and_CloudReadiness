"""scripts/tracker_to_issues.py against an in-memory GitHub behind httpx.MockTransport (no network)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

spec = importlib.util.spec_from_file_location("tracker_to_issues", Path("scripts/tracker_to_issues.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPO = "example-org/example-repo"


class FakeGitHub:
    """Just enough of the Issues and Labels REST API to exercise the script, with a write log."""

    def __init__(self, issues: list[dict[str, Any]] | None = None, labels: set[str] | None = None) -> None:
        self.issues: list[dict[str, Any]] = issues or []
        self.labels: set[str] = labels or set()
        self.writes: list[tuple[str, str, dict[str, Any]]] = []
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path.removeprefix(f"/repos/{REPO}/")
        if request.method == "GET":
            if path == "labels":
                return self._page(request, [{"name": n} for n in sorted(self.labels)])
            if path == "issues":
                assert request.url.params["state"] == "all"
                return self._page(request, self.issues)
        payload = json.loads(request.content) if request.content else {}
        self.writes.append((request.method, path, payload))
        if request.method == "POST" and path == "labels":
            if payload["name"] in self.labels:
                return httpx.Response(422, json={"message": "Validation Failed"})
            self.labels.add(payload["name"])
            return httpx.Response(201, json=payload)
        if request.method == "POST" and path == "issues":
            issue = {
                "number": max((i["number"] for i in self.issues), default=0) + 1,
                "title": payload["title"],
                "body": payload["body"],
                "labels": [{"name": n} for n in payload["labels"]],
                "state": "open",
            }
            self.issues.append(issue)
            return httpx.Response(201, json=issue)
        if request.method == "PATCH" and path.startswith("issues/"):
            number = int(path.rsplit("/", 1)[1])
            issue = next(i for i in self.issues if i["number"] == number)
            for key, value in payload.items():
                if key == "labels":
                    issue["labels"] = [{"name": n} for n in value]
                elif key != "state_reason":
                    issue[key] = value
            return httpx.Response(200, json=issue)
        return httpx.Response(404, json={"message": "Not Found"})

    @staticmethod
    def _page(request: httpx.Request, items: list[dict[str, Any]]) -> httpx.Response:
        per_page = int(request.url.params["per_page"])
        page = int(request.url.params["page"])
        return httpx.Response(200, json=items[(page - 1) * per_page : page * per_page])

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


def _epic(*stories: dict[str, Any]) -> Any:
    base = {"phase": 1, "owner": "", "branch": "", "depends_on": [], "acceptance": "", "notes": ""}
    return mod.Epic(epic="DOC", name="Docs", stories=[{**base, **s} for s in stories])


def _issue(number: int, title: str, body: str, labels: list[str], state: str = "open") -> dict[str, Any]:
    return {"number": number, "title": title, "body": body, "labels": [{"name": n} for n in labels], "state": state}


STORY_TODO = {
    "id": "DOC-06",
    "title": "Tracker sync",
    "status": "todo",
    "owner": "claude-code",
    "depends_on": ["DOC-01"],
}


def test_create_path_makes_labels_and_issue() -> None:
    gh = FakeGitHub(labels={"epic:DOC"})
    epic = _epic({**STORY_TODO, "acceptance": "script exists", "branch": "feat/DOC-06-sync", "notes": "optional"})
    result = mod.sync([epic], mod.GitHubClient(REPO, "secret-token", client=gh.client()))

    assert [str(c) for c in result.changes] == ["DOC-06: create #1"]
    assert result.new_labels == ["phase:1", "status:todo"]
    assert [(m, p) for m, p, _ in gh.writes] == [("POST", "labels"), ("POST", "labels"), ("POST", "issues")]
    issue = gh.issues[0]
    assert issue["title"] == "DOC-06: Tracker sync"
    assert {lab["name"] for lab in issue["labels"]} == {"epic:DOC", "phase:1", "status:todo"}
    body = issue["body"]
    for expected in (
        "**Status:** `todo`",
        "**Phase:** 1",
        "**Owner:** claude-code",
        "**Branch:** `feat/DOC-06-sync`",
        "**Depends on:** DOC-01",
        "script exists",
        "optional",
        "docs/planning/tracker/DOC.yaml",
        "Source of truth",
    ):
        assert expected in body, expected
    auth = {r.headers.get("Authorization") for r in gh.requests}
    assert auth == {"Bearer secret-token"}


def test_update_path_patches_only_changed_fields() -> None:
    epic = _epic(STORY_TODO)
    desired = mod.desired_for(epic, epic.stories[0])
    stale = _issue(7, "DOC-06: Old title", desired.body, ["epic:DOC", "phase:1", "status:todo"])
    gh = FakeGitHub(issues=[stale], labels=set(desired.labels))

    result = mod.sync([epic], mod.GitHubClient(REPO, "t", client=gh.client()))

    assert [str(c) for c in result.changes] == ["DOC-06: update #7 [title]"]
    assert gh.writes == [("PATCH", "issues/7", {"title": "DOC-06: Tracker sync"})]


def test_noop_when_issue_already_matches() -> None:
    epic = _epic(STORY_TODO)
    desired = mod.desired_for(epic, epic.stories[0])
    # GitHub may hand the body back with CRLF line endings; that must not count as a change.
    same = _issue(3, desired.title, desired.body.replace("\n", "\r\n") + "\n", list(desired.labels))
    gh = FakeGitHub(issues=[same], labels=set(desired.labels))

    result = mod.sync([epic], mod.GitHubClient(REPO, "t", client=gh.client()))

    assert [str(c) for c in result.changes] == ["DOC-06: unchanged #3"]
    assert result.writes == []
    assert gh.writes == []


def test_done_story_closes_issue_and_reopens_when_not_done() -> None:
    done = _epic({**STORY_TODO, "status": "done"})
    desired = mod.desired_for(done, done.stories[0])
    open_issue = _issue(5, desired.title, desired.body, list(desired.labels), state="open")
    gh = FakeGitHub(issues=[open_issue], labels=set(desired.labels))

    result = mod.sync([done], mod.GitHubClient(REPO, "t", client=gh.client()))
    assert [str(c) for c in result.changes] == ["DOC-06: update #5 [state]"]
    assert gh.writes == [("PATCH", "issues/5", {"state": "closed", "state_reason": "completed"})]
    assert gh.issues[0]["state"] == "closed"

    # Flip the YAML back to in_progress: the issue is reopened and relabelled.
    again = _epic({**STORY_TODO, "status": "in_progress"})
    gh.writes.clear()
    result = mod.sync([again], mod.GitHubClient(REPO, "t", client=gh.client()))
    assert [str(c) for c in result.changes] == ["DOC-06: update #5 [body, labels, state]"]
    method, path, payload = gh.writes[-1]
    assert (method, path) == ("PATCH", "issues/5")
    assert payload["state"] == "open" and payload["state_reason"] == "reopened"
    assert "status:in_progress" in payload["labels"]


def test_done_story_created_closed() -> None:
    done = _epic({**STORY_TODO, "status": "done"})
    gh = FakeGitHub(labels={"epic:DOC", "phase:1", "status:done"})
    result = mod.sync([done], mod.GitHubClient(REPO, "t", client=gh.client()))
    assert [str(c) for c in result.changes] == ["DOC-06: create #1 [state]"]
    assert [(m, p) for m, p, _ in gh.writes] == [("POST", "issues"), ("PATCH", "issues/1")]
    assert gh.issues[0]["state"] == "closed"


def test_dry_run_reads_but_never_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "DOC.yaml").write_text(
        "epic: DOC\nname: Docs\nstories:\n"
        "  - {id: DOC-01, title: Vision, status: done, phase: 0}\n"
        "  - {id: DOC-06, title: Tracker sync, status: todo, phase: 1}\n"
    )
    gh = FakeGitHub(issues=[_issue(2, "DOC-01: Vision", "stale", ["epic:DOC"], state="open")])
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    rc = mod.main(["--dry-run", "--repo", REPO, "--tracker-dir", str(tmp_path)], client=gh.client())

    assert rc == 0
    assert gh.writes == []
    assert all(r.method == "GET" for r in gh.requests)
    out = capsys.readouterr().out
    assert "dry run" in out
    assert "would create phase:0" in out
    assert "would DOC-01: update #2 [body, labels, state]" in out
    assert "would DOC-06: create" in out
    assert "2 stories, 2 to change" in out


def test_main_requires_token_unless_dry_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert mod.main(["--repo", REPO]) == 2
    assert "GITHUB_TOKEN" in capsys.readouterr().err
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert mod.main(["--dry-run"]) == 2
    assert "GITHUB_REPOSITORY" in capsys.readouterr().err


def test_only_limits_and_rejects_unknown_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    gh = FakeGitHub()
    assert mod.main(["--dry-run", "--repo", REPO, "--only", "NOPE-99"], client=gh.client()) == 2
    assert gh.requests == []
    assert mod.main(["--dry-run", "--repo", REPO, "--only", "DOC-06"], client=gh.client()) == 0


def test_pagination_and_pull_requests_skipped() -> None:
    issues = [_issue(n, f"X-{n}: thing", "", []) for n in range(1, mod.PER_PAGE + 2)]
    issues.append({**_issue(999, "DOC-06: Tracker sync", "", []), "pull_request": {"url": "pr"}})
    gh = FakeGitHub(issues=issues)
    found = mod.GitHubClient(REPO, None, client=gh.client()).list_issues()
    assert len(found) == mod.PER_PAGE + 1
    assert all("pull_request" not in i for i in found)
    assert sum(1 for r in gh.requests if r.url.path.endswith("/issues")) == 2


def test_duplicate_titles_use_lowest_number() -> None:
    epic = _epic(STORY_TODO)
    desired = mod.desired_for(epic, epic.stories[0])
    gh = FakeGitHub(
        issues=[_issue(9, desired.title, "x", []), _issue(4, desired.title, desired.body, list(desired.labels))],
        labels=set(desired.labels),
    )
    result = mod.sync([epic], mod.GitHubClient(REPO, "t", client=gh.client()))
    assert result.duplicates == {"DOC-06": [4, 9]}
    assert [str(c) for c in result.changes] == ["DOC-06: unchanged #4"]


def test_real_tracker_loads_and_every_story_gets_a_desired_issue() -> None:
    epics = mod.load_epics()
    ids = [s.id for e in epics for s in e.stories]
    assert "DOC-06" in ids
    for e in epics:
        for s in e.stories:
            d = mod.desired_for(e, s)
            assert mod.STORY_PREFIX.match(d.title).group(1) == s.id
            assert d.state == ("closed" if s.status == "done" else "open")
