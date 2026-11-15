from typing import Any


def _anchor_text(document: Any, anchor: Any) -> str:
    if not anchor or not anchor.text_segments:
        return ""
    parts = []
    for segment in anchor.text_segments:
        start = int(segment.start_index or 0)
        end = int(segment.end_index)
        parts.append(document.text[start:end])
    return "".join(parts)


def _bbox(layout: Any) -> dict | None:
    poly = getattr(layout, "bounding_poly", None)
    if not poly:
        return None
    vertices = []
    normalized = getattr(poly, "normalized_vertices", None) or []
    if normalized:
        vertices = [{"x": float(v.x), "y": float(v.y)} for v in normalized]
    else:
        vertices = [
            {"x": float(v.x), "y": float(v.y)}
            for v in (getattr(poly, "vertices", None) or [])
        ]
    if not vertices:
        return None
    xs = [v["x"] for v in vertices]
    ys = [v["y"] for v in vertices]
    return {
        "x": min(xs),
        "y": min(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
        "vertices": vertices,
    }


def _layout_item(document: Any, layout: Any) -> dict:
    return {
        "text": _anchor_text(document, getattr(layout, "text_anchor", None)),
        "bbox": _bbox(layout),
    }


def _block_text(block: Any) -> str:
    """Flatten the text of a Layout Parser block (text, list or nested blocks)."""
    parts: list[str] = []
    text_block = getattr(block, "text_block", None)
    if text_block is not None:
        if getattr(text_block, "text", ""):
            parts.append(text_block.text)
        for child in getattr(text_block, "blocks", None) or []:
            parts.append(_block_text(child))
    list_block = getattr(block, "list_block", None)
    if list_block is not None:
        for entry in getattr(list_block, "list_entries", None) or []:
            for child in getattr(entry, "blocks", None) or []:
                parts.append(_block_text(child))
    return " ".join(part for part in parts if part)


def _cell_text(cell: Any) -> str:
    return " ".join(
        part for part in (_block_text(b) for b in (getattr(cell, "blocks", None) or [])) if part
    )


def _block_page(block: Any) -> int:
    span = getattr(block, "page_span", None)
    start = int(getattr(span, "page_start", 0) or 0)
    return start or 1


def _layout_rows(rows: Any) -> list[list[dict]]:
    return [
        [{"text": _cell_text(cell), "bbox": None} for cell in row.cells]
        for row in rows
    ]


def _walk_layout_blocks(blocks: Any, pages: dict[int, dict], texts: list[str]) -> None:
    for block in blocks or []:
        page = pages.setdefault(
            _block_page(block), {"page_number": _block_page(block), "paragraphs": [], "tables": []}
        )
        table_block = getattr(block, "table_block", None)
        if table_block is not None and (
            getattr(table_block, "body_rows", None) or getattr(table_block, "header_rows", None)
        ):
            page["tables"].append({
                "header_rows": _layout_rows(table_block.header_rows),
                "body_rows": _layout_rows(table_block.body_rows),
            })
            for row in list(table_block.header_rows) + list(table_block.body_rows):
                texts.append(" ".join(t for t in (_cell_text(c) for c in row.cells) if t))
            continue
        text = _block_text(block)
        if text:
            page["paragraphs"].append({"text": text, "bbox": None})
            texts.append(text)
        # Nested blocks are already flattened by _block_text; only recurse for
        # containers that _block_text does not cover.


def _normalize_layout_document(document: Any) -> dict:
    pages: dict[int, dict] = {}
    texts: list[str] = []
    _walk_layout_blocks(document.document_layout.blocks, pages, texts)
    ordered = [pages[number] for number in sorted(pages)]
    return {
        "text": document.text or "\n".join(texts),
        "page_count": len(ordered),
        "pages": ordered,
        "entities": [],
        "metadata": {"mime_type": document.mime_type, "processor_output": "layout"},
    }


def _has_layout_blocks(document: Any) -> bool:
    layout = getattr(document, "document_layout", None)
    return bool(layout and getattr(layout, "blocks", None))


def normalize_document(document: Any) -> dict:
    # Layout Parser processors populate document_layout instead of pages[].tables
    # and leave document.text empty.
    if _has_layout_blocks(document):
        return _normalize_layout_document(document)

    pages = []

    for page_number, page in enumerate(document.pages, start=1):
        paragraphs = [_layout_item(document, paragraph.layout) for paragraph in page.paragraphs]

        tables = []
        for table in page.tables:
            header_rows = [
                [_layout_item(document, cell.layout) for cell in row.cells]
                for row in table.header_rows
            ]
            body_rows = [
                [_layout_item(document, cell.layout) for cell in row.cells]
                for row in table.body_rows
            ]
            tables.append({
                "header_rows": header_rows,
                "body_rows": body_rows,
            })

        pages.append({
            "page_number": page_number,
            "paragraphs": paragraphs,
            "tables": tables,
        })

    entities = [
        {
            "type": entity.type_,
            "mention_text": entity.mention_text,
            "confidence": entity.confidence,
            "bbox": _bbox(entity.page_anchor.page_refs[0].bounding_poly)
            if getattr(entity, "page_anchor", None)
            and getattr(entity.page_anchor, "page_refs", None)
            else None,
        }
        for entity in document.entities
    ]

    return {
        "text": document.text,
        "page_count": len(pages),
        "pages": pages,
        "entities": entities,
        "metadata": {
            "mime_type": document.mime_type,
        },
    }
