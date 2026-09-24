# Satya-Lekha Document AI

Google Document AI ingestion and financial-document normalization service for Satya-Lekha AI.

## Current pipeline

```
PDF / image
   ↓
Google Document AI
   ↓
OCR + layout + tables + entities
   ↓
Financial document classification
   ↓
Balance Sheet / P&L / Cash Flow / Notes classification
   ↓
Financial table normalization
   ↓
PostgreSQL-ready document/fact model
   ↓
Regulatory RAG contract (pgvector-ready)
```

## Components

- `app/document_ai.py` — Google Document AI processor integration.
- `app/normalizer.py` — converts Document AI output into stable JSON.
- `app/classifier.py` — deterministic financial-document classification baseline.
- `app/financial_normalizer.py` — monetary parsing and statement-section grouping.
- `app/models.py` — SQLAlchemy models for documents and financial facts.
- `app/db.py` — PostgreSQL session/health helpers.
- `app/rag.py` — retrieval contract for regulatory evidence.
- `app/schema.sql` — pgvector regulation-chunk schema.
- `docker-compose.postgres.yml` — local PostgreSQL + pgvector.

## Configuration

Copy `.env.example` to `.env`:

```env
GOOGLE_CLOUD_PROJECT=your-project
DOCUMENT_AI_LOCATION=us
DOCUMENT_AI_PROCESSOR_ID=your-processor-id
MAX_UPLOAD_MB=20
DATABASE_URL=postgresql+psycopg://satya:satya@localhost:5432/satya_lekha
```

Authenticate Google Cloud locally:

```bash
gcloud auth application-default login
```

Start PostgreSQL:

```bash
docker compose -f docker-compose.postgres.yml up -d
```

Install and run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs

## Process a document

```bash
curl -X POST http://localhost:8000/api/v1/documents/process \
  -F "file=@annual-report.pdf"
```

The response now includes:

- extracted text
- pages and tables
- Document AI entities
- document classification and confidence
- normalized financial table rows
- basic asset/liability/equity/income/expense grouping
- source-page traceability

The classifier is intentionally a transparent baseline. It should be evaluated against a labeled corpus of Indian annual reports before being used for compliance decisions.

## PostgreSQL model

The initial model stores:

- documents
- document classification
- raw text
- normalized JSON
- financial facts
- source page/text for traceability

Regulatory chunks are designed for PostgreSQL + pgvector. The production retrieval layer should apply jurisdiction/regulator/framework/effective-date filters before semantic retrieval.

## Regulatory RAG

The RAG layer is deliberately evidence-first. A production finding should carry:

```text
finding
→ extracted financial fact
→ applicable rule/chunk
→ source URI
→ effective date
→ reasoning
→ confidence
```

Do not use an LLM as the authoritative source of a regulation. Regulatory text should be ingested from authoritative sources and retained with provenance/version metadata.

## Testing

```bash
pytest -q
```

## Production hardening

Before exposing this service publicly, add authentication/authorization, object storage, asynchronous processing, migrations (Alembic), audit logging, retention/deletion controls, request tracing, rate limits, tenant isolation, secrets management, encryption, and a labeled evaluation set.

Never commit service-account keys or database credentials.
