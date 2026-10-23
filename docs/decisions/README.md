# Architecture decision records

One file per decision, named `ADR-YYYYMMDD-<slug>.md`. The date is the day the decision was taken,
not a sequence number, so two people (or agents) can add decisions on the same day on different
branches without a numbering conflict. If two land on the same day with the same slug, the second
author adds a `-2` suffix.

Template:

```
# <Title>

Status: proposed | accepted | superseded by ADR-...
Date: YYYY-MM-DD

## Context
What situation forced a choice.

## Decision
What we chose, in one or two sentences, then the specifics.

## Consequences
What becomes easier, what becomes harder, what we must now do.
```

Write an ADR when a choice constrains future work: a dependency, a boundary, a data-handling rule,
a process. Do not write one for a bug fix or a naming nit. Supersede rather than edit: an accepted
ADR is history.
