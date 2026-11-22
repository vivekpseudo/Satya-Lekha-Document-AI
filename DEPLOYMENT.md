# Deploying Satya-Lekha

The workflow: **build the image on your machine, push it to your registry, then on the server run
`docker compose` with the image from the registry and a `.env` file.** The server never sees the source code and
never builds anything.

```
your machine                    registry                      server
────────────                    ────────                      ──────
docker compose … build  ──────► satya-lekha-app:1.0.0 ──────► docker compose pull
docker compose … push                                          docker compose up -d
                                                               (docker-compose.yml + .env)
```

This guide covers the server. Building and pushing the image is in [customdeployment.md](customdeployment.md).

## Architecture

```
Internet
   │  HTTPS
   ▼
Reverse proxy (Nginx Proxy Manager) ── Docker network "proxy"
   │  HTTP
   ▼
app :8000   (FastAPI: the API and the built web app)
   │  the database's Docker network
   ▼
PostgreSQL + pgvector   (an existing container; not started by docker-compose.yml)
```

The single `app` container serves the API (`/api/...`, `/docs`, `/health`) and the web app, so there is one
hostname and no CORS setup. By default nothing is sent to Google: extraction and embeddings run inside the
container.

> **Accounts protect only the history pages.** Sign-in and per-user report history use a login, but the
> document-processing, compliance and regulation endpoints do not: anyone who can reach the service can use them.
> Set a strong `AUTH_SECRET` (the compose file requires it) and read [Lock it down](#lock-it-down) before the
> service is reachable from the Internet.

## 1. Build and push the image (your machine)

```bash
cp .env.example .env            # set APP_IMAGE, for example registry.example.com/satya-lekha-app:1.0.0
docker login registry.example.com
export AUTH_SECRET=unused-at-build-time   # compose validates the whole file; the value is not stored in the image
docker compose -f docker-compose.yml -f docker-compose.build.yml build
docker compose -f docker-compose.yml -f docker-compose.build.yml push
```

Details, version tags and architecture notes are in [customdeployment.md](customdeployment.md).

## 2. Prepare the server

You need Docker with Compose v2 on the server, and `docker login` to your registry (a pull-only token is enough):

```bash
docker login registry.example.com
```

Put exactly two files in one directory on the server (for example `/opt/satya-lekha/`): `docker-compose.yml`
and `.env`. No clone of the repository is needed.

```bash
scp docker-compose.yml user@server:/opt/satya-lekha/
```

### Docker networks

`docker-compose.yml` joins two Docker networks that must **already exist** (it declares them `external`): the
network PostgreSQL is on, and the reverse proxy's network. If either is missing, `docker compose up` fails with
*"network … declared as external, but could not be found"*.

```bash
docker network ls                         # find the database's network and the proxy's network
docker network create proxy               # only if you have no network for the proxy yet
```

## 3. PostgreSQL with pgvector

Satya-Lekha needs a PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector) extension, version
0.5.0 or newer (the schema uses an HNSW index).

### Option A: reuse a PostgreSQL server you already run

Share the **server**, but give Satya-Lekha its **own database and role**. Do not use another application's
database: both apps may have a table called `documents`, and `app.init_db` skips tables that already exist, so
Satya-Lekha would run against the wrong columns.

Run this on the server, using that server's superuser (`<superuser>`, the value of its `POSTGRES_USER`):

```bash
docker exec <postgres-container> psql -U <superuser> -tAc \
  "select default_version from pg_available_extensions where name='vector'"     # must print 0.5.0 or newer

docker exec <postgres-container> psql -U <superuser> \
  -c "CREATE ROLE satya LOGIN PASSWORD '<new-strong-password>';" \
  -c "CREATE DATABASE satya_lekha OWNER satya;"
docker exec <postgres-container> psql -U <superuser> -d satya_lekha -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Create the extension yourself: `satya` is not a superuser. Find the network the container is on:

```bash
docker inspect <postgres-container> --format '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}'
```

Consequences of sharing a server:

- **Backups:** a job that dumps only the other application's database does not cover `satya_lekha`. Dump it too
  (see [Backups](#backups)).
- **Shared resources:** connections, memory and disk are shared, and upgrading PostgreSQL or pgvector affects both.
- **Network:** `app` joins the database's network, so it can reach every other service on it, and they can reach
  it. If the other application has a service called `app`, the name becomes ambiguous there: use container names.
- **Optional hardening:** by default every role can connect to every database. `REVOKE CONNECT ON DATABASE
  <other-db> FROM PUBLIC;` followed by a `GRANT CONNECT` to the roles that need it stops `satya` connecting to
  the other application's database. Do this only if you know which roles that application uses.

### Option B: start a dedicated PostgreSQL

```bash
docker network create postgres_default      # skip if it exists
docker run -d --name satya-postgres --restart unless-stopped \
  --network postgres_default \
  -e POSTGRES_DB=satya_lekha -e POSTGRES_USER=satya \
  -e POSTGRES_PASSWORD='<a-long-random-password>' \
  -v satya_pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg16
