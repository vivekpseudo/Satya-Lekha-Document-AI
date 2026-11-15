import io

import pytest
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from app.classifier import classify_document
from app.financial_normalizer import normalize_table_rows
from app.local_extractor import UnsupportedDocumentError, extract_pdf


def _balance_sheet_pdf(grid: bool) -> bytes:
    buf = io.BytesIO()
    data = [
        ["Particulars", "31 March 2024"],
        ["Total assets", "1,000.00"],
        ["Total liabilities", "400.00"],
        ["Total equity", "600.00"],
    ]
    table = Table(data, colWidths=[250, 120])
    if grid:
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    styles = getSampleStyleSheet()
    SimpleDocTemplate(buf, pagesize=A4).build(
        [Paragraph("Balance Sheet of Acme Ltd", styles["Title"]), table]
    )
    return buf.getvalue()


@pytest.mark.parametrize("grid", [True, False])
def test_balance_sheet_pdf_extracts_tables(grid):
    out = extract_pdf(_balance_sheet_pdf(grid))
    assert classify_document(out["text"]).document_type == "balance_sheet"
    body = out["pages"][0]["tables"][0]["body_rows"]
    rows = normalize_table_rows(body, 1)
    labels = {r.label: r.values[0] for r in rows}
    assert str(labels["Total assets"]) == "1000.00"
    assert rows[0].bbox["width"] > 0


def test_blank_or_invalid_pdf_rejected():
    with pytest.raises(UnsupportedDocumentError):
        extract_pdf(b"not a pdf")


def test_local_embedder_dimensions():
    pytest.importorskip("fastembed")
    from app.embeddings import EmbeddingService

    service = EmbeddingService()
    assert len(service.embed_query("balance sheet")) == service.dimensions
    assert len(service.embed_document("Ind AS 1 presentation")) == service.dimensions
