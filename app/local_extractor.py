"""Local (no cloud) PDF extraction using PyMuPDF.

Produces the same dict shape as ``app.normalizer.normalize_document`` so the
rest of the pipeline is unchanged. Works on text-based PDFs; scanned PDFs and
images need OCR, which is not bundled.
"""
from __future__ import annotations

import re
from collections import Counter
from statistics import median
from typing import Any

import pymupdf

_AMOUNT = re.compile(r"^\(?-?[\d,]+(\.\d+)?\)?$")
_DASHES = {"-", "\u2013", "\u2014"}
_SMALL_INT = re.compile(r"^\d{1,2}$")
_HEADER = re.compile(
    r"particulars|as at|as on|year ended|\bended\b|\bmarch\b|note no|31st|\bdate\b|\bamount\b"
    r"|\bDIN\b|\bUDIN\b|\bFRN\b|\bCIN\b|M\.?\s?No|proprietor|membership",
    re.I,
)


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


def _visual_lines(words: list[tuple]) -> list[list[tuple]]:
    """Group words that share a baseline into visual lines, left to right."""
    if not words:
        return []
    tol = 0.5 * median(w[3] - w[1] for w in words)
    ordered = sorted(words, key=lambda w: (w[1] + w[3]) / 2)
    lines: list[list[tuple]] = []
    centre = None
    for word in ordered:
        c = (word[1] + word[3]) / 2
        if centre is not None and abs(c - centre) <= tol:
            lines[-1].append(word)
            centre = (centre * (len(lines[-1]) - 1) + c) / len(lines[-1])
        else:
            lines.append([word])
            centre = c
    return [sorted(line, key=lambda w: w[0]) for line in lines]


def _join_tokens(tokens: list[dict]) -> list[dict]:
    """Repair amounts split by glyph spacing ("5 3,274") or a detached minus sign."""
    out: list[dict] = []
    for tok in tokens:
        prev = out[-1] if out else None
        if prev and _AMOUNT.match(prev["t"]) and _AMOUNT.match(tok["t"]) and tok["x0"] - prev["x1"] < 6:
            prev.update(t=prev["t"] + tok["t"], x1=tok["x1"], y0=min(prev["y0"], tok["y0"]), y1=max(prev["y1"], tok["y1"]))
        elif (
            prev and prev["t"] in _DASHES and _AMOUNT.match(tok["t"])
            and not tok["t"].startswith("-") and tok["x0"] - prev["x1"] < 12
        ):
            prev.update(t="-" + tok["t"], x1=tok["x1"], y0=min(prev["y0"], tok["y0"]), y1=max(prev["y1"], tok["y1"]))
        else:
            out.append(dict(tok))
    return out


def _is_value(text: str) -> bool:
    return text in _DASHES or bool(_AMOUNT.match(text))


def _statement_rows(page: Any) -> list[dict]:
    """Reconstruct label + amount rows from word positions (works without ruling lines)."""
    width, height = page.rect.width, page.rect.height
    rows = []
    for line in _visual_lines(page.get_text("words")):
        tokens = _join_tokens(
            [{"t": w[4], "x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3]} for w in line]
        )
        split = len(tokens)
        while split > 0 and _is_value(tokens[split - 1]["t"]):
            split -= 1
        label_tokens, value_tokens = tokens[:split], tokens[split:]
        label = " ".join(t["t"] for t in label_tokens).strip()
        if not label or not value_tokens or _HEADER.search(label):
            continue
        rows.append({"label": label, "label_tokens": label_tokens, "values": value_tokens})

    # Drop the "Note No." column: a leading 1-2 digit integer beyond the usual column count.
    counts = [len(r["values"]) - (1 if _SMALL_INT.match(r["values"][0]["t"]) else 0) for r in rows]
    if counts:
        usual = Counter(counts).most_common(1)[0][0]
        for row in rows:
            if len(row["values"]) > usual and _SMALL_INT.match(row["values"][0]["t"]):
                row["values"] = row["values"][1:]

        # A lone note number (e.g. "Short-Term Borrowings 4") carries no amount.
        rows = [
            r for r in rows
            if not (usual > 1 and len(r["values"]) == 1 and _SMALL_INT.match(r["values"][0]["t"]))
        ]
        # Merge a detached minus sign into the amount that follows it when there
        # are more tokens than columns ("-", "89,278" -> "-89,278").
        for row in rows:
            vals = row["values"]
            i = 0
            while len(vals) > usual and i < len(vals) - 1:
                if vals[i]["t"] in _DASHES and vals[i + 1]["t"] not in _DASHES:
                    vals[i + 1] = {**vals[i + 1], "t": "-" + vals[i + 1]["t"].lstrip("-"), "x0": vals[i]["x0"]}
                    del vals[i]
                else:
                    i += 1

    out = []
    for row in rows:
        lt = row["label_tokens"]
        box = (min(t["x0"] for t in lt), min(t["y0"] for t in lt),
               max(t["x1"] for t in lt), max(t["y1"] for t in lt))
        cells = [{"text": row["label"], "bbox": _norm_bbox(box, width, height)}]
        for tok in row["values"]:
            cells.append({
                "text": tok["t"],
                "bbox": _norm_bbox((tok["x0"], tok["y0"], tok["x1"], tok["y1"]), width, height),
            })
        out.append(cells)
    return out


def _inside(block: tuple, rects: list[Any]) -> bool:
    cx, cy = (block[0] + block[2]) / 2, (block[1] + block[3]) / 2
    return any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in rects)


def extract_pdf(content: bytes) -> dict:
    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
    except Exception as exc:  # corrupt / not a PDF
        raise UnsupportedDocumentError(f"Could not open PDF: {exc}") from exc

    pages, texts, page_texts = [], [], []
    with doc:
        for number, page in enumerate(doc, start=1):
            page_start = len(texts)
            width, height = page.rect.width, page.rect.height
            statement = _statement_rows(page)
            # Prefer line reconstruction; fall back to PyMuPDF's table finder.
            tables = [] if len(statement) >= 2 else _find_tables(page)
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
            if len(statement) >= 2:
                table_out.append({"header_rows": [], "body_rows": statement})
            for table in tables:
                rows = _table_rows(table, width, height)
                table_out.append({"header_rows": rows[:1], "body_rows": rows[1:]})
                texts.extend(" ".join(c["text"] for c in r if c["text"]) for r in rows)

            pages.append({"page_number": number, "paragraphs": paragraphs, "tables": table_out})
            page_texts.append("\n".join(texts[page_start:]))

    if not "".join(texts).strip():
        raise UnsupportedDocumentError(
            "No extractable text found. This looks like a scanned PDF; local extraction needs OCR."
        )
    return {
        # "\f" separates pages so rules can cite the page a phrase appears on.
        "text": "\f".join(page_texts),
        "page_count": len(pages),
        "pages": pages,
        "entities": [],
        "metadata": {"mime_type": "application/pdf", "processor_output": "local-pymupdf"},
    }
