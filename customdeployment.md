# Custom deployment: build an image, push it, run it elsewhere

Use this when you build the image on one machine (or in CI), push it to a private registry, and run it on a
server that already has a PostgreSQL container. For Docker Compose on a VPS behind Nginx Proxy Manager, see
[DEPLOYMENT.md](DEPLOYMENT.md): it covers the database, the proxy, the upload limit and locking the service
down, all of which apply here as well.

One multi-stage image holds the API **and** the built web app. The API serves the UI, so there is a single port.

## Prerequisites

1. Docker on the build machine and on the server.
2. A private Docker registry (for example `registry.example.com`, AWS ECR or GCP Artifact Registry).
3. A PostgreSQL 16 container **with the pgvector extension** (`pgvector/pgvector:pg16`) on a known Docker network.
4. Optional, only for Google Document AI: a service-account key (see [DEPLOYMENT.md](DEPLOYMENT.md)).

By default nothing is sent to Google: extraction and embeddings run inside the container.

## 1. Build and push

```bash
docker login registry.example.com        # use a token; never put a password in a script

docker build -t registry.example.com/satya-lekha-app:1.0.0 .
docker tag  registry.example.com/satya-lekha-app:1.0.0 registry.example.com/satya-lekha-app:latest

docker push registry.example.com/satya-lekha-app:1.0.0
docker push registry.example.com/satya-lekha-app:latest
```

Deploy a version tag rather than `latest`, so you can roll back.

Build notes:

- The image is about 1 GB. It includes the local embedding model (`BAAI/bge-small-en-v1.5`, about 130 MB),
  downloaded **at build time**, so the build needs internet access but the running container does not.
- Another model: `docker build --build-arg EMBEDDING_MODEL=<model> .`, with a matching `EMBEDDING_DIMENSIONS`.
- If you only ever use `EMBEDDER=google`, delete the `fastembed` step in the `Dockerfile` to save the download.
- `VITE_API_BASE_URL` defaults to `/api`, which suits the single-image layout. Rebuild after changing it.

## 2. Configure the server

Create an env file on the server (do not commit it):

```env
EXTRACTOR=local
EMBEDDER=local
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
MAX_UPLOAD_MB=20

# the host is the database container's name on the network the app joins
DATABASE_URL=postgresql+psycopg://satya:<password>@<postgres-container-name>:5432/satya_lekha

# docker compose only: the existing networks to join
POSTGRES_NETWORK=<name-of-the-postgres-network>
PROXY_NETWORK=proxy
```

For Google Document AI also set `EXTRACTOR=google`, `GOOGLE_CLOUD_PROJECT`, `DOCUMENT_AI_LOCATION`,
`DOCUMENT_AI_PROCESSOR_ID`, and mount the key (see below). Find the database network with `docker network ls`.

## 3. Create the tables

The image's default command starts the API only, so create the tables once, and again after upgrades:

```bash
docker run --rm --network <postgres-network> --env-file .env \
  registry.example.com/satya-lekha-app:1.0.0 python -m app.init_db
```

(`docker compose up` does this for you, because `docker-compose.yml` runs `app.init_db` before starting the API.)

## 4. Run

**With Docker Compose.** Point the service at your image by adding a `docker-compose.override.yml` next to
`docker-compose.yml`:

```yaml
services:
  app:
    image: registry.example.com/satya-lekha-app:1.0.0
```

```bash
docker compose pull
docker compose up -d
```

**With `docker run`:**

```bash
docker run -d --name satya-lekha-app --restart unless-stopped \
  --network <postgres-network> \
  -p 127.0.0.1:8000:8000 \
  --env-file .env \
  registry.example.com/satya-lekha-app:1.0.0
```

`-p 127.0.0.1:8000:8000` keeps the port off the public interface: put a reverse proxy in front. For Google
Document AI add:

```bash
  -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google_credentials \
  -v "$(pwd)/secrets/google-service-account.json:/run/secrets/google_credentials:ro" \
```

Check it:

```bash
curl -f http://localhost:8000/health        # {"status":"ok"}
```

## 5. Reverse proxy

The application listens on one port, so any proxy works. There is no login on the service, so restrict access at
the proxy (an IP allow-list, basic authentication, or a tunnel with an access policy).

```nginx
server {
    listen 80;
    server_name satyalekha.example.com;

    client_max_body_size 25m;            # a little above MAX_UPLOAD_MB; the default 1m rejects PDFs

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

Add TLS (for example with Certbot) before real use.

## 6. Updating

Build and push a new tag, change the tag on the server, then repeat steps 3 and 4. Take a database backup first
(see [DEPLOYMENT.md](DEPLOYMENT.md#operations)). There are no migrations: `app.init_db` creates what is missing but
does not alter existing tables.

## Troubleshooting

- **Container exits or restarts with a connection error.** `DATABASE_URL` must use the database container's name,
  and the app must be on the same Docker network as the database.
- **Errors about `vector` or an `embedding` column.** The database lacks pgvector, or `EMBEDDING_DIMENSIONS`
  differs from the existing column. See [DEPLOYMENT.md](DEPLOYMENT.md#troubleshooting).
- **Blank page or 404 on `/`.** The web app was not built into the image. Check that the build finished, then look
  for `index.html` with `docker exec <container> ls /app/static`.
- **`/api/...` returns 404.** A proxy rule is rewriting paths. Forward `/` to the container unchanged.
- **`413` on upload.** The proxy's body limit: set `client_max_body_size`.
- **Local extraction rejects a scan or image.** Use `EXTRACTOR=google`.