```

Generate the password with `openssl rand -base64 24`. Publish no port. Here `satya` is the superuser, so
`app.init_db` creates the `vector` extension itself on first start.

## 4. The `.env` file on the server

```env
# the image you pushed
APP_IMAGE=registry.example.com/satya-lekha-app:1.0.0

# the database: the host is the PostgreSQL container's name on POSTGRES_NETWORK
DATABASE_URL=postgresql+psycopg://satya:<password>@<postgres-container>:5432/satya_lekha
POSTGRES_NETWORK=<the database's network>
PROXY_NETWORK=proxy

# signs login tokens: generate once with   openssl rand -hex 32
AUTH_SECRET=<64 random hex characters>
```

- A password containing `@`, `/`, `:` or `#` must be URL-encoded in `DATABASE_URL`.
- Use `postgresql+psycopg://`, not `postgresql://`: Satya-Lekha uses the psycopg 3 driver. `?sslmode=disable` is
  not needed.
- Everything else has a working default (`EXTRACTOR=local`, `EMBEDDER=local`, `EMBEDDING_MODEL`,
  `EMBEDDING_DIMENSIONS=384`, `MAX_UPLOAD_MB=20`); see `.env.example` for the full list.
- `APP_PORT_BIND` sets where the API is published on the host. It defaults to `127.0.0.1:8000`; use
  `127.0.0.1:18000` if something else (another application's backend, say) already uses 8000.
- **`AUTH_SECRET` is required.** `docker compose` refuses to start without it, so the container can never run on
  the app's public built-in default (with which anyone could forge a login). Keep it secret and stable: changing
  it signs every user out.
- Never commit `.env`, and keep it readable only by you: `chmod 600 .env`.

### Optional: Google Document AI

Needed only for scanned PDFs and images. Document AI does not accept API keys, so you need a service-account key
with *Document AI API User* (and *Vertex AI User* if you also set `EMBEDDER=google`). Put the key on the server,
outside the repository:

```bash
mkdir -p secrets && chmod 700 secrets
cp /path/to/key.json secrets/google-service-account.json && chmod 600 secrets/google-service-account.json
```

Set `EXTRACTOR=google`, `GOOGLE_CLOUD_PROJECT`, `DOCUMENT_AI_LOCATION` and `DOCUMENT_AI_PROCESSOR_ID` in `.env`,
and mount the key with a `docker-compose.override.yml` next to `docker-compose.yml` (the base file mounts no
credentials):

```yaml
services:
  app:
    environment:
      GOOGLE_APPLICATION_CREDENTIALS: /run/secrets/google_credentials
    volumes:
      - ./secrets/google-service-account.json:/run/secrets/google_credentials:ro
```

Embeddings are separate from extraction. If you change `EMBEDDER`, `EMBEDDING_MODEL` or `EMBEDDING_DIMENSIONS`
after regulations were loaded, drop the `regulation_chunks` table, restart, and load them again: vectors from
different models do not mix.

## 5. Start

```bash
cd /opt/satya-lekha
docker compose pull
docker compose up -d
docker compose ps
docker compose logs -f app
```

The container runs `python -m app.init_db` and then starts the API, so the tables are created on the first start.
The image already contains the local embedding model, so the first request downloads nothing.

Check it:

```bash
curl -f http://localhost:8000/health        # {"status":"ok"}; use your APP_PORT_BIND port
curl -s -X POST http://localhost:8000/api/v1/documents/process-and-store -F "file=@statements.pdf" | head -c 400
```

The second command should return JSON with a `classification`, `facts` and `findings`. Then confirm the tables
landed in the right database:

```bash
docker exec <postgres-container> psql -U <superuser> -d satya_lekha -c '\dt'
```

## 6. Reverse proxy (Nginx Proxy Manager)

Add a **Proxy Host**:

| Field | Value |
|---|---|
| Domain Names | your domain, for example `satyalekha.example.com` |
| Scheme | `http` |
| Forward Hostname / IP | `app` (reachable because NPM shares the `proxy` network); use `satya-lekha-app-1` if another service on that network is also called `app` |
| Forward Port | `8000` (the container's port, not `APP_PORT_BIND`) |
| Block Common Exploits | on |
| SSL | request a Let's Encrypt certificate, then **Force SSL** |

**Raise the upload limit.** Nginx accepts 1 MB request bodies unless told otherwise, so a PDF upload through the
proxy typically fails with `413 Request Entity Too Large`. In the proxy host's **Advanced** tab add:

```nginx
client_max_body_size 25m;
proxy_read_timeout 300s;
proxy_send_timeout 300s;
```

The first value should be a little above `MAX_UPLOAD_MB`. The timeouts allow for slow extraction of a long report.

## Lock it down

- The API is published on `127.0.0.1` by default, so it is not reachable on the server's public address. Check from
  another machine: `curl -m 5 http://<server-public-ip>:8000/health` should fail. Only change `APP_PORT_BIND` to
  `0.0.0.0:…` if you really need a public port.
- Only the history pages are behind a login, so restrict who can reach the domain. In NPM, create an
  **Access List** (basic authentication and/or an IP allow-list) and attach it to the proxy host.
- Do not publish PostgreSQL.

## Operations

**Update.** Build and push a new tag (see [customdeployment.md](customdeployment.md)), change `APP_IMAGE` in the
server's `.env`, then:

```bash
docker compose pull
docker compose up -d
```

The start-up command re-runs `app.init_db`, which creates anything missing but does not migrate existing tables.
There are no migrations yet: a change to a table needs a manual `ALTER`. Take a backup before upgrading.

**Roll back.** Set `APP_IMAGE` back to the previous tag and run `docker compose up -d`. This works because you
deploy version tags, not `latest`.

**Logs:** `docker compose logs -f app`.

### Backups

Back up the database off the server as well as on it, and test a restore:

```bash
docker exec <postgres-container> pg_dump -U <superuser> -d satya_lekha | gzip > satya_lekha_$(date +%F).sql.gz
gunzip -c satya_lekha_2026-01-01.sql.gz | docker exec -i <postgres-container> psql -U <superuser> -d satya_lekha
```

What is stored: each processed document (its text and normalised JSON), the extracted facts, the regulation
passages you loaded, and user accounts (password hashes, not passwords) with their saved reports. Uploaded PDFs
themselves are not kept.

**Load regulations** for evidence retrieval with `POST /api/v1/regulations` (see the README). Source them from
authoritative publications and keep their URIs and effective dates.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `required variable APP_IMAGE is missing a value` | `.env` is not in the directory you run `docker compose` from, or `APP_IMAGE` is not set. |
| `pull access denied` / `unauthorized` | `docker login` to the registry on the server, and check the image name and tag. |
| `no matching manifest` or `exec format error` | The image was built for a different CPU architecture than the server. Rebuild with `APP_PLATFORM` set to the server's (see [customdeployment.md](customdeployment.md)). |
| `network … declared as external, but could not be found` | `POSTGRES_NETWORK` or `PROXY_NETWORK` in `.env` names a network that does not exist (`docker network ls`). |
| `port is already allocated` | Something else uses the host port. Set `APP_PORT_BIND=127.0.0.1:18000`. |
| Container restarts; the log shows a connection error | The host in `DATABASE_URL` is wrong, or the database is not on `POSTGRES_NETWORK`. Use the database container's name. |
| `password authentication failed` | `DATABASE_URL` has the wrong password, or the password is not URL-encoded. |
| `required variable AUTH_SECRET is missing a value` | Add `AUTH_SECRET` to the server's `.env` (`openssl rand -hex 32`). On the build machine, `export AUTH_SECRET=unused-at-build-time` before `docker compose … build`. |
| Everyone is signed out after a redeploy | `AUTH_SECRET` changed. Keep the same value across deployments. |
| `extension "vector" is not available` / `permission denied to create extension` | No pgvector in that PostgreSQL, or `satya` is not a superuser: create the extension as the superuser (step 3). |
| `413 Request Entity Too Large` on upload | The proxy's body limit: add `client_max_body_size` (step 6). |
| Upload hangs, then `504` / `502` | Raise `proxy_read_timeout` (step 6); check `docker compose logs app`. |
| `422 … scanned PDF` | The PDF has no text layer. Local extraction cannot read it: use `EXTRACTOR=google`. |
| `415 Unsupported MIME type` | Local extraction accepts PDFs only. Images need `EXTRACTOR=google`. |
| `expected 768 dimensions, not 384` (or similar) | `EMBEDDING_DIMENSIONS` differs from the existing `regulation_chunks.embedding` column. See step 4. |
| Blank page or 404 on `/` | The image has no web app. Rebuild it (`--no-cache`) and push it again. |

## Before real client data

Add authentication and per-user or per-tenant access, object storage for uploads, asynchronous processing,
Alembic migrations, audit logging, rate limiting, request tracing, centralised secrets, encrypted off-host backups,
and retention and deletion controls. The rules also need review by a qualified professional: see the README's
[limitations](README.md#limitations).
