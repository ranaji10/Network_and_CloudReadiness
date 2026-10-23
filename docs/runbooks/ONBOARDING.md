# Runbook: onboarding (first day for an engineer or an agent)

## Read, in this order (about an hour)

1. `README.md`
2. `docs/product/VISION.md` and `docs/product/ROADMAP.md`
3. `docs/planning/README.md` and `docs/planning/TRACKER.md`
4. `docs/collaboration/WORKING_AGREEMENT.md`
5. `docs/architecture/OVERVIEW.md`, `DATA_FLOW.md`
6. `docs/security/GUARDRAILS.md` and `DATA_HANDLING_POLICY.md`
7. `CLAUDE.md` (the same rules apply to people)
8. `docs/legacy/V1_SUMMARY.md` for where this came from

## Do

```bash
uv sync --group dev
make demo            # read the report; this is the product
make check           # must be green before you touch anything
uv run readiness checks network_security
```

Open `config/scoring/network_security.yaml` next to the report and trace one check from signal to score to
recommendation. That is most of the system.

## Pick a story

In `docs/planning/TRACKER.md` find a `todo` story with no open dependencies, preferably one labelled
good-first in its notes. Claim it per the working agreement (edit YAML, `make tracker`, commit, push), branch,
work, open a PR with the template.

## Ask

Questions about the product: the product owner (see `docs/collaboration/OWNERSHIP.md`). About
infrastructure or credentials: the infra owner. Never ask for or share client data to understand the system;
the synthetic fixtures are enough.
