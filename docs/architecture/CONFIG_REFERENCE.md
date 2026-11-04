# Configuration reference

Field-by-field reference for the YAML under `config/`. Values are validated by the pydantic models in
`src/readiness/scoring/profiles.py`, `src/readiness/recommend/engine.py` and `src/readiness/recommend/waves.py`;
an unknown field or a wrong type fails at load time. `config/README.md` is the short orientation; this page is the contract.

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
| `pillar_weight_overrides` | map of `{domain_id: {pillar_id: number}}` | `{}` | Replaces the `weight` of the named pillars for this profile only; unlisted pillars keep the domain's weight |
| `migration_waves` | boolean | `false` | Derive migration waves from inventory documents with `recommendations/waves.yaml` and add them to the report (`gcp_migration` sets it) |

`pillar_weight_overrides` is validated at load time: every domain id must appear in `domains`, every
pillar id must exist in that domain's `scoring/<id>.yaml`, and every weight must be greater than zero.
`readiness.scoring.profiles.load_domains` applies the overrides to the loaded `DomainDef`s, so the
domain score, coverage, recommendation priority (`base` below) and the pillar weight printed in the
report all use the overridden value. The domain file on disk is never changed. The shipped
`healthcare`, `finance` and `public_sector` profiles use this to express their compliance emphasis.

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
| `dedupe_by_product` | boolean | `true` | Merge actions whose preferred option shares a product family into one action listing every check it closes (see *Product-family merge*) |

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
`operations`, `questionnaire`. Documents classified `irrelevant` or with empty text are never searched.
`questionnaire` is assigned by the pipeline to stored questionnaire answers (`readiness answer`,
`POST /assessments/{id}/answers`); such documents are searched by every check regardless of its
`doc_classes`, and only their answer text is scored.

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

With the LLM judge enabled, each pillar is sent to the model with all its check questions and a selection
of the redacted documents. A verdict replaces the rule result only when its confidence is at least
`llm_override_min_confidence` and its status is not `unknown`; points are recomputed from the new status.

### What the judge sees (environment settings, LLM-06)

| Setting | Default | Meaning |
|---|---|---|
| `READINESS_JUDGE_MAX_DOCS_PER_PILLAR` | `8` | Documents sent per pillar: the best-ranked by the number of distinct signal hits for that pillar's checks (weak, strong and negative signals, each check on its own `doc_classes` pool; ties broken by document name, then id). Documents with no hit for the pillar are never sent. `0` sends every relevant document in source order (the behaviour before LLM-06). |
| `READINESS_JUDGE_BATCH_CHARS` | `60000` | Evidence characters per call. The selected documents each get an even share, never less than 2,000 characters; when they still do not fit (only possible with pre-selection off or a very small budget) the pillar goes out in several calls and the verdicts are merged, a non-`unknown` verdict beating `unknown`, then the more confident one. |
| `READINESS_LLM_PROMPT_CACHING` | `true` | Mark the static prompt prefix as cacheable where the provider SDK supports it (Anthropic `cache_control: ephemeral` on the system block; Gemini has no equivalent wired, see the adapter docstring). No effect on the mock. |

Every judge call is laid out as a system prompt (`JUDGE_SYSTEM`, the pillar's check list, the untrusted-data
preamble) that contains no document text and is byte-identical for every batch of a pillar and every run,
followed by the user turn with the `<document>` blocks. The selection is deterministic: the same pack and
configuration always send the same documents in the same order. On a 100-document synthetic pack the
default settings cut the judge's input tokens by about 86% against pre-selection off (see
`tests/test_judge_preselection.py`), with the mock returning no verdicts so no score moves.

`report.extra["llm_usage"]` and the `run.end` audit event carry `cache_creation_input_tokens` and
`cache_read_input_tokens` next to `input_tokens` (0 for providers without a cache); the cost estimate charges
cached tokens at the full input price, so it remains an upper bound.

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

