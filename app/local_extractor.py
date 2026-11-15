"""Local (no cloud) PDF extraction using PyMuPDF.

Produces the same dict shape as ``app.normalizer.normalize_document`` so the
rest of the pipeline is unchanged. Works on text-based PDFs; scanned PDFs and
images need OCR, which is not bundled.
"""
from __future__ import annotations

from typing import Any

import pymupdf


class UnsupportedDocumentError(ValueError):
    pass


def _norm_bbox(rect: Any, width: float, height: float) -> dict | None:
    if rect is None:
        return None
    x0, y0, x1, y1 = (float(v) for v in tuple(rect)[:4])
    xs, ys = (x0 / width, x1 / width), (y0 / height, y1 / height)
    return {
        "x": xs[0], "y": ys[0],
        "width": xs[1] - xs[0], "height": ys[1] - ys[0],
        "vertices": [
            {"x": xs[0], "y": ys[0]}, {"x": xs[1], "y": ys[0]},
            {"x": xs[1], "y": ys[1]}, {"x": xs[0], "y": ys[1]},
        ],
    }


def _find_tables(page: Any) -> list[Any]:
    tables = page.find_tables().tables
    if not tables:  # statements often have no ruling lines
        tables = page.find_tables(strategy="text").tables
    return [t for t in tables if t.row_count >= 2 and t.col_count >= 2]


def _table_rows(table: Any, width: float, height: float) -> list[list[dict]]:
    extracted = table.extract()
    rows = []
    for row_obj, texts in zip(table.rows, extracted):
        cells = []
        for index, text in enumerate(texts):
            rect = row_obj.cells[index] if index < len(row_obj.cells) else None
            cells.append({
                "text": " ".join((text or "").split()),
                "bbox": _norm_bbox(rect, width, height),
            })
        rows.append(cells)
    return rows


def _inside(block: tuple, rects: list[Any]) -> bool:
    cx, cy = (block[0] + block[2]) / 2, (block[1] + block[3]) / 2
    return any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in rects)


def extract_pdf(content: bytes) -> dict:
    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
    except Exception as exc:  # corrupt / not a PDF
        raise UnsupportedDocumentError(f"Could not open PDF: {exc}") from exc

    pages, texts = [], []
    with doc:
        for number, page in enumerate(doc, start=1):
            width, height = page.rect.width, page.rect.height
            tables = _find_tables(page)
            table_rects = [t.bbox for t in tables]

            paragraphs = []
            for block in page.get_text("blocks", sort=True):
                if block[6] != 0 or _inside(block, table_rects):  # 0 = text block
                    continue
                text = " ".join(block[4].split())
                if text:
                    paragraphs.append({"text": text, "bbox": _norm_bbox(block[:4], width, height)})
                    texts.append(text)

            table_out = []
            for table in tables:
                rows = _table_rows(table, width, height)
                table_out.append({"header_rows": rows[:1], "body_rows": rows[1:]})
                texts.extend(" ".join(c["text"] for c in r if c["text"]) for r in rows)

            pages.append({"page_number": number, "paragraphs": paragraphs, "tables": table_out})

    if not "".join(texts).strip():
        raise UnsupportedDocumentError(
            "No extractable text found. This looks like a scanned PDF; local extraction needs OCR."
        )
    return {
        "text": "\n".join(texts),
        "page_count": len(pages),
        "pages": pages,
        "entities": [],
        "metadata": {"mime_type": "application/pdf", "processor_output": "local-pymupdf"},
    }
