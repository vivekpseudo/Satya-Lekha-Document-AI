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


def normalize_document(document: Any) -> dict:
    pages = []

    for page_number, page in enumerate(document.pages, start=1):
        paragraphs = [
            _anchor_text(document, paragraph.layout.text_anchor)
            for paragraph in page.paragraphs
        ]

        tables = []
        for table in page.tables:
            header_rows = [
                [
                    _anchor_text(document, cell.layout.text_anchor)
                    for cell in row.cells
                ]
                for row in table.header_rows
            ]
            body_rows = [
                [
                    _anchor_text(document, cell.layout.text_anchor)
                    for cell in row.cells
                ]
                for row in table.body_rows
            ]
            tables.append(
                {
                    "header_rows": header_rows,
                    "body_rows": body_rows,
                }
            )

        pages.append(
            {
                "page_number": page_number,
                "paragraphs": paragraphs,
                "tables": tables,
            }
        )

    entities = [
        {
            "type": entity.type_,
            "mention_text": entity.mention_text,
            "confidence": entity.confidence,
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
