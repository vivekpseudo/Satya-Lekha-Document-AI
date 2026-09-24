from sqlalchemy.orm import Session

from app.models import Document, FinancialFact


def save_processed_document(
    session: Session,
    *,
    filename: str | None,
    mime_type: str,
    normalized: dict,
) -> Document:
    classification = normalized["classification"]
    document = Document(
        filename=filename,
        mime_type=mime_type,
        document_type=classification["document_type"],
        classification_confidence=classification["confidence"],
        raw_text=normalized["text"],
        normalized_json=normalized,
    )
    session.add(document)
    session.flush()

    for table in normalized.get("financial_normalization", {}).get("tables", []):
        for row in table.get("rows", []):
            for index, value in enumerate(row.get("values", [])):
                if value is None:
                    continue
                session.add(
                    FinancialFact(
                        document_id=document.id,
                        statement_type=classification["document_type"],
                        section=_find_section(row["label"], table.get("groups", {})),
                        label=row["label"],
                        period=None,
                        value=value,
                        source_page=row.get("source_page"),
                        source_text=row["label"],
                    )
                )

    session.commit()
    session.refresh(document)
    return document


def _find_section(label: str, groups: dict) -> str:
    for section, labels in groups.items():
        if label in labels:
            return section
    return "other"
