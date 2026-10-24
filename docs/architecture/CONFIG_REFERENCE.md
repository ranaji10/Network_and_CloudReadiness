# Configuration reference

Field-by-field reference for the YAML under `config/`. Values are validated by the pydantic models in
`src/readiness/scoring/profiles.py` and `src/readiness/recommend/engine.py`; an unknown field or a wrong
type fails at load time. `config/README.md` is the short orientation; this page is the contract.

## Where configuration is loaded from

`readiness.config.resolve_default_config_dir` picks the first directory that contains a `profiles/` folder:

| Order | Location | Case |
|---|---|---|
| 0 | `READINESS_CONFIG_DIR` | explicit override (Docker image sets it to `/app/config`) |
| 1 | `<repo>/config` | checkout, developer machine, Cloud Run image |
| 2 | `<parent of the package>/config` | Agent Runtime bundle: `/app/readiness` next to `/app/config` |
| 3 | `readiness/_bundled_config` | wheel installed with `pip`; copy force-included at build time |

Profiles, domains, the catalog and `redaction.yaml` are all read from that one directory
(`Settings.config_dir`). The CSA CCM catalog is package data (`src/readiness/data/ccm_v4.1.json`), not config.

## Profile (`config/profiles/<id>.yaml`)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | required | Selected with `--profile`; should equal the file name |
| `name` | string | required | Shown in `readiness profiles` and the API |
| `version` | string | `"1"` | Printed in the report header as `profile_version` |
| `description` | string | `""` | Informational |
| `domains` | list of `{id, weight}` | required | Which `scoring/<id>.yaml` files to run and their relative weights |
| `thresholds` | map of number | see below | Grade boundaries and the confidence gate |
| `rules` | object | see below | Signal evaluation rules |
| `target_providers` | list of string | `[gcp, aws, oss]` | Preference order for recommendation options; providers not listed are dropped, `process` is always kept and listed last |
| `max_recommendations` | integer | `40` | Truncates the prioritised list (actions and discovery items together) |

`thresholds` defaults: `high_confidence_coverage: 70`, `grade_a: 85`, `grade_b: 70`, `grade_c: 50`.
Grades use `>=`: A at or above `grade_a`, B at or above `grade_b`, C at or above `grade_c`, else D.
`high_confidence_coverage` is used by the report and the web UI only, to decide whether to show the
"collect more evidence first" warning; it does not change any score.

`rules` fields:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `met_min_signals` | integer | `2` | Distinct weak signals needed for MET when no strong signal matched |
| `partial_points_ratio` | number | `0.5` | Share of a check's points awarded for PARTIAL |
| `negative_overrides` | boolean | `true` | A negative signal match forces NOT_MET |
| `llm_override_min_confidence` | number | `0.6` | Minimum confidence for an LLM verdict to replace the rule verdict |

## Domain (`config/scoring/<id>.yaml`)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | required | Referenced from profiles |
| `name` | string | required | Report heading |
| `version` | string | `"1"` | Informational |
| `description` | string | `""` | Informational |
| `pillars` | list of pillar | required | At least one |

Check ids must be unique across the whole domain; duplicates fail validation.

### Pillar

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | required | Used in results and recommendation records |
| `name` | string | required | Report heading |
| `weight` | number | required | Relative weight inside the domain; tests require it to be positive |
| `description` | string | `""` | Informational |
| `checks` | list of check | required | |

The pillar maximum is the sum of its checks' `points`; it is never written in the file.

### Check

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | required | Prefix by domain: `NS-`, `CR-`, `AI-`; must have a catalog entry |
| `title` | string | required | Shown in the report |
| `points` | number | `5` | Awarded in full for MET, times `partial_points_ratio` for PARTIAL, else 0 |
| `ccm` | list of string | `[]` | CSA CCM v4.1 control ids; each must exist in the catalog; their CAIQ questions become discovery questions |
| `signals` | list of string | `[]` | Weak evidence; each distinct entry that matches counts once |
| `strong_signals` | list of string | `[]` | One match is MET on its own; also counts as a distinct signal |
| `negative_signals` | list of string | `[]` | A match is NOT_MET when `negative_overrides` is true; recorded in evidence as `NEGATIVE:<signal>` |
| `doc_classes` | list of string | `[]` | Restrict the search to documents of these classes; falls back to all relevant documents when none match |
| `question` | string | `""` | Question for the LLM judge; the title is used when empty |
| `tags` | list of string | `[]` | Free-form, unused by the engine |

