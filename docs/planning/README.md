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
Story DOC-06 adds an optional sync to GitHub Issues for people who prefer that view.
