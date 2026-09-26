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


## Persistence and RAG APIs

### Store a processed document

`POST /api/v1/documents/process-and-store`

This runs Document AI + classification + normalization and persists the document and extracted financial facts in PostgreSQL.

### Index a regulatory source

`POST /api/v1/regulations`

The service generates a `gemini-embedding-001` retrieval-document embedding and stores it with the regulation metadata. The implementation uses 768 dimensions to keep the pgvector schema compact; Google's current embedding API supports controlling output dimensionality. citeturn0search1

### Search regulatory sources

`POST /api/v1/regulations/search`

The query is embedded as a retrieval query and searched with pgvector cosine distance. Results retain the regulation ID, source URI and effective dates so later compliance findings can cite the underlying source.

## Database setup

Run:

```bash
docker compose -f docker-compose.postgres.yml up -d
psql "$DATABASE_URL" -f app/schema.sql
```

The current database layer is a prototype. Add Alembic migrations before production deployment.


## Compliance rules engine

`POST /api/v1/compliance/evaluate`

The prototype rules engine evaluates normalized financial facts and returns structured findings:

- `PASS`
- `FAIL`
- `REVIEW`

Every finding carries a rule ID, severity, message, confidence and source evidence.

The initial rules are deliberately limited to structural/data-quality checks. Regulatory assertions must be linked to authoritative Ind AS/SEBI/RBI source material and effective dates before production compliance use.

## Classification evaluation

`tests/test_labeled_classifier_fixture.py` provides a small synthetic fixture to validate the classifier contract. It is **not** a substitute for a real annual-report corpus.

For meaningful classification evaluation, create a versioned dataset with document/page-level labels for:

- balance sheet
- statement of profit and loss
- cash flow statement
- notes to accounts
- accounting policies
- auditor report
- other schedules

Recommended metrics: macro F1, per-class precision/recall, confusion matrix, and abstention/review rate.

## Compliance + regulatory evidence

The compliance endpoint now optionally retrieves regulatory evidence for each rule.

`POST /api/v1/compliance/evaluate`

Each finding can contain financial evidence plus regulatory evidence: regulation ID, title, source text, source URI, effective dates, and similarity. Regulatory retrieval is filtered by the reporting date before vector similarity ranking, so future/expired chunks are excluded for historical reporting periods.

The current rule IDs remain prototype identifiers. Before production compliance use, populate their authoritative regulatory references and add rule-specific applicability conditions.

## Important design rule

Satya-Lekha must not treat vector similarity as proof that a regulation applies. Retrieval is evidence discovery; deterministic rule metadata decides jurisdiction, framework, statement type, and effective-date applicability. The regulatory source remains authoritative.


## Final PDF report

The system now generates a final compliance report as a PDF:

`POST /api/v1/compliance/report`

The report includes:

- A first-page executive summary with PASS / FAIL / REVIEW counts and interpretation

- company and source-document metadata
- document classification and confidence
- PASS / FAIL / REVIEW summary
- each compliance rule finding
- financial evidence and source pages
- retrieved regulatory evidence
- regulation IDs and source URIs
- effective dates
- confidence
- methodology and limitations

The PDF is generated with ReportLab and returned as `application/pdf`.


## Web application

The repository now includes a production-oriented frontend under `frontend/`:

- Vite
- React
- TypeScript
- Tailwind CSS
- Ant Design
- PDF.js document rendering
- page navigation
- Document AI evidence highlights
- clickable audit pins
- live compliance score
- FastAPI integration
- PDF compliance report export

Run locally:

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` when the API is not available at the default local backend.

## Docker Compose deployment

The root `docker-compose.yml` runs the complete application:

```
Browser
   ↓
