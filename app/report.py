from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)


def build_compliance_report(
    output_path: str,
    *,
    company_name: str,
    document_name: str,
    reporting_date: str | None,
    classification: dict,
    findings: list[dict],
) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="Satya-Lekha Compliance Report",
        author="Satya-Lekha",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Small", parent=styles["BodyText"], fontSize=8.5, leading=11
        )
    )
    styles.add(
        ParagraphStyle(
            name="Finding", parent=styles["Heading3"], spaceBefore=8, spaceAfter=4
        )
    )

    story = [
        Paragraph("Satya-Lekha Compliance Report", styles["Title"]),
        Spacer(1, 6),
        Paragraph(f"<b>Company:</b> {escape(company_name)}", styles["BodyText"]),
        Paragraph(f"<b>Document:</b> {escape(document_name)}", styles["BodyText"]),
        Paragraph(
            f"<b>Reporting date:</b> {escape(reporting_date or 'Not provided')}",
            styles["BodyText"],
        ),
        Paragraph(
            f"<b>Document type:</b> {escape(str(classification.get('document_type', 'unknown')))} "
            f"(confidence {classification.get('confidence', 0):.2f})",
            styles["BodyText"],
        ),
        Spacer(1, 10),
        Paragraph("Executive Summary", styles["Heading2"]),
    ]

    counts = {"PASS": 0, "FAIL": 0, "REVIEW": 0}
    for finding in findings:
        status = finding.get("status", "REVIEW")
        counts[status] = counts.get(status, 0) + 1

    summary = [
        ["Status", "Count"],
        ["PASS", str(counts.get("PASS", 0))],
        ["FAIL", str(counts.get("FAIL", 0))],
        ["REVIEW", str(counts.get("REVIEW", 0))],
    ]
    table = Table(summary, colWidths=[45 * mm, 25 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ]
        )
    )
    story += [table, Spacer(1, 12), Paragraph("Findings", styles["Heading2"])]

    if not findings:
        story.append(Paragraph("No findings were produced by the configured rules.", styles["BodyText"]))

    for finding in findings:
        story.append(Paragraph(
            escape(f"{finding.get('rule_id', '')} - {finding.get('title', '')}"),
            styles["Finding"],
        ))
        story.append(
            Paragraph(
                f"<b>Status:</b> {escape(str(finding.get('status', 'REVIEW')))} &nbsp; "
                f"<b>Severity:</b> {escape(str(finding.get('severity', 'MEDIUM')))} &nbsp; "
                f"<b>Confidence:</b> {finding.get('confidence', 0):.2f}",
                styles["Small"],
            )
        )
        story.append(Paragraph(escape(str(finding.get("message", ""))), styles["BodyText"]))

        evidence_rows = [["Financial evidence", "Page", "Value"]]
        for evidence in finding.get("evidence", []):
            evidence_rows.append([
                str(evidence.get("label", "")),
                str(evidence.get("source_page", "")),
                str(evidence.get("value", "")),
            ])

        if len(evidence_rows) > 1:
            story.append(Spacer(1, 4))
            t = Table(evidence_rows, colWidths=[80 * mm, 20 * mm, 35 * mm])
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ]
                )
            )
            story.append(t)

        regs = finding.get("regulatory_evidence", [])
        if regs:
            story.append(Spacer(1, 5))
            story.append(Paragraph("Regulatory Evidence", styles["Heading4"]))
            for reg in regs:
                story.append(
                    Paragraph(
                        f"<b>{escape(str(reg.get('regulation_id', '')))}</b> - "
                        f"{escape(str(reg.get('title', '')))}<br/>"
                        f"{escape(str(reg.get('text', '')))}<br/>"
                        f"Source: {escape(str(reg.get('source_uri', '')))}<br/>"
                        f"Effective: {escape(str(reg.get('effective_from', '')))} "
                        f"to {escape(str(reg.get('effective_to', '')))}",
                        styles["Small"],
                    )
                )

    story += [
        PageBreak(),
        Paragraph("Methodology and Limitations", styles["Heading2"]),
        Paragraph(
            "This report is generated from extracted document data, configured deterministic rules, "
            "and retrieved regulatory evidence. Retrieval similarity is not treated as proof of legal "
            "applicability. Prototype rules must be linked to authoritative source material and "
            "validated by qualified accounting/legal reviewers before production compliance use.",
            styles["BodyText"],
        ),
    ]

    doc.build(story)
    return str(path)