Valid `doc_classes` values are the `DocClass` enum: `architecture`, `network`, `security_policy`,
`compliance_audit`, `inventory`, `data_storage`, `identity`, `backup_dr`, `contract_license`, `ai_ml`,
`operations`. Documents classified `irrelevant` or with empty text are never searched.

### Signal matching

A signal containing any of the characters `\ [ ] ( ) . * + ? |` is compiled as a regular expression.
Any other signal is matched as `\b<escaped text>\b`. Both are case-insensitive and search the whole
redacted text of each document. Evidence is capped at eight hits per check and snippets (80 characters
each side of the match) are included only when `READINESS_INCLUDE_EVIDENCE_SNIPPETS=true` or `--snippets`.

### Status rules (in this order)

| Condition | Status | Confidence recorded |
|---|---|---|
| Any negative signal matched and `negative_overrides` is true | NOT_MET | 0.6 |
| Any strong signal matched, or distinct matched signals >= `met_min_signals` | MET | 0.7 |
| At least one distinct signal matched | PARTIAL | 0.5 |
| Nothing matched | UNKNOWN | 0.3 |

With the LLM judge enabled, each pillar is sent once to the model with all its check questions and the
redacted documents (about 60,000 characters of evidence split evenly across documents, at least 2,000
per document). A verdict replaces the rule result only when its confidence is at least
`llm_override_min_confidence` and its status is not `unknown`; points are recomputed from the new status.

## Scoring math

Per pillar:

- `points` = sum of awarded check points; `max_points` = sum of check `points`
- `ratio` = `points / max_points`
- `coverage` = checks with status other than UNKNOWN divided by number of checks (unweighted)

Per domain:

- `score` = 100 × Σ(pillar weight × pillar ratio) / Σ(pillar weight), rounded to one decimal
- `coverage` = 100 × Σ(pillar weight × pillar coverage) / Σ(pillar weight)
- `grade` from `thresholds`

Overall:

- `overall_score` = Σ(domain weight × domain score) / Σ(domain weight)
- `overall_coverage` = Σ(domain weight × domain coverage) / Σ(domain weight)

Numeric example with the default profile and the `perimeter` pillar of `network_security` (weight 25,
checks worth 5, 5, 4, 4):

| Check | Status | Points |
|---|---|---|
| NS-PER-01 | MET | 5 |
| NS-PER-02 | UNKNOWN | 0 |
| NS-PER-03 | PARTIAL | 4 × 0.5 = 2 |
| NS-PER-04 | MET | 4 |

Pillar ratio = 11 / 18 = 0.611, pillar coverage = 3 / 4 = 0.75. If a second pillar of weight 25 scored
1.0, the domain score would be 100 × (25 × 0.611 + 25 × 1.0) / 50 = 80.6, grade B. With domain weights
40 / 35 / 25 and the other two domains at 40, the overall score is (40 × 80.6 + 35 × 40 + 25 × 40) / 100 = 56.2.

## Recommendation catalog (`config/recommendations/catalog.yaml`)

Top level: `version` (string, informational) and `recommendations` (list). One entry per check:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `check_id` | string | required | Must match a check id; a check without an entry fails the tests |
| `title` | string | required | Action title in the report |
| `rationale` | string | `""` | One or two sentences on why it matters |
| `effort` | `S`, `M` or `L` | `M` | Relative effort |
| `impact` | `high`, `medium` or `low` | `medium` | Relative impact |
| `options` | list of option | `[]` | Product choices, ordered by the profile's `target_providers` |

