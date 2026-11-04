"""Secrets are always masked. Identifiers (IPs, hostnames, emails, account ids) are masked or
pseudonymized with a per-run, in-memory mapping. The mapping is only ever written to the local
workspace when explicitly requested and never leaves the process otherwise.

Share-safe runs (GRD-09) additionally hide document names: `share_safe_ref` swaps a DocumentRef's name
and uri for an opaque label derived from the document hash, so a report can leave the tenant without
listing what the client's files are called."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from readiness.config import resolve_default_config_dir
from readiness.models import DocumentRef


def default_rules_path() -> Path:
    """config/redaction.yaml from wherever the configuration lives (checkout, staged bundle or wheel)."""
    return resolve_default_config_dir() / "redaction.yaml"


def share_safe_label(ref: DocumentRef) -> str:
    """Opaque, stable label for a document: `doc-<6 hex>` from its content hash (or its id when the source
    gave no hash). Stable across runs for the same content, so two share-safe reports stay comparable."""
    return f"doc-{(ref.sha256 or ref.id)[:6]}"


def share_safe_ref(ref: DocumentRef) -> DocumentRef:
    """Copy of `ref` with the name and uri replaced by the opaque label. Id, source, mime, size and hash
    stay: they are metadata the audit log already carries."""
    label = share_safe_label(ref)
    return ref.model_copy(update={"name": label, "uri": f"share-safe://{label}"})


@dataclass
class RedactionRule:
    name: str
    pattern: re.Pattern[str]
    kind: str  # secret | pii | identifier
    placeholder: str


@dataclass
class Redactor:
    mode: str = "pseudonymize"  # off | mask | pseudonymize
    rules: list[RedactionRule] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    _reverse: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_config(cls, mode: str, path: Path | None = None) -> Redactor:
        data = yaml.safe_load((path or default_rules_path()).read_text())
        rules = [
            RedactionRule(r["name"], re.compile(r["pattern"], re.I | re.M), r["kind"], r.get("placeholder", r["name"]))
            for r in data["rules"]
        ]
        return cls(mode=mode, rules=rules)

    def _token(self, rule: RedactionRule, original: str) -> str:
        if rule.kind == "secret" or self.mode == "mask":
            return f"[REDACTED:{rule.placeholder}]"
        key = f"{rule.placeholder}:{original}"
        if key not in self._reverse:
            n = sum(1 for k in self._reverse if k.startswith(rule.placeholder + ":")) + 1
            token = f"<{rule.placeholder}-{n:02d}>"
            self._reverse[key] = token
            self.mapping[token] = original
        return self._reverse[key]

    def redact(self, text: str) -> str:
        if self.mode == "off":
            # secrets are masked even when identifier redaction is off
            rules = [r for r in self.rules if r.kind == "secret"]
        else:
            rules = self.rules
        for rule in rules:

            def _sub(m: re.Match[str], rule: RedactionRule = rule) -> str:
                self.counts[rule.name] = self.counts.get(rule.name, 0) + 1
                return self._token(rule, m.group(0))

            text = rule.pattern.sub(_sub, text)
        return text

    def summary(self) -> dict[str, int]:
        return dict(sorted(self.counts.items()))
