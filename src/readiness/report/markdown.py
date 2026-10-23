"""Markdown renderer. The report is the client-facing deliverable; keep it readable and honest about
coverage. Snippets are included only if the run was configured to include them."""

from __future__ import annotations

from readiness.models import AssessmentReport, CheckStatus

_ICON = {
    CheckStatus.MET: "PASS",
    CheckStatus.PARTIAL: "PARTIAL",
    CheckStatus.NOT_MET: "FAIL",
    CheckStatus.UNKNOWN: "NO EVIDENCE",
}


def render(report: AssessmentReport) -> str:
    lines: list[str] = []
    lines.append("# Network, Cloud & Agentic-AI Readiness Assessment\n")
    lines.append(
        f"*Report {report.id} · tenant `{report.tenant_id}` · {report.created_at:%Y-%m-%d %H:%M UTC} · "
        f"profile `{report.profile}` v{report.profile_version} · tool v{report.tool_version}*\n"
    )
    lines.append("## 1. Scores at a glance\n")
    lines.append("| Area | Posture score | Grade | Evidence coverage |")
    lines.append("|---|---:|:-:|---:|")
    lines.append(f"| **Overall** | **{report.overall_score:.0f} / 100** | | **{report.overall_coverage:.0f}%** |")
    for d in report.domains:
        lines.append(f"| {d.name} | {d.score:.0f} / 100 | {d.grade} | {d.coverage:.0f}% |")
    hc = report.domains[0].thresholds.get("high_confidence_coverage", 70) if report.domains else 70
    lines.append("")
    if report.overall_coverage < hc:
        lines.append(
            f"> **Evidence coverage is below the {hc:.0f}% confidence threshold.** The posture score is only as good "
            "as the documents supplied. Work through the *discovery* items in section 4 before acting on the actions."
        )
    else:
        lines.append(
            f"> Evidence coverage meets the {hc:.0f}% confidence threshold; "
            "the posture scores can be used for planning."
        )
    lines.append("\n### How the score is calculated\n")
    lines.append(
        "Each area is made of weighted pillars; each pillar is a set of checks with points. A check is **PASS** when "
        "two or more independent signals (or one strong signal) are found, **PARTIAL** on a single weak signal, "
        "**FAIL** "
        "when the documents state the control is absent, and **NO EVIDENCE** otherwise. Posture = earned points / "
        "available points, weighted. Coverage = share of checks with any evidence, weighted. Checks map to CSA Cloud "
        "Controls Matrix v4.1 controls where applicable."
    )
    lines.append("\n## 2. Documents reviewed\n")
    lines.append("| Document | Class | Source |")
    lines.append("|---|---|---|")
    for ref in report.documents:
        lines.append(f"| {ref.name} | {report.document_classes.get(ref.id, '-')} | {ref.source} |")
    lines.append("\n## 3. Detailed findings\n")
    for d in report.domains:
        lines.append(f"### {d.name} — {d.score:.0f}/100 (grade {d.grade}, coverage {d.coverage:.0f}%)\n")
        for p in d.pillars:
            lines.append(
                f"#### {p.name} (weight {p.weight:g}) — {p.points:g}/{p.max_points:g} pts, "
                f"coverage {p.coverage * 100:.0f}%\n"
            )
            lines.append("| Check | Result | Pts | CCM | Rationale |")
            lines.append("|---|---|---:|---|---|")
            for c in p.checks:
                ev = ""
                if c.evidence:
                    names = sorted({e.doc_name for e in c.evidence})
                    ev = " _(" + ", ".join(names[:3]) + (", …" if len(names) > 3 else "") + ")_"
                    seen: set[str] = set()
                    snippets = []
                    for e in c.evidence:  # one snippet per document keeps the table readable
                        if e.snippet and e.doc_name not in seen:
                            seen.add(e.doc_name)
                            snippets.append(e.snippet)
                    snippets = snippets[:2]
                    if snippets:
                        ev += "<br>" + "<br>".join(f"> {s[:160]}" for s in snippets)
                lines.append(
                    f"| {c.check_id} {c.title} | {_ICON[c.status]} | {c.points:g}/{c.max_points:g} | "
                    f"{', '.join(c.ccm_controls)} | {c.rationale}{ev} |"
                )
            lines.append("")
    lines.append("## 4. Recommendations\n")
    actions = [r for r in report.recommendations if r.kind == "action"]
    disc = [r for r in report.recommendations if r.kind == "discovery"]
    lines.append(f"### 4a. Actions ({len(actions)}) — prioritised\n")
    for i, r in enumerate(actions, 1):
        lines.append(f"**{i}. {r.title}** · effort {r.effort} · impact {r.impact} · check {r.check_id}")
        if r.rationale:
            lines.append(f"  \n{r.rationale}")
        for o in r.options:
            lines.append(f"- **{o.provider.upper()}**: {o.product}" + (f" — {o.note}" if o.note else ""))
        lines.append("")
    lines.append(f"### 4b. Discovery — evidence to collect ({len(disc)})\n")
    for r in disc:
        lines.append(f"- **{r.check_id}** {r.title.removeprefix('Provide evidence for: ')}")
        for q in r.caiq_questions[:3]:
            lines.append(f"  - {q}")
    lines.append("\n## 5. Data handling\n")
    lines.append(
        f"Redaction mode `{report.redaction.mode}`; LLM provider `{report.llm_provider}`. Redaction counts: "
        + (", ".join(f"{k}={v}" for k, v in report.redaction.counts.items()) or "none")
        + ". No document content is stored in logs; see docs/security/DATA_HANDLING_POLICY.md."
    )
    if report.warnings:
        lines.append("\n## Warnings\n")
        lines.extend(f"- {w}" for w in report.warnings)
    return "\n".join(lines) + "\n"
