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


def normalize_document(document: Any) -> dict:
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
