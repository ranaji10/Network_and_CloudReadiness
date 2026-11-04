"""PDF renderer (API-04). Renders the same structure as `report/markdown.py` straight from the
`AssessmentReport` model (never by parsing the Markdown) so the two deliverables cannot drift.

Dependency: `fpdf2`, pure Python, installed through the optional `pdf` extra (`uv sync --extra pdf`).
It is imported lazily so the core package, the CLI and the API start without it; `render_pdf` raises
`PdfExportUnavailableError` with the install hint when it is missing and the API turns that into a 501.

Fonts: only fpdf2's built-in core fonts (Helvetica) are used, so nothing is downloaded and no system
font is needed in the slim container. Core fonts cover Latin-1 only; `_t` maps the typographic
characters the report uses (em dash, ellipsis, curly quotes, arrows) to ASCII and replaces anything
else with `?` instead of failing the export.

Share-safe mode: when `report.redaction.share_safe` is set (GRD-09; `report.extra["share_safe"]` also
works for hand-built reports) the tenant id is withheld and document names
are left out of the PDF (documents table and evidence references) and a note says so."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from readiness.models import AssessmentReport, CheckResult, CheckStatus
from readiness.report.markdown import COST_BAND_LEGEND

if TYPE_CHECKING:
    from fpdf import FPDF

INSTALL_HINT = "PDF export needs the `pdf` extra: `uv sync --extra pdf` (or `pip install 'readiness[pdf]'`)."

_STATUS = {
    CheckStatus.MET: "PASS",
    CheckStatus.PARTIAL: "PARTIAL",
    CheckStatus.NOT_MET: "FAIL",
    CheckStatus.UNKNOWN: "NO EVIDENCE",
}

# Characters outside Latin-1 that the report text commonly contains, mapped to ASCII equivalents.
_ASCII = str.maketrans(
    {
        "—": "-",  # em dash
        "–": "-",  # en dash
        "…": "...",  # ellipsis
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "→": "->",  # arrow
        "•": "-",  # bullet
        "✓": "yes",
        "✗": "no",
        " ": " ",
        "​": "",
    }
)

TITLE = "Network, Cloud & Agentic-AI Readiness Assessment"


class PdfExportUnavailableError(RuntimeError):
    """Raised when fpdf2 is not installed. The message carries the install hint."""


def _t(value: Any) -> str:
    """Make a string safe for fpdf2's core (Latin-1) fonts."""
    return str(value).translate(_ASCII).encode("latin-1", "replace").decode("latin-1")


def _coverage_threshold(report: AssessmentReport) -> float:
    return report.domains[0].thresholds.get("high_confidence_coverage", 70) if report.domains else 70


def _evidence_text(check: CheckResult, share_safe: bool) -> str:
    """Document names and (if the run kept them) one snippet per document, as in the Markdown table."""
    if not check.evidence:
        return ""
    parts: list[str] = []
    if share_safe:
        parts.append(f"({len({e.doc_id for e in check.evidence})} document(s))")
    else:
        names = sorted({e.doc_name for e in check.evidence})
        parts.append("(" + ", ".join(names[:3]) + (", ..." if len(names) > 3 else "") + ")")
    seen: set[str] = set()
    snippets: list[str] = []
    for e in check.evidence:
        if e.snippet and e.doc_name not in seen:
            seen.add(e.doc_name)
            snippets.append(e.snippet[:160])
    parts.extend(f'"{s}"' for s in snippets[:2])
    return "\n".join(parts)


class _Doc:
    """Thin layout helper over fpdf2 so the section code below reads like the Markdown renderer."""

    def __init__(self, pdf: FPDF) -> None:
        self.pdf = pdf

    def heading(self, text: str, level: int) -> None:
        size = {1: 17, 2: 13, 3: 11, 4: 10}[level]
        self.pdf.ln(3 if level > 1 else 0)
        self.pdf.set_font("Helvetica", "B", size)
        self.pdf.multi_cell(0, size * 0.55, _t(text), new_x="LMARGIN", new_y="NEXT")
        self.pdf.ln(1)
        self.body_font()

    def body_font(self, size: float = 9.5, style: str = "") -> None:
        self.pdf.set_font("Helvetica", style, size)

    def para(self, text: str, size: float = 9.5, style: str = "", indent: float = 0) -> None:
        self.body_font(size, style)
        if indent:
            self.pdf.set_x(self.pdf.l_margin + indent)
        self.pdf.multi_cell(0, size * 0.5, _t(text), new_x="LMARGIN", new_y="NEXT")
        self.body_font()

    def note(self, text: str) -> None:
        self.pdf.set_text_color(90, 90, 90)
        self.para(text, size=8.5, style="I")
        self.pdf.set_text_color(0, 0, 0)

    def table(self, header: list[str], rows: list[list[str]], widths: tuple[float, ...], align: tuple[str, ...]):
        from fpdf.enums import TableBordersLayout
        from fpdf.fonts import FontFace

        if not rows:
            self.note("none")
            return
        self.body_font(8)
        with self.pdf.table(
            col_widths=widths,
            text_align=align,
            borders_layout=TableBordersLayout.HORIZONTAL_LINES,
            headings_style=FontFace(emphasis="BOLD", fill_color=(235, 238, 242)),
            line_height=4.2,
            padding=1,
        ) as table:
            table.row([_t(h) for h in header])
            for r in rows:
                table.row([_t(c) for c in r])
        self.body_font()
        self.pdf.ln(2)