Option fields: `provider` (`gcp`, `aws`, `oss` or `process`), `product` (string), `note` (string,
default empty), `url` (string or null).

### What the engine produces

| Check status | Record | Content |
|---|---|---|
| MET | nothing | |
| PARTIAL or NOT_MET | action `A-<check id>` | Catalog title, rationale, effort, impact, filtered and ordered options |
| UNKNOWN | discovery `D-<check id>` | "Provide evidence for: <title>", up to six CAIQ questions from the check's CCM controls, effort `S`, impact `medium` |

### Priority math

`base` = lost points × pillar weight × domain weight / 100, where lost points = check `points` minus
awarded points.

- action priority = `base` × impact weight × effort weight, with impact weights `high 1.5`, `medium 1.0`,
  `low 0.6` and effort weights `S 1.2`, `M 1.0`, `L 0.8` (unknown values count as 1.0)
- discovery priority = `base` × 0.5

Example (default profile, `network_security` weight 40, `perimeter` weight 25): NS-PER-02 UNKNOWN loses
5 points, so base = 5 × 25 × 40 / 100 = 50 and the discovery item has priority 25. NS-PER-03 PARTIAL
loses 2 points, base = 20; its catalog entry is effort `M`, impact `medium`, so the action has priority 20.
The list is sorted by priority descending, then id, and cut at `max_recommendations`.

## Redaction rules (`config/redaction.yaml`)

Top level: `version` and `rules` (list, applied in file order). Rule fields:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | required | Key in the redaction summary counts |
| `kind` | `secret`, `pii` or `identifier` | required | Decides the mode behaviour below |
| `pattern` | string | required | Python regular expression, compiled with `re.I` and `re.M` |
| `placeholder` | string | `name` | Text inside the replacement token |

Mode behaviour (`READINESS_REDACTION_MODE`):

| Mode | `secret` rules | `pii` and `identifier` rules |
|---|---|---|
| `off` | masked as `[REDACTED:<placeholder>]` | not applied |
| `mask` | masked | masked as `[REDACTED:<placeholder>]` |
| `pseudonymize` (default) | masked | replaced by `<placeholder-NN>`, numbered per placeholder in order of first appearance and stable for the run |

Redaction runs on every document before scoring, so signals, snippets, reports and any model prompt
see redacted text. In `pseudonymize` mode with `READINESS_PROVIDER=local`, the token-to-original mapping
is written to `pseudonym_mapping.local.json` in the run folder and nowhere else. Counts per rule appear in
the report's data-handling section.

## LLM pricing (`config/llm_pricing.yaml`)

Used only to estimate the cost shown in reports and audit events; it never affects scoring or egress.

| Field | Type | Meaning |
|---|---|---|
| `models.<model id>.input_per_million_usd` | number | List price per million input tokens |
| `models.<model id>.output_per_million_usd` | number | List price per million output tokens |
| `models.<model id>.currency` | string | Always `USD` for now |
| `models.<model id>.as_of` | date | When the price was last checked |

Estimate = `input_tokens * input_price / 1e6 + output_tokens * output_price / 1e6`, rounded to six decimals.
A model with no entry yields `estimated_cost_usd: null` rather than an error, so add entries as you adopt
models. Cached-input, batch and long-context tiers are not modelled; treat the figure as an upper bound at
list price.

## What is not configurable (requires a code change)

- the confidence values attached to rule verdicts (0.6, 0.7, 0.5, 0.3) and the evidence cap of eight hits
- the snippet window (80 characters) and the rule that decides whether a signal is a regex
- the document classifier's keywords, weights and threshold (`src/readiness/ingestion/classify.py`)
- the impact and effort weight tables, the 0.5 discovery factor and the six-question cap
- the LLM judge prompt, the evidence budget per pillar and the one-call-per-pillar batching
- the composite being a weighted mean, the grade letters, and the report layout
- supported file types and extraction behaviour (`src/readiness/ingestion/extract.py`)
- runtime limits such as `READINESS_MAX_DOC_BYTES` and `READINESS_MAX_TEXT_CHARS`, which are environment settings, not YAML
