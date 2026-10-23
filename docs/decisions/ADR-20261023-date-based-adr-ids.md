# Date-based ADR identifiers

Status: accepted
Date: 2026-10-23

## Context
Sequential ADR numbers collide when two authors (or agents) open decisions on separate branches.

## Decision
ADR files are named `ADR-YYYYMMDD-<slug>.md`. Same day and slug: add `-2`. Status changes are made
by adding a superseding ADR, not by editing the old one beyond its `Status:` line.

## Consequences
- No numbering coordination needed.
- Ordering is by date; readers browse the folder rather than a numbered index.