def _make_pdf(footer_text: str) -> FPDF:
    from fpdf import FPDF

    class _ReportPDF(FPDF):
        def footer(self) -> None:
            self.set_y(-12)
            self.set_font("Helvetica", "I", 7.5)
            self.set_text_color(120, 120, 120)
            self.cell(0, 5, _t(footer_text), align="L")
            self.cell(0, 5, f"page {self.page_no()}/{{nb}}", align="R")
            self.set_text_color(0, 0, 0)

    pdf = _ReportPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_margins(16, 16, 16)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_title(TITLE)
    pdf.set_creator("readiness")
    return pdf


def render_pdf(report: AssessmentReport) -> bytes:
    """Render the report to PDF bytes. Raises `PdfExportUnavailableError` when fpdf2 is not installed."""
    try:
        import fpdf  # noqa: F401 - presence check; the renderer imports what it needs lazily
    except ImportError as exc:
        raise PdfExportUnavailableError(INSTALL_HINT) from exc

    share_safe = bool(report.redaction.share_safe or report.extra.get("share_safe"))
    tenant = "withheld" if share_safe else report.tenant_id
    pdf = _make_pdf(f"Readiness report {report.id} - tenant {tenant} - profile {report.profile}")
    pdf.add_page()
    doc = _Doc(pdf)

    # Title block
    doc.heading(TITLE, 1)
    doc.note(
        f"Report {report.id} - tenant {tenant} - {report.created_at:%Y-%m-%d %H:%M UTC} - "
        f"profile {report.profile} v{report.profile_version} - tool v{report.tool_version}"
    )

    # 1. Scores at a glance
    doc.heading("1. Scores at a glance", 2)
    rows = [["Overall", f"{report.overall_score:.0f} / 100", "", f"{report.overall_coverage:.0f}%"]]
    rows += [[d.name, f"{d.score:.0f} / 100", d.grade, f"{d.coverage:.0f}%"] for d in report.domains]
    doc.table(["Area", "Posture score", "Grade", "Evidence coverage"], rows, (46, 18, 12, 24), ("L", "R", "C", "R"))
    hc = _coverage_threshold(report)
    if report.overall_coverage < hc:
        doc.para(
            f"Evidence coverage is below the {hc:.0f}% confidence threshold. The posture score is only as good as "
            "the documents supplied. Work through the discovery items in section 4b before acting on the actions.",
            style="B",
        )
    else:
        doc.para(
            f"Evidence coverage meets the {hc:.0f}% confidence threshold; the posture scores can be used for planning."
        )
    doc.heading("How the score is calculated", 3)
    doc.para(
        "Each area is made of weighted pillars; each pillar is a set of checks with points. A check is PASS when two "
        "or more independent signals (or one strong signal) are found, PARTIAL on a single weak signal, FAIL when the "
        "documents state the control is absent, and NO EVIDENCE otherwise. Posture = earned points / available "
        "points, weighted. Coverage = share of checks with any evidence, weighted. Checks map to CSA Cloud Controls "
        "Matrix v4.1 controls where applicable."
    )

    # 2. Documents reviewed
    doc.heading("2. Documents reviewed", 2)
    # In share-safe mode every document name (table, evidence, warnings) becomes "document N".
    alias = {r.name: f"document {i}" for i, r in enumerate(report.documents, 1)} if share_safe else {}
    if share_safe:
        doc.note("Share-safe report: document names are withheld; only classes and sources are listed.")
    doc_rows = [[alias.get(r.name, r.name), report.document_classes.get(r.id, "-"), r.source] for r in report.documents]
    doc.table(["Document", "Class", "Source"], doc_rows, (60, 25, 15), ("L", "L", "L"))

    # 3. Detailed findings
    doc.heading("3. Detailed findings", 2)
    for d in report.domains:
        doc.heading(f"{d.name} - {d.score:.0f}/100 (grade {d.grade}, coverage {d.coverage:.0f}%)", 3)
        for p in d.pillars:
            doc.heading(
                f"{p.name} (weight {p.weight:g}) - {p.points:g}/{p.max_points:g} pts, coverage {p.coverage * 100:.0f}%",
                4,
            )
            check_rows = [
                [
                    f"{c.check_id} {c.title}",
                    _STATUS[c.status],
                    f"{c.points:g}/{c.max_points:g}",
                    ", ".join(c.ccm_controls),
                    "\n".join(x for x in (c.rationale, _evidence_text(c, share_safe)) if x),
                ]
                for c in p.checks
            ]
            doc.table(
                ["Check", "Result", "Pts", "CCM", "Rationale"],
                check_rows,
                (30, 13, 9, 14, 34),
                ("L", "L", "R", "L", "L"),
            )

    # 4. Recommendations
    doc.heading("4. Recommendations", 2)
    actions = [r for r in report.recommendations if r.kind == "action"]
    disc = [r for r in report.recommendations if r.kind == "discovery"]
    doc.heading(f"4a. Actions ({len(actions)}) - prioritised", 3)
    doc.note(COST_BAND_LEGEND)
    for i, r in enumerate(actions, 1):
        doc.para(f"{i}. {r.title}", style="B")
        doc.note(f"effort {r.effort} - impact {r.impact} - check {r.check_id}")
        closes = r.closes_check_ids or [r.check_id]
        titles = r.closes_titles if len(r.closes_titles) == len(closes) else [""] * len(closes)
        doc.note("Closes: " + ", ".join(f"{cid} {t}".strip() for cid, t in zip(closes, titles, strict=True)))
        if r.rationale:
            doc.para(r.rationale, indent=5)
        for o in r.options:
            # REC-03: documentation url on the same line as the product (core fonts: plain ASCII, no link object)
            product = f"{o.product} ({o.url})" if o.url else o.product
            band = f" - cost: {o.cost_band}" if o.cost_band else ""  # REC-04
            doc.para(f"- {o.provider.upper()}: {product}{band}" + (f" - {o.note}" if o.note else ""), indent=5)
        pdf.ln(1.5)
    if not actions:
        doc.note("none")
    doc.heading(f"4b. Discovery - evidence to collect ({len(disc)})", 3)
    for r in disc:
        doc.para(f"- {r.check_id} {r.title.removeprefix('Provide evidence for: ')}", style="B")
        for q in r.caiq_questions[:3]:
            doc.para(f"- {q}", size=8.5, indent=6)
    if not disc:
        doc.note("none")

    # 5. Migration waves (only when the profile asked for them and an inventory document existed)
    section = 5
    plan = report.migration_waves
    if plan is not None and plan.inventory_documents:
        doc.heading(f"{section}. Migration waves", 2)
        doc.note(
            f"{plan.total_systems} systems from {len(plan.inventory_documents)} inventory document(s), placed by the "
            "first matching signal; rows without a signal fall into the default wave."
        )
        for wave in sorted(plan.waves, key=lambda v: v.order):
            doc.heading(f"{wave.name} ({wave.count})", 3)
            if wave.description:
                doc.para(wave.description, size=8.5)
            rows = [[x.system, x.reason, alias.get(x.source_doc, x.source_doc)] for x in wave.systems]
            if rows:
                doc.table(["System", "Reason", "Source document"], rows, (50, 70, 50), ("L", "L", "L"))
            if wave.count > len(wave.systems):
                doc.note(f"... and {wave.count - len(wave.systems)} more")
        section += 1

    # Data handling
    doc.heading(f"{section}. Data handling", 2)
    counts = ", ".join(f"{k}={v}" for k, v in report.redaction.counts.items()) or "none"
    doc.para(
        f"Redaction mode {report.redaction.mode}; LLM provider {report.llm_provider}. Redaction counts: {counts}. "
        "No document content is stored in logs; see docs/security/DATA_HANDLING_POLICY.md."
    )
    if share_safe:
        doc.para("This is a share-safe rendering: document names are withheld throughout.", style="B")
    usage = report.extra.get("llm_usage")
    if usage:
        cost = usage.get("estimated_cost_usd")
        cost_txt = (
            f"about USD {cost:.4f} at list price" if cost is not None else "cost not estimated (no pricing entry)"
        )
        doc.para(
            f"Model usage: {usage.get('calls', 0)} call(s) to {usage.get('model') or usage.get('provider')}, "
            f"{usage.get('input_tokens', 0):,} input and {usage.get('output_tokens', 0):,} output tokens, {cost_txt}."
        )
    if report.warnings:
        doc.heading("Warnings", 2)
        for w in report.warnings:
            for name, placeholder in alias.items():
                w = w.replace(name, placeholder)
            doc.para(f"- {w}", size=8.5)

    return bytes(pdf.output())
