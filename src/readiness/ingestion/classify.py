"""Keyword classifier for documents. Deterministic and cheap; an LLM classifier can refine it."""

from __future__ import annotations

import re

from readiness.models import DocClass

# Each class: list of (regex, weight). Scores are summed; the best class wins if above threshold.
_RULES: dict[DocClass, list[tuple[str, float]]] = {
    DocClass.NETWORK: [
        (r"\b(vlan|subnet|cidr|firewall|vpn|bgp|ospf|router|switch|wan|lan|dmz|ids|ips|waf|ddos|nat)\b", 2),
        (r"\b(network (diagram|topology|architecture)|ip (plan|schema|address))\b", 4),
    ],
    DocClass.ARCHITECTURE: [
        (r"\b(architecture|topology|microservice|monolith|load balancer|kubernetes|gke|eks|cloud run)\b", 2),
        (r"\b(solution design|system design|hld|lld|reference architecture)\b", 4),
    ],
    DocClass.SECURITY_POLICY: [
        (r"\b(policy|standard|procedure|acceptable use|incident response|vulnerability management)\b", 2),
        (r"\b(information security policy|security baseline|hardening)\b", 4),
    ],
    DocClass.COMPLIANCE_AUDIT: [
        (r"\b(soc ?2|iso ?27001|pci[- ]dss|hipaa|gdpr|audit report|caiq|ccm|nist|cis benchmark)\b", 4),
    ],
    DocClass.INVENTORY: [
        (r"\b(inventory|asset (list|register)|cmdb|server list|vm list|hardware)\b", 3),
        (r"\b(cpu|ram|vcpu|hostname|serial number)\b", 1),
    ],
    DocClass.DATA_STORAGE: [
        (r"\b(database|schema|postgres|mysql|oracle|sql server|mongodb|storage|nfs|smb|san|nas|iops)\b", 2),
    ],
    DocClass.IDENTITY: [
        (r"\b(active directory|okta|ldap|sso|saml|oidc|mfa|iam|rbac|identity provider|entra)\b", 3),
    ],
    DocClass.BACKUP_DR: [
        (r"\b(backup|restore|disaster recovery|rpo|rto|business continuity|snapshot|replication)\b", 3),
    ],
    DocClass.CONTRACT_LICENSE: [
        (r"\b(license|licence|enterprise agreement|software assurance|msa|sow|contract|subscription)\b", 3),
    ],
    DocClass.AI_ML: [
        (
            r"\b(llm|machine learning|ml pipeline|model registry|vector (db|database|store)|rag)\b",
            3,
        ),
        (
            r"\b(agent(ic)?|mlops|prompt)\b",
            3,
        ),
        (r"\b(vertex ai|bedrock|sagemaker|openai|gemini|anthropic|claude|embeddings)\b", 3),
    ],
    DocClass.OPERATIONS: [
        (r"\b(runbook|monitoring|logging|siem|observability|on-call|sre|change management|patching)\b", 3),
    ],
}
_NOISE = [
    (r"\b(meeting (minutes|notes)|agenda|invoice|receipt|marketing|newsletter|press release)\b", 4),
]
_COMPILED = {k: [(re.compile(p, re.I), w) for p, w in v] for k, v in _RULES.items()}
_NOISE_C = [(re.compile(p, re.I), w) for p, w in _NOISE]


def classify(name: str, text: str, threshold: float = 4.0) -> tuple[DocClass, float]:
    sample = (name + "\n" + text[:20000]).lower()
    scores: dict[DocClass, float] = {}
    for cls, rules in _COMPILED.items():
        s = 0.0
        for rx, w in rules:
            hits = len(rx.findall(sample))
            if hits:
                s += w * min(hits, 5)
        scores[cls] = s
    noise = sum(w * min(len(rx.findall(sample)), 5) for rx, w in _NOISE_C)
    best = max(scores, key=lambda k: scores[k])
    best_score = scores[best]
    if best_score < threshold or noise > best_score:
        return DocClass.IRRELEVANT, min(1.0, noise / 20) if noise else 0.2
    total = sum(scores.values()) or 1.0
    return best, round(min(1.0, best_score / total + 0.3), 2)