Option fields:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `provider` | `gcp`, `aws`, `oss` or `process` | required | Decides ordering and filtering by the profile's `target_providers` |
| `product` | string | required | Product or practice named in the report |
| `url` | string or null | `null` | Official documentation landing page; **required (`https://`) for `gcp`, `aws` and `oss`**. For `process` the most relevant public reference (CSA CCM / STAR, NIST SP 800-xx, NIST AI RMF, CIS Controls, FinOps Framework); `null` only when nothing authoritative fits, and the note must then say "no authoritative reference" |
| `note` | string | required by test | At most 220 characters, neutral, no prices: a sizing hint ("fits up to ...", "needs a team that ...") followed by a sentence starting with `Wrong when` that names the situation in which the option is the wrong choice |
| `family` | string | `""` | Short tag such as `cloud-identity` shared by options that are the same product rollout; see *Product-family merge* |

`test_every_catalog_option_has_docs_link_and_limitation_note` enforces the `url` and `note` rules. The Markdown
report renders the product as `[product](url)` followed by the note; the PDF prints the url in parentheses after
the product on the same line.

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

### Product-family merge

With `rules.dedupe_by_product: true` (the default), actions are grouped before sorting by the *family
key* of their preferred option, the first option left after provider-preference ordering and filtering:

`family key` = `<provider>:<family>`, where `family` is the option's `family` tag lower-cased, or, when
the tag is empty, the `product` text lower-cased with whitespace collapsed.

Each group becomes one action. The member with the highest priority is the *lead* and provides the
`id` (`A-<lead check id>`), `check_id`, title, rationale and options; the merged record has:

- `priority` = sum of the members' priorities (one rollout closes all of them)
- `effort` = the largest member effort (`L` > `M` > `S`), `impact` = the largest member impact
- `ccm_controls` = union in first-seen order
- `closes_check_ids` / `closes_titles` = every member's check id and title, lead first

Every action, merged or not, carries `closes_check_ids` (a single-member action lists its own check) and
`family`; the Markdown report prints them as a `Closes:` line under the action. Discovery items are never
merged, actions without options (catalog-less checks or `process`-only entries whose provider was
filtered out) are never merged, and `max_recommendations` is applied after merging.

Example (default profile, `gcp` first, a pillar of weight 25 in `network_security`): NS-IAM-01 NOT_MET
losing 5 points has priority 5 × 25 × 40 / 100 × 1.5 × 1.0 = 75; NS-IAM-02 PARTIAL losing 2 points has
priority 20 × 1.5 × 1.2 = 36. Both prefer a `gcp` option tagged `cloud-identity`, so the report shows one
action "Consolidate on a central identity provider with SSO" with priority 111 and
`Closes: NS-IAM-01 ..., NS-IAM-02 ...`. With the rule off they are two separate actions.

## Migration waves (`config/recommendations/waves.yaml`)

Read only when the profile sets `migration_waves: true`. Validated by `readiness.recommend.waves.WaveConfig`.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `version` | string | `"1"` | Informational |
| `default_wave` | string | required | Wave id for rows that match no signal; must be one of the wave ids |
| `max_rows_per_wave` | integer | `25` | Rows listed per wave in `report.json` and `report.md`; `count` is always the full number |
| `header_cells` | list of string | `[]` | Lower-case first-cell values that mark a header row (`hostname`, `name`, ...) |
| `waves` | list of wave | required | At least one; ids must be unique |

Wave fields: `id` (string), `name` (string, report heading), `order` (integer, report order and precedence),
`description` (string, printed under the heading), `signals` (list of string, at least one, same syntax as
check signals; an invalid regular expression fails at load).

### How rows are placed

1. Only documents classified `inventory` (keyword or LLM classifier) with non-empty text are read, after redaction.
2. Each line is a row. Blank lines, `## sheet:` markers from XLSX extraction, Markdown table rules and lines
   without a letter are skipped. Cells are split on `,`, `|`, tab and `;`; the system label is the first cell,
   or the first word when the line has a single cell, cut at 60 characters.
3. A row is a header when its first cell is in `header_cells`, or when it is the first row of the document and
   contains no digit.
