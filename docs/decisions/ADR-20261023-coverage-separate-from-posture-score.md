# Evidence coverage is reported separately from posture score

Status: accepted
Date: 2026-10-23

## Context
V1's single "confidence score" mixed two questions: how much do we know, and how good is it. A thin
folder produced a low number that read as "insecure".

## Decision
Every pillar, domain and the overall result carry two numbers: posture score (points from met and
partial checks) and evidence coverage (share of checks with any evidence). A check with no evidence
is `unknown`, scores zero, and produces a discovery item rather than an action. Profiles keep V1's
70% gate as `high_confidence_coverage`.

## Consequences
- Reports are honest about thin inputs and tell the reader what to collect next.
- Recommendations split cleanly into actions and discovery.
- Two numbers are harder to headline than one; the report leads with both on purpose.
