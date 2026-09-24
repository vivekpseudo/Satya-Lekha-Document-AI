from __future__ import annotations

import os
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(
        A4[0] / 2, 8 * mm, f"Satya-Lekha • Confidential • Page {doc.page}"
    )
    canvas.restoreState()


def _brand_logo(path: str | None):
    if path and Path(path).exists():
        img = Image(path)
        img.drawHeight = 20 * mm
        img.drawWidth = 55 * mm
        return img
    return Paragraph(
        "SATYA-LEKHA",
        ParagraphStyle(
            "BrandLogo",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            alignment=TA_CENTER,
        ),
    )


def build_compliance_report(
    output_path: str,
    *,
    company_name: str,
    document_name: str,
    reporting_date: str | None,
    classification: dict,
    findings: list[dict],
    logo_path: str | None = None,
) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    logo_path = logo_path or os.getenv("SATYA_LEKHA_LOGO_PATH")

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Satya-Lekha Compliance Report",
        author="Satya-Lekha",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle", parent=styles["Title"], fontSize=28,
            leading=34, alignment=TA_CENTER, spaceAfter=12
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSub", parent=styles["BodyText"], fontSize=10.5,
            leading=15, alignment=TA_CENTER, textColor=colors.grey
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallSL", parent=styles["BodyText"], fontSize=8.5, leading=11
        )
    )
    styles.add(
        ParagraphStyle(
            name="FindingSL", parent=styles["Heading3"], spaceBefore=8, spaceAfter=4
        )
    )

    counts = {"PASS": 0, "FAIL": 0, "REVIEW": 0}
    for finding in findings:
        status = str(finding.get("status", "REVIEW")).upper()
        counts[status] = counts.get(status, 0) + 1

    story = [
        Spacer(1, 30 * mm),
        _brand_logo(logo_path),
        Spacer(1, 18 * mm),
        Paragraph("COMPLIANCE REPORT", styles["CoverTitle"]),
        Paragraph(
            f"<b>{escape(company_name)}</b><br/>{escape(document_name)}",
            styles["CoverSub"],
        ),
        Spacer(1, 7 * mm),
        Paragraph(
            f"Reporting date: {escape(reporting_date or 'Not provided')}",
            styles["CoverSub"],
        ),
        Spacer(1, 15 * mm),
    ]

    cover_table = Table(
        [
            ["Document Type", str(classification.get("document_type", "unknown"))],
            ["Classification Confidence", f"{classification.get('confidence', 0):.2f}"],
            ["PASS", str(counts.get("PASS", 0))],
            ["FAIL", str(counts.get("FAIL", 0))],
            ["REVIEW", str(counts.get("REVIEW", 0))],
        ],
        colWidths=[62 * mm, 55 * mm],
        hAlign="CENTER",
    )
    cover_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story += [
        cover_table,
        Spacer(1, 22 * mm),
        Paragraph(
            "Prepared by Satya-Lekha automated compliance analysis.",
            styles["CoverSub"],
        ),
        Paragraph(
            "This report is an analytical output and is not, by itself, a statutory audit opinion or legal opinion.",
            styles["CoverSub"],
        ),
        Paragraph("EXECUTIVE SUMMARY", styles["CoverTitle"]),
        Paragraph(
            "Automated assessment of extracted financial statements against the configured Satya-Lekha compliance rules and retrieved regulatory evidence.",
            styles["CoverSub"],
        ),
        Spacer(1, 10 * mm),
        Table(
            [["Outcome", "Count"],
             ["PASS", str(counts.get("PASS", 0))],
             ["FAIL", str(counts.get("FAIL", 0))],
             ["REVIEW", str(counts.get("REVIEW", 0))]],
            colWidths=[55 * mm, 30 * mm],
            hAlign="CENTER",
            style=TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ]),
        ),
        Spacer(1, 10 * mm),
        Paragraph("Overall interpretation", styles["Heading3"]),
        Paragraph(
            "FAIL findings identify rule checks whose configured conditions were not satisfied. REVIEW findings indicate that the available extraction, applicability metadata, or source evidence requires human verification.",
            styles["BodyText"],
        ),
        PageBreak(),
        Paragraph("Executive Summary", styles["Heading2"]),
    ]

    summary = Table(
        [["Status", "Count"]]
        + [[key, str(counts.get(key, 0))] for key in ("PASS", "FAIL", "REVIEW")],
        colWidths=[45 * mm, 25 * mm],
    )
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ]
        )
    )
    story += [summary, Spacer(1, 12), Paragraph("Detailed Findings", styles["Heading2"])]

    if not findings:
        story.append(Paragraph("No findings were produced by the configured rules.", styles["BodyText"]))

    for finding in findings:
        story.append(
            Paragraph(
                escape(f"{finding.get('rule_id', '')} - {finding.get('title', '')}"),
                styles["FindingSL"],
            )
        )
        story.append(
            Paragraph(
                f"<b>Status:</b> {escape(str(finding.get('status', 'REVIEW')))} "
                f"&nbsp;&nbsp;<b>Severity:</b> {escape(str(finding.get('severity', 'MEDIUM')))} "
                f"&nbsp;&nbsp;<b>Confidence:</b> {finding.get('confidence', 0):.2f}",
                styles["SmallSL"],
            )
        )
        story.append(Paragraph(escape(str(finding.get("message", ""))), styles["BodyText"]))

        evidence_rows = [["Financial evidence", "Page", "Value"]]
        for evidence in finding.get("evidence", []):
            evidence_rows.append(
                [
                    escape(str(evidence.get("label", ""))),
                    str(evidence.get("source_page", "")),
                    str(evidence.get("value", "")),
                ]
            )

        if len(evidence_rows) > 1:
            t = Table(evidence_rows, colWidths=[82 * mm, 18 * mm, 35 * mm])
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
            story += [Spacer(1, 4), t]

        regulations = finding.get("regulatory_evidence", [])
        if regulations:
            story.append(Paragraph("Regulatory Evidence", styles["Heading4"]))
            for reg in regulations:
                story.append(
                    Paragraph(
                        f"<b>{escape(str(reg.get('regulation_id', '')))}</b> — "
                        f"{escape(str(reg.get('title', '')))}<br/>"
                        f"{escape(str(reg.get('text', '')))}<br/>"
                        f"Source: {escape(str(reg.get('source_uri', '')))}<br/>"
                        f"Effective: {escape(str(reg.get('effective_from', '')))} "
                        f"to {escape(str(reg.get('effective_to', '')))}",
                        styles["SmallSL"],
                    )
                )
                story.append(Spacer(1, 4))

    story += [
        PageBreak(),
        Paragraph("Methodology, Sources and Limitations", styles["Heading2"]),
        Paragraph(
            "Findings are generated from extracted financial data, configured deterministic rules, "
            "and retrieved regulatory evidence. Similarity retrieval is used to discover candidate "
            "evidence; it is not treated as proof of regulatory applicability.",
            styles["BodyText"],
        ),
        Spacer(1, 8),
        Paragraph(
            "Production deployment requires authoritative regulatory source ingestion, versioning, "
            "effective-date controls, entity applicability controls, audit logging, and qualified review.",
            styles["BodyText"],
        ),
    ]

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return str(path)
