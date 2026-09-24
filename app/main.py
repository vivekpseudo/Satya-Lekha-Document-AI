from fastapi import FastAPI, File, HTTPException, UploadFile

from app.config import get_settings
from app.document_ai import DocumentAIService
from app.normalizer import normalize_document

app = FastAPI(
    title="Satya-Lekha Document AI",
    version="0.1.0",
    description="Google Document AI ingestion service for Satya-Lekha.",
)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/documents/process")
async def process_document(file: UploadFile = File(...)) -> dict:
    settings = get_settings()

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported MIME type: {file.content_type}",
        )

    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_mb} MB limit.",
        )

    service = DocumentAIService(
        project_id=settings.google_cloud_project,
        location=settings.document_ai_location,
        processor_id=settings.document_ai_processor_id,
    )

    try:
        document = service.process(content, file.content_type)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Document AI processing failed: {exc}",
        ) from exc

    result = normalize_document(document)
    result["source"] = {
        "filename": file.filename,
        "mime_type": file.content_type,
        "size_bytes": len(content),
    }
    return result
