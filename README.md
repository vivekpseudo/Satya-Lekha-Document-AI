# Satya-Lekha Document AI

Google Document AI ingestion service for Satya-Lekha AI.

## Flow

PDF/image → Google Document AI → normalized JSON → downstream compliance/rules engine.

This service deliberately separates document extraction from regulatory reasoning.

## Requirements

- Python 3.11+
- Google Cloud project with the Document AI API enabled
- A Document AI processor
- Google Application Default Credentials

## Configuration

Copy `.env.example` to `.env`:

```env
GOOGLE_CLOUD_PROJECT=your-project
DOCUMENT_AI_LOCATION=us
DOCUMENT_AI_PROCESSOR_ID=your-processor-id
MAX_UPLOAD_MB=20
```

For local development:

```bash
gcloud auth application-default login
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs

## API

### POST /api/v1/documents/process

Multipart field: `file`

```bash
curl -X POST http://localhost:8000/api/v1/documents/process \
  -F "file=@annual-report.pdf"
```

Returns extracted full text, per-page paragraphs/tables, entities, and source metadata.

## Docker

```bash
docker build -t satya-lekha-document-ai .
docker run --rm -p 8000:8000 \
  -e GOOGLE_CLOUD_PROJECT=your-project \
  -e DOCUMENT_AI_LOCATION=us \
  -e DOCUMENT_AI_PROCESSOR_ID=your-processor-id \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  satya-lekha-document-ai
```

## Production hardening

Before exposing this service publicly, add application authentication/authorization, object storage for large documents, asynchronous processing, audit logging, retention/deletion controls, request tracing, rate limits, tenant isolation, and secret management. Never commit service-account keys.