Frontend / Nginx
   ↓ /api/*
FastAPI
   ↓
PostgreSQL + pgvector
   ↓
Regulatory evidence
```

It provides:

- PostgreSQL 16 + pgvector
- FastAPI backend
- React/Vite frontend served by Nginx
- health checks
- persistent PostgreSQL volume
- automatic database initialization
- Google Document AI credential mounting
- API reverse proxy

Configure:

```bash
cp .env.example .env
mkdir -p secrets
# place the Google service-account JSON at:
# secrets/google-service-account.json

docker compose up -d --build
```

The web application is available on `http://localhost:8080` by default.

See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment and production-hardening guidance.

### Environment

Required Google settings:

- `GOOGLE_CLOUD_PROJECT`
- `DOCUMENT_AI_LOCATION`
- `DOCUMENT_AI_PROCESSOR_ID`

Deployment settings:

- `POSTGRES_PASSWORD`
- `WEB_PORT`

Never commit `.env`, Google service-account credentials, database passwords, or other secrets.

## End-to-end architecture

```
                    Satya-Lekha Web
                         │
             ┌───────────┴───────────┐
             │                       │
       Document Upload          Compliance UI
             │                       │
             ▼                       ▼
       Google Document AI       Findings / Score
             │                       │
       OCR + Tables + Layout         │
             │                       │
             ▼                       │
     Financial Normalization         │
             │                       │
             ▼                       │
      PostgreSQL / pgvector          │
             │                       │
       ┌─────┴─────┐                 │
       ▼           ▼                 │
  Rules Engine   Regulatory RAG ─────┘
       │
       ▼
 PASS / FAIL / REVIEW
       │
       ▼
 PDF Compliance Report
```


## Production deployment

The repository can be deployed on a Linux VPS with Docker. The recommended production topology is:

```
Internet
   │
   ▼
Nginx Proxy Manager / Reverse Proxy
   │
   ├── https://satya-lekha.example.com
   │       ▼
   │   Frontend container (Nginx)
   │
   └── https://api.satya-lekha.example.com
           ▼
       FastAPI container
           │
           ├── PostgreSQL + pgvector
           ├── Google Document AI
           └── Regulatory/RAG data
```

### Prerequisites

Install the following on the deployment host:

- Ubuntu/Debian Linux
- Docker Engine
- Docker Compose v2
- Git
- Nginx Proxy Manager or another TLS reverse proxy
- At least 4 CPU cores and 8 GB RAM for the document-processing MVP
- Additional CPU/GPU resources are required when hosting local OCR/LLM models
- A persistent disk for PostgreSQL, uploaded documents, logs, and model/data assets

Verify:

```bash
docker --version
docker compose version
git --version
```

### 1. Clone the repository

```bash
git clone https://github.com/vivekpseudo/Satya-Lekha-Document-AI.git
cd Satya-Lekha-Document-AI
```

### 2. Configure production environment

Create the environment file:

```bash
cp .env.example .env
nano .env
```

Set production values for at least:

```env
GOOGLE_CLOUD_PROJECT=<google-cloud-project-id>
DOCUMENT_AI_LOCATION=<processor-location>
DOCUMENT_AI_PROCESSOR_ID=<document-ai-processor-id>

POSTGRES_DB=satya_lekha
POSTGRES_USER=satya
POSTGRES_PASSWORD=<strong-random-password>

WEB_PORT=8080
```

Do not commit `.env`.

Generate a strong database password, for example:

```bash
openssl rand -base64 32
```

### 3. Configure Google Document AI credentials

Create a production `secrets` directory outside version control:

```bash
mkdir -p secrets
chmod 700 secrets
```

Copy the Google service-account JSON into:

```
secrets/google-service-account.json
```

Set restrictive permissions:

```chmod 600 secrets/google-service-account.json```

The service account should have only the Google Cloud permissions required by Document AI. Never put the JSON credentials in GitHub, `.env`, Docker images, or public object storage.

### 4. Configure the reverse proxy

Create DNS records pointing your domain/subdomains to the VPS.

Recommended:

```
satya-lekha.example.com      -> VPS_PUBLIC_IP
api.satya-lekha.example.com  -> VPS_PUBLIC_IP
```

In Nginx Proxy Manager create:

**Frontend proxy host**

- Domain: `satya-lekha.example.com`
- Forward host: the Docker host IP
- Forward port: `8080`
- Enable WebSocket Support if required by the frontend
- Issue a Let's Encrypt certificate
- Force SSL

**API proxy host**

- Domain: `api.satya-lekha.example.com`
- Forward host: the Docker host IP
- Forward port: the published FastAPI port configured by `docker-compose.yml`
- Enable WebSocket Support if required
- Issue a Let's Encrypt certificate
- Force SSL

For a single-domain deployment, the frontend can also proxy `/api` to FastAPI internally. Do not expose PostgreSQL directly to the Internet.

### 5. Configure the frontend API URL

Before building the frontend, set the production API URL in the environment used by the frontend build.

Example:

```env
VITE_API_BASE_URL=https://api.satya-lekha.example.com
```

For a same-origin reverse-proxy setup, use:

```env
VITE_API_BASE_URL=/api
```

Rebuild the frontend after changing any `VITE_*` variable because Vite injects these values at build time.

### 6. Build and start the stack

```bash
docker compose pull
docker compose build --no-cache
docker compose up -d
```

Check container state:

```bash
docker compose ps
```

Inspect logs:

```bash
docker compose logs -f
```

Backend only:

```bash
docker compose logs -f backend
```

Frontend only:

```bash
docker compose logs -f frontend
```

### 7. Verify health

From the server:

```bash
curl -f http://localhost:<backend-port>/health
```

Verify the web application through the HTTPS domain:

```
https://satya-lekha.example.com
```

Verify the API:

```
https://api.satya-lekha.example.com/docs
```

The exact backend health endpoint/port should match the current FastAPI application and `docker-compose.yml`.

### 8. Initialize and verify the database

For a fresh environment:

```bash
docker compose exec backend python -m pytest -q
```

Verify PostgreSQL:

```bash
docker compose exec postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

For production, prefer Alembic migrations over manually applying `app/schema.sql` once migrations are introduced.

### 9. Production validation checklist

Run an end-to-end test with:

1. A native-text annual report PDF.
2. A scanned PDF requiring OCR.
3. A Balance Sheet.
4. A Cash Flow Statement.
5. A Director's Report.
6. A document containing a financial table spanning multiple pages.
7. A regulatory evidence search.
8. A compliance evaluation.
9. A generated PDF compliance report.

Confirm that every finding contains:

```
finding
  -> rule_id
  -> source document
  -> page/evidence reference
  -> extracted value
  -> regulatory evidence
  -> source URI
  -> effective date
  -> model/version metadata
```

### 10. Backups

At minimum, back up:

- PostgreSQL data
- uploaded/raw documents
- normalized document JSON
- regulatory corpus
- model/version metadata
- audit logs

The PostgreSQL volume used by Docker is persistent, but persistence is **not** the same as backup. Configure scheduled off-host backups and test restoration regularly.

Example database dump:

```bash
docker compose exec -T postgres pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  > backup-$(date +%F).sql
```

Do not store production backups in the public Git repository.

### 11. Updating the deployment

Pull the new version and recreate the affected containers:

```bash
git pull origin main
docker compose build
docker compose up -d
docker image prune -f
```

For schema changes, run the project's migration command before serving traffic.

### 12. Security requirements before production use

Do not treat the default Docker Compose stack as regulator-grade production by itself. Before processing sensitive financial records, add:

- Authentication and RBAC
- HTTPS-only external access
- API rate limiting
- strict CORS configuration
- request-size limits
- malware/file validation
- secret management
- encrypted backups
- network isolation for PostgreSQL and internal services
- centralized structured logging
- audit-log integrity protection
- dependency and container vulnerability scanning
- tenant/data isolation where multi-tenant access is introduced
- retention and deletion controls
- disaster recovery procedures
- versioned regulatory data with effective dates
- human review workflow for high-risk findings

### 13. Important architecture note

The current repository is the **Document AI / financial normalization foundation** of Satya-Lekha. The full production architecture described in the project design additionally requires separate services or modules for:

- Arelle/XBRL ingestion
- regulatory corpus ingestion and versioning
- deterministic compliance rules
- RAG retrieval
- anomaly detection
- immutable audit trails
- analyst review workflow
- OSINT monitoring
- local/open-source LLM inference

These components should be added incrementally rather than coupled into the document-ingestion container.

For the initial MVP, prioritize:

```
PDF/XBRL ingestion
   ↓
Balance Sheet extraction
   ↓
Cash Flow extraction
   ↓
Director's Report extraction
   ↓
Normalization
   ↓
XBRL ↔ PDF reconciliation
   ↓
Deterministic compliance checks
   ↓
Evidence-linked findings
```

This keeps the first production milestone measurable and preserves the source-traced design described in the project documentation. 
