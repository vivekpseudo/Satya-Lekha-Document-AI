# Satya-Lekha Document AI

Reads the documents of an Indian company's annual filing — financial statements, Directors' Report, Auditor's
Report, AGM notice, invoices — and checks them against the Companies Act, 2013 and related rules. Every check is
a deterministic rule whose finding quotes the text or figures it relied on.

It answers questions such as: do both years of the balance sheet balance? Does the cash flow statement tie to the
balance sheet? Does the Directors' Report agree with the statements about the year's result? Is the UDIN on the
audit report? Is the statutory auditor billing the company for work s.144 restricts?

> **A finding is a pointer for a reviewer, not an opinion.** A passing result means documents are consistent with
> each other, not that they are right. The legal references come from the authors' reading of the law and have
> **not** been reviewed by a qualified professional. See [Limitations](#limitations).

## What it does

```
PDF ──► extraction ──► classification ──► normalisation ──► rules ──► findings ──► PDF report
        (local or        (9 document        (rows, both       (per-document  evidence +      (print /
         Google)          types)             years, bboxes)    per-document   regulatory       export)
                                                              and cross-
                                                              document)
```

- **Extraction** reads text, tables and positions from a PDF. The default is local ([PyMuPDF](https://pymupdf.readthedocs.io/)),
  so no cloud account is needed. Google Document AI can be used instead for scans and images.
- **Classification** labels each document: `balance_sheet`, `profit_and_loss`, `cash_flow`, `notes_to_accounts`,
  `directors_report`, `auditors_report`, `agm_notice`, `invoice` or `other`.
- **Rules** run per document and across documents. The full list is in [docs/RULES.md](docs/RULES.md).
- **Regulatory evidence** (optional): regulation text you load is embedded (locally by default) and stored in
  PostgreSQL + pgvector, so each finding can cite candidate passages with their source and effective dates.
- **Web app** shows the PDF with highlights on the evidence, the findings, a control score, and a printable or
  downloadable PDF report.

## Quick start (local)

Requirements: Python 3.11+, Node 20.19+ or 22.12+ (a Vite requirement), and Docker (for PostgreSQL + pgvector).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                                  # defaults work for local use
docker compose -f docker-compose.postgres.yml up -d   # PostgreSQL 16 + pgvector on :5432
python -m app.init_db                                 # creates the tables and the vector index
uvicorn app.main:app --reload                         # API on http://localhost:8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev                                           # UI on http://localhost:5173
```

API docs: <http://localhost:8000/docs>. Health check: `curl localhost:8000/health`.

The first time regulation text is embedded, the local embedding model (about 130 MB) is downloaded from Hugging Face.

> **Do not initialise the database with `psql -f app/schema.sql`.** The file hard-codes a 768-dimension vector
> column, while the default local model produces 384. `python -m app.init_db` sizes the column from
> `EMBEDDING_DIMENSIONS`.

### Try it

Upload documents in the web app, or call the API directly:

```bash
curl -X POST localhost:8000/api/v1/documents/process -F "file=@annual-report.pdf"
```

Upload several documents of the same filing in one session (for example the statements, the Directors' Report, the
Auditor's Report and the notice). From the second upload the app also runs the **cross-document checks** and
shows them with the document's own findings.

## Configuration

Settings come from environment variables or `.env` (see [.env.example](.env.example)).

| Variable | Default | Purpose |
|---|---|---|
| `EXTRACTOR` | `local` | `local` (PyMuPDF, text-based PDFs) or `google` (Document AI: also scans and images) |
| `EMBEDDER` | `local` | `local` (fastembed, ONNX) or `google` (Vertex AI) |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | For Google use `gemini-embedding-001` |
| `EMBEDDING_DIMENSIONS` | `384` | Must match the model. Use `768` with `gemini-embedding-001` |
| `DATABASE_URL` | local PostgreSQL | `postgresql+psycopg://user:password@host:5432/db` |
| `MAX_UPLOAD_MB` | `20` | Upload size limit |
| `AUTH_SECRET` | built-in default (local only) | Signs login tokens. **Required for Docker**: compose refuses to start without it. Use `openssl rand -hex 32` |
| `CORS_ORIGINS` | the Vite dev origins | Comma-separated origins allowed to call the API. Not needed when the UI is served by the API itself |
| `GOOGLE_CLOUD_PROJECT`, `DOCUMENT_AI_LOCATION`, `DOCUMENT_AI_PROCESSOR_ID`, `GOOGLE_CLOUD_LOCATION` | empty | Only for `google` mode |
| `FASTEMBED_CACHE_PATH` | system temp dir | Where the local embedding model is cached |
| `SATYA_LEKHA_LOGO_PATH` | none | Optional logo for the PDF report |
| `APP_IMAGE`, `APP_PORT_BIND`, `POSTGRES_NETWORK`, `PROXY_NETWORK` | see `.env.example` | Docker Compose only: the image to run, where to publish the port, and the existing networks to join |

**Changing the embedding model or dimensions** means the existing `regulation_chunks` vectors no longer fit: drop
that table, run `python -m app.init_db`, and ingest the regulations again. Vectors from different models cannot
be mixed.

### Using Google Document AI

Set `EXTRACTOR=google` and the three `GOOGLE_*` values. Document AI does **not** accept API keys: it needs a
service-account key (or Application Default Credentials). Grant the service account *Document AI API User*
(and *Vertex AI User* for `EMBEDDER=google`), then either:

```bash
gcloud auth application-default login                              # local development
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json  # servers
```

Both Layout Parser and OCR / Form Parser processors are understood. Layout Parser returns no bounding boxes, so
evidence highlights on the PDF are unavailable in that mode.

Never commit service-account keys or `.env`. Both are in `.gitignore`.

## Documents and rules

| Document | Rules | Highlights |
|---|---|---|
| Balance sheet | `FSBS-001`–`007`, `INDAS-FS-001` | both years balance, sub-totals and line items add up, Schedule III headings, note totals tie, signatures and UDIN |
| Profit and loss | `FSPL-001`–`005`, `FSX-001`, `DATA-QUALITY-001` | expense totals, profit before and after tax, EPS, reserves move by the year's result |
| Cash flow | `CFS-001`–`009` | arithmetic in both years, opening = prior closing, ties to the balance sheet and P&L |
| Directors' Report | `DIRREP-001`–`011` | s.134 disclosures, Board meeting count and 120-day gaps, annual return, signatures |
| Auditor's Report | `AUDREP-001`–`009` | opinion type, basis for opinion, s.143(3), CARO version, signature and UDIN |
| AGM notice | `NOTICE-001`–`010` | six-month deadline, 21 clear days, hours, business, proxies, auditor appointment |
| Invoice | `INV-001`–`008` | GST particulars, GSTIN check digit, PAN, totals, amount in words |
| Two or more documents | `XDOC-001`–`017` | company, year-end, auditor, dates, profit/loss wording, summary figures, address, papers, invoice cut-off |

Each finding is `PASS`, `FAIL` or `REVIEW`, with a severity, a confidence, and evidence: the quoted text or
figures with their document and page. A `REVIEW` means a person should look; there may be an innocent
explanation. Rules stay silent on documents they do not apply to.

See [docs/RULES.md](docs/RULES.md) for every rule. That file is generated from the code
(`python -m app.rule_docs`) and a test fails if it is stale.

## API

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness check |
| `POST /api/v1/documents/process` | Extract, classify and normalise one document (multipart `file`) |
| `POST /api/v1/documents/process-and-store` | The same, then store it and return findings |
| `POST /api/v1/compliance/evaluate` | Run the per-document rules on facts and text |
| `POST /api/v1/compliance/cross-check` | Compare two or more documents of one filing |
| `POST /api/v1/compliance/report` | Build the PDF compliance report |
| `POST /api/v1/regulations` | Embed and store a regulation passage |
| `POST /api/v1/regulations/search` | Search stored regulation passages |

Examples:

```bash
# per-document rules
curl -X POST localhost:8000/api/v1/compliance/evaluate -H 'content-type: application/json' -d '{
  "document_type": "balance_sheet",
  "facts": [{"label": "Total assets", "value": "1000"},
            {"label": "Total liabilities", "value": "400"},
            {"label": "Total equity", "value": "600"}],
  "retrieve_regulations": false
}'

# cross-document checks (two or more documents; "text" is the extracted text)
curl -X POST localhost:8000/api/v1/compliance/cross-check -H 'content-type: application/json' -d '{
  "documents": [
    {"document_type": "directors_report", "document_name": "dr.pdf", "text": "..."},
    {"document_type": "auditors_report",  "document_name": "ar.pdf", "text": "..."}
  ]
}'

# load a regulation passage for evidence retrieval
curl -X POST localhost:8000/api/v1/regulations -H 'content-type: application/json' -d '{
  "regulation_id": "INDAS-1", "title": "Ind AS 1", "source_uri": "https://www.mca.gov.in",
  "content": "A balance sheet shall present total assets equal to total equity plus liabilities."
}'
```

`process` accepts PDFs only in `local` mode; PNG, JPEG and TIFF need `EXTRACTOR=google`. `facts` are the
extracted rows: each has a `label`, a `value`, and optionally `values` (every column, current year first),
`source_page` and `bbox`. The response of `process-and-store` already contains them.

Evidence retrieval attaches the closest regulation passages to each finding. It is a search, not a determination
of which regulation applies: deterministic rule metadata decides applicability.

## Project layout

```
app/
  main.py                 FastAPI routes
  config.py               settings
  local_extractor.py      PyMuPDF extraction (line-based rows, tables as fallback)
  document_ai.py          Google Document AI client
  normalizer.py           Document AI and Layout Parser output
  classifier.py           document type classification
  financial_normalizer.py amounts and row grouping
  rules_engine.py         engine, applicability, balance-sheet and revenue rules
  statement_rules.py      balance sheet, profit and loss, cross-statement rules
  cash_flow_rules.py      cash flow rules
  text_rules.py           Directors' Report and Auditor's Report rules
  notice_invoice_rules.py AGM notice and invoice rules
  cross_rules.py          cross-document checks
  rule_docs.py            generates docs/RULES.md and the rule metadata files
  regulatory_rag.py, embeddings.py   regulation storage and search (pgvector)
  report.py               PDF compliance report
  models.py, db.py, storage.py, schema.sql, init_db.py   persistence
frontend/                 React + Vite + TypeScript + Ant Design + PDF.js
docs/RULES.md             generated rule reference
tests/                    pytest suite
```

## Web app

- Pages: a **home** page explaining the features, **register** and **sign in** (full name, organization name, email,
  password, and a required tick for the [Terms & Conditions](frontend/src/Terms.tsx) page), the upload page, and
  **History**. History is a grid of the signed-in user's past reports (document name and date); *Open report* shows the
  report in a dialog. Only the finished report is stored, never the uploaded file.
- Accounts and history use `POST /api/v1/auth/register`, `/auth/login`, `GET /auth/me` and `/api/v1/reports`. The
  tables are created by `python -m app.init_db`. The document-processing endpoints themselves are not behind a login.
- Upload a PDF. The document renders with PDF.js; evidence from a selected finding is highlighted on the page,
  with numbered audit pins.
- The right-hand panel lists the findings. Selecting evidence jumps to its page.
- **Print report** and **Export PDF report** produce the same PDF from `POST /api/v1/compliance/report`.
- The control score is a summary of the findings (`PASS` 100%, `REVIEW` 50%, `FAIL` 0%), not an audit opinion.
- Documents uploaded in a session are remembered until the page is reloaded, so they can be cross-checked.

See [frontend/README.md](frontend/README.md).

## Testing

```bash
pytest -q                                   # backend
cd frontend && npx tsc -b && npm run build  # frontend type check and build
python -m app.rule_docs --check             # the rule reference is up to date
```

CI runs the backend tests on every push. The suite includes tests that break one figure at a time to prove each
rule can fail, and an end-to-end test that runs a generated PDF through extraction, classification and the rules.

### Adding a rule

1. Write the evaluator next to the related rules and add it to that module's rule list.
2. Register its ID in [app/rule_registry.py](app/rule_registry.py) (per-document rules).
3. Run `python -m app.rule_docs` to refresh [docs/RULES.md](docs/RULES.md).
4. Add tests: one that passes, and one that fails for each way the rule can fail.

## Deployment

Build the image on your machine, push it to your registry, and run it on the server with `docker compose` using the
image from the registry and a `.env` file. The server needs only `docker-compose.yml` and `.env`: no source code,
no build.

```bash
# your machine: set APP_IMAGE in .env (for example registry.example.com/satya-lekha-app:1.0.0), then
docker compose -f docker-compose.yml -f docker-compose.build.yml build
docker compose -f docker-compose.yml -f docker-compose.build.yml push

# the server: docker-compose.yml and .env in one directory
docker compose pull
docker compose up -d
```

| Guide | Covers |
|---|---|
| [customdeployment.md](customdeployment.md) | building and pushing the image, versions, CPU architecture |
| [DEPLOYMENT.md](DEPLOYMENT.md) | the server: networks, PostgreSQL (including sharing an existing server), `.env`, the reverse proxy, backups, updates and rollback, troubleshooting |

The default image contains the API and the built web app; the API serves the UI. PostgreSQL is not started by the
compose file: it must already exist on a Docker network that the app can join.

## Limitations

- **Accounts protect only the history pages.** Sign-in, per-user report history and the pages built on them are behind
  a login, but the document-processing, compliance and regulation endpoints are not: anyone who can reach the
  service can use them, including loading regulations. Do not expose it to the Internet as it is; put it behind a
  proxy with access control, and set a strong `AUTH_SECRET` (anyone who knows the secret can forge a login).
- **The rules check consistency and presence, not correctness or adequacy.** A document can pass every rule and
  still be wrong; a `REVIEW` can have an innocent explanation.
- **Legal references are unverified.** The rules encode the authors' reading of the Companies Act, 2013, SS-2, the
  Standards on Auditing, CARO, the CGST Rules and AS 3 / Ind AS 7. Have a qualified professional confirm them.
- **Local extraction reads text-based PDFs only.** Scans and images need `EXTRACTOR=google`. Layouts that differ
  a lot from Schedule III Division I, or cash flow statements using the direct method, may need rule changes.
- **Tested on a small corpus** of one company's documents, plus synthetic cases. No real cash flow statement
  has been tried.
- **Regulatory evidence is generic.** Each finding gets the passages closest to a generic query, not text chosen
  for that rule, and the regulation corpus must be loaded by you from authoritative sources.
- Session memory for cross-checks lives in the browser; nothing links stored documents to each other.
- Before wider use, add authentication, object storage for uploads, asynchronous processing, Alembic
  migrations, audit logging, rate limits, and a labelled evaluation set.
