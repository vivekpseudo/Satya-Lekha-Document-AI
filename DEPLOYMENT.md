# Deploying Satya-Lekha on a VPS

Docker Compose on a Linux VPS (written for a Hostinger KVM) behind **Nginx Proxy Manager (NPM)**, which
terminates TLS. To build an image once and run it elsewhere, see [customdeployment.md](customdeployment.md).

## Architecture

```
Internet
   │  HTTPS
   ▼
Nginx Proxy Manager ── network "proxy"
   │  HTTP
   ▼
app :8000   (FastAPI: the API and the built web app)
   │  network "postgres_default"
   ▼
PostgreSQL 16 + pgvector   (a separate container, not part of docker-compose.yml)
```

The `app` container serves both the API (`/api/...`, `/docs`, `/health`) and the web app (everything else), so
there is a single hostname and nothing to configure for CORS. PostgreSQL is **not** started by
`docker-compose.yml`: it must already exist on a Docker network that the compose file can join.

By default no Google account is needed: extraction and embeddings run inside the container.

> **There is no authentication.** Every endpoint is open, including regulation ingestion. Read
> [step 7](#7-lock-it-down) before the service is reachable from the Internet.

## 1. Create the Docker networks

`docker-compose.yml` declares both networks as `external`, so `docker compose up` fails with *"network … declared
as external, but could not be found"* if either is missing.

```bash
docker network create proxy                 # skip if NPM already has one; use its name as PROXY_NETWORK
docker network create postgres_default      # skip if your database is already on a network
```

If NPM is not on the `proxy` network yet:

```bash
docker ps --format '{{.Names}}'             # find the NPM container
docker network connect proxy <npm-container-name>
```

## 2. Provide PostgreSQL with pgvector

The database needs the [pgvector](https://github.com/pgvector/pgvector) extension. If you already run
PostgreSQL 16 with pgvector, attach it to the network from step 1 and skip to step 3. Otherwise start one:

```bash
docker run -d --name satya-postgres --restart unless-stopped \
  --network postgres_default \
  -e POSTGRES_DB=satya_lekha -e POSTGRES_USER=satya \
  -e POSTGRES_PASSWORD='<a-long-random-password>' \
  -v satya_pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg16
```

Generate the password with `openssl rand -base64 24`. Publish no port: only containers on `postgres_default`
need to reach it.

On first start the app runs `CREATE EXTENSION IF NOT EXISTS vector`, which needs a superuser (the image above
is one). On a managed database, create the extension yourself first.

## 3. Get the code and configure

```bash
git clone https://github.com/vivekpseudo/Satya-Lekha-Document-AI.git
cd Satya-Lekha-Document-AI
cp .env.example .env
nano .env
```

Set at least:

```env
# the host name is the database container's name on the shared network
DATABASE_URL=postgresql+psycopg://satya:<password>@satya-postgres:5432/satya_lekha
POSTGRES_NETWORK=postgres_default
PROXY_NETWORK=proxy
```

A password containing `@`, `/`, `:` or `#` must be URL-encoded in `DATABASE_URL`.

The remaining defaults (`EXTRACTOR=local`, `EMBEDDER=local`, `EMBEDDING_MODEL=BAAI/bge-small-en-v1.5`,
`EMBEDDING_DIMENSIONS=384`, `MAX_UPLOAD_MB=20`) work as they are. Never commit `.env`.

### Optional: Google Document AI

Needed only for scanned PDFs and images. Document AI does not accept API keys, so ask whoever administers the
Google Cloud project for a service-account key with *Document AI API User* (and *Vertex AI User* if you also
set `EMBEDDER=google`). Then:

```bash
mkdir -p secrets && chmod 700 secrets
cp /path/to/key.json secrets/google-service-account.json && chmod 600 secrets/google-service-account.json
```

Set `EXTRACTOR=google`, `GOOGLE_CLOUD_PROJECT`, `DOCUMENT_AI_LOCATION` and `DOCUMENT_AI_PROCESSOR_ID` in `.env`,
and mount the key with a `docker-compose.override.yml` next to `docker-compose.yml` (the base file does not mount
credentials):

```yaml
services:
  app:
    environment:
      GOOGLE_APPLICATION_CREDENTIALS: /run/secrets/google_credentials
    volumes:
      - ./secrets/google-service-account.json:/run/secrets/google_credentials:ro
```

`secrets/` is in `.gitignore`. Never put the key in the repository, the image or `.env`.

Embeddings are separate from extraction. If you change `EMBEDDER`, `EMBEDDING_MODEL` or `EMBEDDING_DIMENSIONS`
after regulations were loaded, drop the `regulation_chunks` table, restart, and load them again: vectors from
different models do not mix.

## 4. Build and start

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f app
```

The container runs `python -m app.init_db` and then starts the API, so the tables are created on the first start.
The image already contains the local embedding model, so the first request does not download anything.

## 5. Check it works

```bash
curl -f http://localhost:8000/health        # {"status":"ok"}
docker compose exec app python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
```

Process a real PDF end to end:

```bash
curl -s -X POST http://localhost:8000/api/v1/documents/process-and-store -F "file=@statements.pdf" | head -c 400
```

You should get JSON with a `classification`, `facts` and `findings`. If the database or the vector extension is
the problem, this is where it shows.

## 6. Configure Nginx Proxy Manager

Add a **Proxy Host**:

| Field | Value |
|---|---|
| Domain Names | your domain, for example `satyalekha.example.com` |
| Scheme | `http` |
| Forward Hostname / IP | `app` (the compose service, reachable because NPM shares the `proxy` network) |
| Forward Port | `8000` |
| Block Common Exploits | on |
| SSL | request a Let's Encrypt certificate, then **Force SSL** |

If another stack on the same network also has a service called `app`, forward to this container's name instead
(`docker compose ps` shows it).

**Raise the upload limit.** Nginx accepts 1 MB request bodies unless told otherwise, so a PDF upload through the
proxy typically fails with `413 Request Entity Too Large`. Open the proxy host's **Advanced** tab and add:

```nginx
client_max_body_size 25m;
proxy_read_timeout 300s;
proxy_send_timeout 300s;
```

The first line should be a little above `MAX_UPLOAD_MB`. The timeouts allow for slow extraction of a long report.

## 7. Lock it down

`docker-compose.yml` publishes `8000:8000`, which makes the API reachable on the VPS's public IP *around* NPM and
without TLS. Since NPM reaches `app` over the `proxy` network, you can close the port:

- bind it to the loopback interface by changing the mapping in `docker-compose.yml` to
  `"127.0.0.1:8000:8000"`, or remove the `ports:` block, and
- check with `curl -m 5 http://<vps-public-ip>:8000/health` from another machine: it should fail.

Because the service has no login, restrict who can reach the domain too. In NPM, create an **Access List** (basic
authentication and/or an IP allow-list) and attach it to the proxy host. Do not expose PostgreSQL.

## Operations

**Logs:** `docker compose logs -f app`.

**Update:**

```bash
git pull
docker compose up -d --build
docker compose ps
```

The start-up command re-runs `app.init_db`, which creates anything missing but does not migrate existing tables.
There are no migrations yet (Alembic is on the to-do list): a change to a table needs a manual `ALTER`.

**Back up** the database off the VPS as well as on it, and test a restore:

```bash
docker exec satya-postgres pg_dump -U satya -d satya_lekha | gzip > satya_lekha_$(date +%F).sql.gz
gunzip -c satya_lekha_2026-01-01.sql.gz | docker exec -i satya-postgres psql -U satya -d satya_lekha
```

What is stored: each processed document (its text and normalised JSON), the extracted facts, and the regulation
passages you loaded. Uploaded PDFs themselves are not kept.

**Load regulations** for evidence retrieval with `POST /api/v1/regulations` (see the README). Source them from
authoritative publications and keep their URIs and effective dates.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `network … declared as external, but could not be found` | Step 1 was skipped, or `POSTGRES_NETWORK` / `PROXY_NETWORK` in `.env` name a network that does not exist (`docker network ls`). |
| Container restarts; log shows a connection error | `DATABASE_URL` host is wrong, or the database is not on `POSTGRES_NETWORK`. Use the database container's name. |
| `extension "vector" is not available` | The database image has no pgvector. Use `pgvector/pgvector:pg16`, or install the extension. |
| `413 Request Entity Too Large` on upload | NPM's body limit: add `client_max_body_size` in step 6. |
| Upload hangs, then `504` / `502` | Raise `proxy_read_timeout` (step 6); check `docker compose logs app`. |
| `422 … scanned PDF` | The PDF has no text layer. Local extraction cannot read it: use `EXTRACTOR=google`. |
| `415 Unsupported MIME type` | Local extraction accepts PDFs only. Images need `EXTRACTOR=google`. |
| `expected 768 dimensions, not 384` (or similar) | `EMBEDDING_DIMENSIONS` differs from the existing `regulation_chunks.embedding` column. See step 3. |
| Blank page or 404 on `/` | The web app was not built into the image. Rebuild: `docker compose build --no-cache app`. |

## Not in the compose file

`frontend/Dockerfile` and `frontend/nginx.conf` build the web app as its own Nginx container that proxies `/api/`
to a service named `backend`. That was the earlier three-container layout and is not used by `docker-compose.yml`;
keep them only if you want to serve the UI separately from the API.

## Before real client data

Add authentication and per-user or per-tenant access, object storage for uploads, asynchronous processing,
Alembic migrations, audit logging, rate limiting, request tracing, centralised secrets, encrypted off-host backups,
and retention and deletion controls. The rules also need review by a qualified professional: see the README's
[limitations](README.md#limitations).
