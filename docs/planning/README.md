# Planning

Three documents, each with one job:

| File | Job | Who edits |
|---|---|---|
| `../product/ROADMAP.md` | why the phases exist and when a phase is finished | product owner |
| `tracker/<EPIC>.yaml` | the live list of stories, their status and owner | anyone, one epic file per PR |
| `TRACKER.md` | generated view of the YAML for people who only read | nobody (run `make tracker`) |

Decisions that change how we build live in `../decisions/` as ADRs (see its README).

## Working the tracker

1. **Pick a story** from `TRACKER.md` in the current phase whose `depends_on` are all `done`.
2. **Claim it first.** On your branch, set `owner` (your name or agent name) and
   `status: in_progress` in the epic YAML, run `make tracker`, and push that as a small first commit.
   Anyone else looking at the branch list or the file sees the claim before you have written code.
3. **One story per pull request.** Branch name `<type>/<STORY-ID>-<slug>`, for example
   `feat/ING-04-gdrive-live`. Put the story id in the PR title.
4. When the acceptance text is met, set `status: done`, clear `branch`, run `make tracker`, and
   include that change in the same PR.
5. If you stop, set `status: blocked` (with `notes` saying why) or back to `todo` with `owner: ""`.

CI runs `python scripts/render_tracker.py --check`; a PR with a hand-edited or stale `TRACKER.md`
fails until you run `make tracker`.

## Adding stories

Add an entry to the epic's YAML with the next free number (`EPIC-NN`). Keep `acceptance` concrete
enough that another person can tell when it is done. Set `phase` according to the roadmap; if a
story does not fit a phase, it probably needs a roadmap conversation first.

Two agents or people adding stories to the same epic at the same time will conflict on that one
file only; resolve by keeping both entries and renumbering the later one.

## Why YAML per epic and not GitHub Issues

The tracker lives in the repository so that any clone, including an agent's sandbox, has the full
plan without network access, and so that a story and the code that closes it ship in one change.
The optional sync below exists for people who prefer the Issues view.

## Optional: mirror the tracker into GitHub Issues

`scripts/tracker_to_issues.py` creates or updates one issue per story. It is **one-way** (YAML to
Issues) and **optional**: nothing in the build depends on it, and edits made on an issue are
overwritten by the next run. The issue title starts with `<STORY-ID>: ` (that prefix is how the
script finds the issue again), the body repeats status, phase, owner, branch, dependencies,
acceptance and notes, and the labels are `epic:<EPIC>`, `phase:<n>` and `status:<status>`
(created when missing). A `done` story closes its issue; any other status reopens it. Issues that
already match are not touched, so re-running is cheap and idempotent.

```sh
make tracker-issues                                   # dry run: prints what would change, writes nothing
GITHUB_TOKEN=<token> GITHUB_REPOSITORY=<owner/repo> \
  uv run python scripts/tracker_to_issues.py          # apply
uv run python scripts/tracker_to_issues.py --repo <owner/repo> --only DOC-06 --dry-run
```

- `GITHUB_TOKEN` needs `issues: write` on the repository (a fine-grained PAT or the Actions token).
  It is required unless `--dry-run`, and it is never printed.
- `GITHUB_REPOSITORY` (`owner/repo`) or `--repo`; `GITHUB_API_URL` for GitHub Enterprise.
  Both variables are set automatically inside GitHub Actions, so a workflow step that runs the
  script after `make tracker` keeps Issues in step with `main`.
- `--only <STORY-ID>` (repeatable) limits the run to a few stories.
