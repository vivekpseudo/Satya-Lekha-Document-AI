from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.classifier import classify_document
from app.config import get_settings
from app.document_ai import DocumentAIService
from app.financial_normalizer import classify_statement_rows, normalize_table_rows
from app.normalizer import normalize_document
from app.db import get_db
from app.storage import save_processed_document
from app.api_models import RegulationIn, RegulationSearchIn
from app.regulatory_rag import add_regulation, retrieve_regulations, regulation_provider
from app.rules_engine import ComplianceRulesEngine, RuleContext
from app.finding_models import ComplianceEvaluateRequest, ComplianceFindingResponse

app = FastAPI(
    title="Satya-Lekha Document AI",
    version="0.2.0",
    description="Google Document AI ingestion, financial classification and normalization service.",
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
        raise HTTPException(status_code=415, detail=f"Unsupported MIME type: {file.content_type}")

    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB limit.")

    service = DocumentAIService(
        project_id=settings.google_cloud_project,
        location=settings.document_ai_location,
        processor_id=settings.document_ai_processor_id,
    )

    try:
        document = service.process(content, file.content_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Document AI processing failed: {exc}") from exc

    result = normalize_document(document)
    classification = classify_document(result["text"])

    normalized_tables = []
    for page in result["pages"]:
        for table in page["tables"]:
            rows = normalize_table_rows(table["body_rows"], page["page_number"])
            groups = classify_statement_rows(rows, classification.document_type)
            normalized_tables.append({
                "page_number": page["page_number"],
                "header_rows": table["header_rows"],
                "rows": [
                    {
                        "label": row.label,
                        "values": [str(value) if value is not None else None for value in row.values],
                        "source_page": row.source_page,
                    }
                    for row in rows
                ],
                "groups": {
                    group: [row.label for row in grouped_rows]
                    for group, grouped_rows in groups.items()
                },
            })

    result["classification"] = {
        "document_type": classification.document_type,
        "confidence": classification.confidence,
        "signals": classification.signals,
    }
    result["financial_normalization"] = {
        "tables": normalized_tables,
    }
    result["source"] = {
        "filename": file.filename,
        "mime_type": file.content_type,
        "size_bytes": len(content),
    }
    return result


@app.post("/api/v1/documents/process-and-store")
async def process_and_store(
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
) -> dict:
    result = await process_document(file)
    document = save_processed_document(
        session,
        filename=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        normalized=result,
    )
    return {
        "document_id": document.id,
        "document_type": document.document_type,
        "classification_confidence": float(document.classification_confidence),
        "financial_fact_count": len(document.facts),
    }


@app.post("/api/v1/regulations")
def ingest_regulation(
    payload: RegulationIn,
    session: Session = Depends(get_db),
) -> dict:
    add_regulation(
        session,
        regulation_id=payload.regulation_id,
        title=payload.title,
        content=payload.content,
        source_uri=payload.source_uri,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    return {"status": "indexed", "regulation_id": payload.regulation_id}


@app.post("/api/v1/regulations/search")
def search_regulations(
    payload: RegulationSearchIn,
    session: Session = Depends(get_db),
) -> dict:
    return {
        "query": payload.query,
        "results": retrieve_regulations(
            session,
            query=payload.query,
            top_k=payload.top_k,
        ),
    }


@app.post("/api/v1/compliance/evaluate")
def evaluate_compliance(\n    payload: ComplianceEvaluateRequest,\n    session: Session = Depends(get_db),\n) -> list[ComplianceFindingResponse]:
    context = RuleContext(
        document_type=payload.document_type,
        facts=payload.facts,
        jurisdiction=payload.jurisdiction,
        framework=payload.framework,
        reporting_date=payload.reporting_date,
    )
    provider = (
        regulation_provider(
            session,
            as_of=payload.reporting_date,
            top_k=payload.regulation_top_k,
        )
        if payload.retrieve_regulations
        else None
    )
    return ComplianceRulesEngine().evaluate(context, regulation_provider=provider)
