from app.config import Settings
from app.local_extractor import UnsupportedDocumentError, extract_pdf
from app.normalizer import normalize_document

LOCAL_MIME_TYPES = {"application/pdf"}
GOOGLE_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}


def allowed_mime_types(settings: Settings) -> set[str]:
    return LOCAL_MIME_TYPES if settings.extractor == "local" else GOOGLE_MIME_TYPES


def extract_document(content: bytes, mime_type: str, settings: Settings) -> dict:
    """Return the normalized document dict using the configured extractor."""
    if settings.extractor == "local":
        return extract_pdf(content)

    from app.document_ai import DocumentAIService  # lazy: needs Google credentials

    service = DocumentAIService(
        project_id=settings.google_cloud_project,
        location=settings.document_ai_location,
        processor_id=settings.document_ai_processor_id,
    )
    return normalize_document(service.process(content, mime_type))


__all__ = ["extract_document", "allowed_mime_types", "UnsupportedDocumentError"]
