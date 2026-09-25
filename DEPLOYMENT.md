# Satya-Lekha deployment

Designed for a **Hostinger KVM VPS with Docker and Nginx Proxy Manager (NPM)**.

## Architecture

```
Internet
   |
Nginx Proxy Manager
   | HTTPS -> HTTP
   v
frontend:80
   | /api/*
   v
backend:8000
   |
   +--> PostgreSQL + pgvector
   +--> Google Document AI
```

Only the frontend is attached to the NPM network. PostgreSQL and FastAPI stay on the private Docker network.

## 1. Create the shared NPM network

```bash
docker network create proxy
```

If NPM is not attached to it, find its container:

```bash
docker ps --format '{{.Names}}'
```

Then:

```bash
docker network connect proxy <npm-container-name>
```

If your existing NPM network has another name, set `PROXY_NETWORK` in `.env`.

## 2. Prepare the application

```bash
git clone https://github.com/vivekpseudo/Satya-Lekha-Document-AI.git
cd Satya-Lekha-Document-AI
mkdir -p secrets
```

Place the Google Cloud service-account key at:

```
secrets/google-service-account.json
```

Do not commit this file.

## 3. Configure environment

```bash
cp .env.example .env
nano .env
```

Set:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
DOCUMENT_AI_LOCATION=us
DOCUMENT_AI_PROCESSOR_ID=your-processor-id
POSTGRES_PASSWORD=use-a-long-random-password
PROXY_NETWORK=proxy
```

The frontend uses `VITE_API_BASE_URL=/api`, so the browser does not need a public FastAPI URL.

## 4. Start

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

There is deliberately **no host port mapping** for frontend, backend, or PostgreSQL.

## 5. Configure Nginx Proxy Manager

Create a Proxy Host:

- Domain Names: your Satya-Lekha domain, e.g. `satyalekha.example.com`
- Scheme: `http`
- Forward Hostname / IP: `frontend`
- Forward Port: `80`
- Block Common Exploits: enabled
- Websockets Support: enabled

The NPM container must share the external `proxy` network so Docker DNS can resolve `frontend`.

### SSL

In NPM:

1. Request a Let's Encrypt certificate.
2. Select the Satya-Lekha domain.
3. Enable **Force SSL**.
4. Enable HTTP/2 if desired.

TLS terminates at NPM.

## 6. Verify

Backend:

```bash
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"
```

Frontend-to-backend routing:

```bash
docker compose exec frontend wget -qO- http://backend:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Then open the HTTPS domain through NPM.

## 7. Updates

```bash
git pull
docker compose up -d --build
docker compose ps
```

## 8. Database backup

```bash
docker compose exec -T postgres pg_dump -U satya -d satya_lekha > satya_lekha_backup.sql
```

Keep backups outside the VPS too.

## 9. Security

Do not publicly expose:

- PostgreSQL `5432`
- FastAPI `8000`
- frontend `80`

NPM should be the public web entry point.

Before production use, add authentication/authorization, tenant isolation, object storage for uploaded PDFs, asynchronous Document AI jobs, Alembic migrations, centralized secrets, audit logging, backups, tracing, rate limiting, malware scanning, retention/deletion controls, and authoritative regulatory-source ingestion.

Persistent document viewing will require object storage or an access-controlled document-serving endpoint; the current upload flow can render the selected PDF locally in the browser during the session.