4. The same label twice in one document counts once.
5. Waves are tested in descending `order`; the first wave with a matching signal takes the row and the first
   matching signal in that wave's list is the `reason`. No match: `default_wave` with the reason
   `no signal matched (default wave)`.

Output: `AssessmentReport.migration_waves` (`MigrationWavePlan`: `waves[]` with `id`, `name`, `order`,
`description`, `count`, `systems[]` of `{system, reason, source_doc}`, plus `inventory_documents`,
`total_systems`, `default_wave`, `max_rows_per_wave`). It is `null` when the profile has the switch off. When
the switch is on but no inventory document exists, `inventory_documents` is empty, the report carries a
warning and the Markdown shows a one-line note instead of the section.

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

`READINESS_SHARE_SAFE=true` (per run: `readiness assess --share-safe`, API `share_safe=true`) overrides the
mode with `mask`, switches snippets off and replaces document names in the report with `doc-<hash>` labels;
see `docs/security/DATA_HANDLING_POLICY.md`, "Sharing a report outside the tenant".

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

## Evaluation packs and score drift

`tests/evals/packs/` holds 20 synthetic document packs, each with an `expected.yaml` that pins the composite
score, the composite coverage and every domain's score and coverage for the configuration as committed, in
rules-only mode and with the (mock) LLM judge. `tests/evals/test_evals.py` runs them as part of `make test`;
a value outside the pack's tolerance (1.0 point by default) or a changed designed check status fails CI.

Changing scoring configuration therefore has one extra step: run `make evals`; if the drift is what you
intended, run `make evals-refresh` and review the diff of the `expected.yaml` files like a snapshot. The
packs and the refresh workflow are documented in `tests/evals/packs/README.md`.

## OCR for scanned documents (environment settings)

Scanned PDFs and raster images (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`) are read with the `ocr` extra
(pypdfium2, pytesseract, Pillow) and the `tesseract-ocr` binary, both installed in the container image. OCR
runs inside the process with the local binary; no page image or text leaves the machine. These are
`READINESS_*` environment settings (`src/readiness/config.py`), not YAML:

| Setting | Default | Meaning |
|---|---|---|
| `READINESS_OCR_ENABLED` | `true` | `false` leaves scanned PDF pages empty and reports image files as unreadable (an extraction warning, never a failure) |
| `READINESS_OCR_MIN_CHARS_PER_PAGE` | `20` | A PDF page on which `pypdf` finds fewer characters is treated as scanned and OCR'd; text PDFs never touch OCR |
| `READINESS_OCR_MAX_PAGES` | `50` | OCR budget per document; pages or image frames beyond it are skipped and the document is marked `truncated` |
| `READINESS_OCR_DPI` | `200` | Render resolution for PDF pages before OCR |
| `READINESS_OCR_LANGUAGES` | `eng` | Tesseract language codes joined with `+` (`eng+deu`); each needs its `tesseract-ocr-<lang>` package |

When the extra or the binary is missing, a scanned document gets an extraction error that names the install
step (`install the ocr extra ... and the tesseract-ocr binary`), the text `pypdf` did find is kept, the run
continues and the report lists the document under warnings. The audit log records `ocr_pages` per document
(a count, never content).

## What is not configurable (requires a code change)

- the confidence values attached to rule verdicts (0.6, 0.7, 0.5, 0.3) and the evidence cap of eight hits
- the snippet window (80 characters) and the rule that decides whether a signal is a regex
- the document classifier's keywords, weights and threshold (`src/readiness/ingestion/classify.py`)
- the impact and effort weight tables, the 0.5 discovery factor, the six-question cap and the way merged
  actions combine priority (sum), effort and impact (maximum)
- the LLM judge prompt, the 2,000-character floor per selected document and the ranking rule for pre-selection
  (the document count and the character budget per call are environment settings, see *What the judge sees*)
- the composite being a weighted mean, the grade letters, and the report layout
- supported file types and extraction behaviour (`src/readiness/ingestion/extract.py`)
- runtime limits such as `READINESS_MAX_DOC_BYTES`, `READINESS_MAX_TEXT_CHARS` and the `READINESS_OCR_*` switches above, which are environment settings, not YAML
