# Satya-Lekha deployment

## Docker Compose

The root docker-compose.yml deploys:

- PostgreSQL 16 with pgvector
- FastAPI backend
- Vite/React frontend served by Nginx
- Nginx reverse proxy from the frontend to backend /api/* routes

### 1. Prepare Google credentials

Create a Google Cloud service account with access to Document AI and provide its JSON key at:

secrets/google-service-account.json

Do not commit this file.

For production, prefer a platform secret/identity mechanism instead of a long-lived service-account key.

### 2. Configure environment

Copy .env.example to .env and set at minimum:

    GOOGLE_CLOUD_PROJECT=your-project-id
    DOCUMENT_AI_LOCATION=us
    DOCUMENT_AI_PROCESSOR_ID=your-processor-id
    POSTGRES_PASSWORD=use-a-long-random-password
    WEB_PORT=8080

### 3. Start

    mkdir -p secrets
    docker compose up -d --build

Open http://localhost:8080

Direct backend Swagger, when exposed locally, is available at http://localhost:8000/docs.

### 4. Logs and status

    docker compose ps
    docker compose logs -f backend
    docker compose logs -f frontend

Stop:

    docker compose down

Data persists in the postgres_data volume.

## Production notes

Put TLS in front of the frontend container using your existing Nginx/Caddy/load balancer. Do not expose PostgreSQL publicly.

Before production use, add:

- authentication and authorization
- tenant isolation
- object storage for uploaded PDFs
- asynchronous Document AI jobs
- Alembic migrations
- centralized secrets
- structured audit logging
- backup/restore
- request tracing
- rate limiting
- malware/file scanning
- retention/deletion controls
- authoritative regulatory source ingestion
