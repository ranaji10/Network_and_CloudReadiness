# SYNTHETIC evaluation packs

Everything under this folder is invented for the SCR-05 evaluation set. Every organisation is fictional and
named so that it cannot be mistaken for a real one, every person is a first name only, every address uses
the documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) or RFC 1918 space, and every
e-mail uses `example.com` / `example.org`. Nothing here comes from a client or from any real assessment.

## Layout

```
packs/<pack_id>/docs/          the documents the pipeline reads (file:// source)
packs/<pack_id>/expected.yaml  design fields (hand-written) + pinned scores (generated)
```

`tests/evals/test_evals.py` runs every pack through `run_assessment` offline, with the mock LLM
(`READINESS_LLM_PROVIDER=mock`, egress disabled), in two modes: rules only and rules + LLM judge. The mock
judge answers conservatively (no verdicts), so both modes currently produce the same numbers; the `judge`
block is only written when they differ. The run takes a few seconds.

## `expected.yaml`

| Field | Written by | Meaning |
|---|---|---|
| `pack`, `description` | hand | Id and the design intent of the pack |
| `profile` | hand | Scoring profile id (`default`, `gcp_migration`, `security_only`) |
| `tolerance` | hand | Absolute points allowed on every pinned score and coverage value (default `1.0`) |
| `tolerances` | hand, optional | Per-value override, e.g. `{overall_score: 2.0, network_security.coverage: 3.0}` |
| `documents` | hand, optional | Number of documents the source must list |
| `document_classes` | hand, optional | File name to expected class (`irrelevant` for noise documents) |
| `warnings_contain` | hand, optional | Fragments that must appear in `report.warnings` |
| `checks` | hand | Check id to expected status (`met`, `partial`, `not_met`, `unknown`) in both modes |
| `rules` | generated | Composite score and coverage plus per-domain score and coverage, rules mode |
| `judge` | generated | Same, judge mode; present only when it differs from `rules` |

## Changing scoring configuration

1. Edit `config/scoring/*.yaml` or `config/profiles/*.yaml`.
2. Run `make evals`. A failure lists every pinned value outside its tolerance and every designed status that
   changed. If the change was not intended, fix the configuration.
3. If the change is intended, run `make evals-refresh`, then review `git diff tests/evals/packs` the way you
   would review a snapshot: every moved number should be explained by the change you made. Commit the refreshed
   `expected.yaml` files with the configuration change.
4. A designed status in `checks` that legitimately changes is edited by hand, with a sentence in the PR
   explaining why the pack's intent now reads differently.

To widen a tolerance (for example a pack that is sensitive to a signal you expect to tune often), set
`tolerance` on the pack or add one key to `tolerances`; keep the default tight (`1.0`) so that drift of a
single check (worth 2 to 5 points inside a pillar) is still caught.

## The packs

| Pack | Organisation (fictional) | Profile | Design |
|---|---|---|---|
| `01_mature_enterprise` | Nimbus Orchard Holdings | default | Six well-written documents covering every pillar; every check met, 100 / 100 |
| `02_startup_minimal` | Pixelmoth Labs | default | One blurb (irrelevant) and one short technical note; coverage near zero, three partial verdicts |
| `03_security_heavy_no_cloud` | Ironvale Mutual Savings Bank | default | Strong network security, no cloud or AI material; NS near 100, the other domains mostly unknown |
| `04_cloud_native_weak_netsec` | Kestrel Stack Inc | default | Mature cloud platform plus a network note with explicit negatives (no firewall, flat network, SSH open, shared admin account) |
| `05_ai_forward` | Lumen Fox AI | default | Agentic AI domain fully met; thin IT basics elsewhere |
| `06_explicit_negatives` | Rustbucket Logistics | default | Audit findings written as negative statements; seven checks must be `not_met` |
| `07_noisy_office` | Blue Teacup Catering | default | Two real documents plus a menu, meeting notes, a newsletter and an invoice that must classify as irrelevant; the WAF mentioned only in the meeting notes must not count |
| `08_single_large_document` | Granite Heron Utilities | default | One ~7 KB handbook covering everything in nine sections; AI platform and agent protocols absent |
| `09_many_tiny_documents` | Thimbleweed Dental Group | default | 24 documents of one to three lines, each classified on its own |
| `10_mixed_formats` | Saffron Comet Retail | default | Markdown, CSV, JSON, YAML, txt, DOCX, XLSX and an unsupported SVG that produces a warning |
| `11_gcp_migration_candidate` | Copperfield Marine Insurance | gcp_migration | Discovery inventory, portfolio, connectivity and cost material; cloud readiness near 100 |
| `12_security_only_review` | Verdigris Clinic Network | security_only | Medium security posture; the report has a single domain |
| `13_mid_maturity` | Halcyon Pebble Co-op | default | A little of everything in one summary; many partial verdicts |
| `14_legacy_datacenter` | Old Mill Paper Works | default | On-premises VMware estate with a good inventory, flat network, exposed RDP and TLS 1.0 |
| `15_regulated_healthcare` | Meadowlark Health Partners | default | Strong compliance and AI governance, no AI platform selected |
| `16_shadow_ai` | Quartz Badger Media | default | Ungoverned AI tooling: hardcoded API key and credentials in prompts fail AI-SEC-02 |
| `17_contradictory_evidence` | Tin Lantern Software | default | A strong policy contradicted by an audit exceptions register; negative signals override the positives |
| `18_doc_class_scoping` | Silver Marmot Freight | default | Topology evidence lives in an operations runbook, outside the classes NS-SEG-02 may search (unknown); CR-CMP-01 has no inventory document and falls back to all documents (met) |
| `19_no_relevant_docs` | Paper Kite Florist | default | Only noise documents; score and coverage are zero and the "no relevant documents" warning is raised |
| `20_aws_centric` | Juniper Owl Fintech | default | AWS-centric evidence; the signals are provider-neutral, so the scores stay high |

## Behaviours the packs pin on purpose

These are properties of the rule engine as configured today. They are pinned so that a change to them is
noticed, not because they are necessarily desirable; the LLM judge exists to refine them.

- A negative signal overrides any positive evidence for the same check (`17_contradictory_evidence`), even
  when the sentence says the weak protocol is *disabled* ("TLS 1.0 and SSLv3 are disabled" fails NS-RES-01).
- A statement of absence without a configured negative signal counts as weak positive evidence
  ("no WAF" is a partial NS-PER-02 in `04_cloud_native_weak_netsec`; "no AI policy exists" is a partial
  AI-GOV-01 in `16_shadow_ai`).
- IP literals are pseudonymised before scoring, so a negative signal written as an address
  (`0.0.0.0/0`) can never match; the packs use "SSH open to the internet" instead.
- `doc_classes` restricts the search only while a document of that class exists; otherwise the check
  searches every relevant document (`18_doc_class_scoping`).
- A document whose noise score (meeting notes, agenda, invoice, newsletter, marketing) beats its best class
  score is irrelevant and never searched, whatever technical words it contains (`07_noisy_office`).
