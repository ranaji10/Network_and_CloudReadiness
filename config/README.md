# Configuration

Everything that decides *what* the tool measures and recommends lives here as YAML. Code decides *how*.
Full field reference: `docs/architecture/CONFIG_REFERENCE.md`.

| Folder / file | What it holds | Loaded by |
|---|---|---|
| `profiles/*.yaml` | Which domains count, their weights, grade thresholds, signal rules, provider preference | `readiness.scoring.profiles.load_profile` |
| `scoring/*.yaml` | One domain per file: pillars with weights, checks with points, signals and CCM control ids | `readiness.scoring.profiles.load_domain` |
| `recommendations/catalog.yaml` | One entry per check id: the action, effort, impact and GCP / AWS / open-source / process options | `readiness.recommend.engine.load_catalog` |
| `redaction.yaml` | Regex rules for secrets, PII and identifiers, applied before anything leaves the process | `readiness.guardrails.redaction.Redactor.from_config` |

The directory is found in this order: `READINESS_CONFIG_DIR`, then `<repo>/config`, then a `config/`
folder next to the installed package (Agent Runtime bundle), then the copy bundled into the wheel.

## Edit, test, repeat

```bash
uv run readiness profiles                      # list profiles and their domains
uv run readiness checks cloud_readiness        # list a domain's pillars, checks, points and CCM ids
uv run readiness controls "key rotation"       # search the CSA CCM v4.1 catalog for a control id
uv run readiness redact some.txt --mode mask   # see what the redaction rules do to a file
make test                                      # schema validation and invariants
make demo                                      # full offline run on the synthetic sample, with snippets
```

Tests enforce these invariants (`tests/test_config_profiles.py`):

- every profile and every domain parses against the pydantic schema (unknown fields are an error);
- check ids are unique within a domain;
- every check has `signals` or `strong_signals`;
- every `ccm` id exists in the CSA catalog;
- every check has an entry in `recommendations/catalog.yaml`;
- every pillar weight is greater than zero.

## Worked example: adding a check

Goal: score whether DNS filtering is in place, in the network security domain.

1. Pick the pillar and an id with the domain prefix (`NS-`, `CR-`, `AI-`). Append under `detection` in
   `scoring/network_security.yaml`:

   ```yaml
         - id: NS-DET-05
           title: DNS-layer filtering of malicious domains
           points: 3
           ccm: [I&S-09, TVM-02]
           signals: ["dns filtering", "protective dns", "cisco umbrella", "cloudflare gateway", "dns security", "sinkhole"]
           strong_signals: ["protective dns"]
           negative_signals: ["no dns filtering"]
           question: Is outbound DNS resolved through a filtering service that blocks known-bad domains?
   ```

2. Check the control ids exist: `uv run readiness controls I&S-09` and `uv run readiness controls TVM-02`.
3. Add the matching catalog entry in `recommendations/catalog.yaml`:

   ```yaml
     - check_id: NS-DET-05
       title: Route outbound DNS through a filtering resolver
       rationale: DNS is the cheapest place to break malware callbacks and phishing links.
       effort: S
       impact: medium
       options:
         - { provider: gcp, product: "Cloud DNS response policies + Cloud Armor / Cloud NGFW threat lists" }
         - { provider: aws, product: "Route 53 Resolver DNS Firewall" }
         - { provider: oss, product: "Pi-hole or Technitium with threat-intel block lists; Quad9 upstream" }
   ```

4. Run `make test`, then `make demo` and confirm the new row appears with the status you expect. If the
   pillar's total points changed, nothing else needs editing: pillar maximums are computed.

## Writing signals

- **Word or regex?** A signal is treated as a regular expression when it contains any of `\ [ ] ( ) . * + ? |`;
  otherwise it is matched as a whole, case-insensitive word or phrase (`\bphrase\b`). A dot makes it a
  regex, so `10.0.0.0` matches `10a0b0c0` too; write `10\.0\.0\.0` or avoid dots.
- **Weak vs strong.** Each entry in `signals` found anywhere in the relevant documents counts as one
  distinct signal; `met_min_signals` distinct ones (default 2) make the check PASS, one makes it PARTIAL.
  A single `strong_signals` hit is PASS on its own. Use strong signals only for phrases that can only
  mean the control is in place.
- **Negative signals** flip the check to FAIL whenever they match, regardless of positive hits, while
  `rules.negative_overrides` is true. Keep them literal and rare (`"no firewall"`, `"mfa is not enforced"`);
  a loose negative such as `"not"` would fail everything.
- **Distinct means distinct strings.** The same signal found in five documents is still one signal. Spread
  synonyms across entries rather than repeating one.
- **Scoring runs on redacted text.** IPs, hostnames, e-mails and secrets have already been replaced by
  placeholders when signals are evaluated, so never write a signal that depends on them.
- **`doc_classes`** limits the search to documents the classifier put in those classes (`network`,
  `architecture`, `security_policy`, `compliance_audit`, `inventory`, `data_storage`, `identity`,
  `backup_dr`, `contract_license`, `ai_ml`, `operations`). If no relevant document has one of those
  classes, the check falls back to all relevant documents, so the filter never silently hides evidence.
- **`question`** is only used when the LLM judge is enabled (`READINESS_USE_LLM_JUDGE=true`); it is the
  question put to the model for that check. `tags` is free-form and unused by the engine.

## Profiles

Copy `profiles/default.yaml`, change `id`, domain weights, `thresholds`, `rules` and `target_providers`.
New profiles are discovered automatically and selected with `--profile <id>` or the `profile` query
parameter of the API. Domain weights are relative; they do not need to sum to 100.

## Redaction rules

Rules in `redaction.yaml` run in file order with the `re.I | re.M` flags. `kind: secret` rules are
always masked irreversibly, in every mode. `pii` and `identifier` rules are masked in `mask` mode and
replaced by stable per-run pseudonyms (`<ip-01>`, `<host-02>`) in `pseudonymize` mode. Put specific
patterns before general ones, and test each new rule with `uv run readiness redact` plus a case in
`tests/test_redaction.py`.
