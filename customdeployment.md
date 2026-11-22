# Building and publishing the image

The image is built on your machine, pushed to your registry, and run on the server by `docker compose` using the
image from the registry. This guide covers the build and publish side; the server side is in
[DEPLOYMENT.md](DEPLOYMENT.md).

One multi-stage image holds the API **and** the built web app, so the API serves the UI on a single port.

## Prerequisites

- Docker with Compose v2 on the build machine, with internet access (the build downloads npm and Python packages
  and the local embedding model).
- A registry you can push to, for example `registry.example.com`, AWS ECR or GCP Artifact Registry.

## 1. Choose the image name

Set `APP_IMAGE` in `.env` (copy `.env.example` first), or export it for one session. Use a **version tag**, not
`latest`, so you can roll back:

```env
APP_IMAGE=registry.example.com/satya-lekha-app:1.0.0
```

The compose files read it, so the same name is used to build, push and deploy.

## 2. Build and push

```bash
docker login registry.example.com        # use a token; never put a password in a script

docker compose -f docker-compose.yml -f docker-compose.build.yml build
docker compose -f docker-compose.yml -f docker-compose.build.yml push
```

`docker-compose.build.yml` adds the build instructions on top of the deploy file. It is only used here; the server
uses `docker-compose.yml` alone. Without compose, the equivalent is:

```bash
docker buildx build --platform linux/amd64 -t registry.example.com/satya-lekha-app:1.0.0 --push .
```

To also move a `latest` tag:

```bash
docker tag  registry.example.com/satya-lekha-app:1.0.0 registry.example.com/satya-lekha-app:latest
docker push registry.example.com/satya-lekha-app:latest
```

### Check the image before you push it (optional)

```bash
docker run --rm --entrypoint sh "$APP_IMAGE" -c 'ls /app/static | head -3; ls /opt/fastembed'
```

You should see the web app's `index.html` and `assets`, and the cached embedding model.

## Build notes

- **Size and time.** The image is about 1.1 GB, of which the local embedding model
  (`BAAI/bge-small-en-v1.5`) is about 130 MB. It is downloaded **at build time**, so the build needs internet
  access but the running container does not.
- **CPU architecture.** A VPS is normally `linux/amd64`. `docker-compose.build.yml` builds for that by default, so
  an image built on an Apple Silicon Mac still starts on the server (the build runs under emulation and is slower).
  If your server differs, set `APP_PLATFORM`, for example `APP_PLATFORM=linux/arm64`. A mismatch shows up on the
  server as `no matching manifest` or `exec format error`.
- **A different embedding model.** `docker compose -f docker-compose.yml -f docker-compose.build.yml build
  --build-arg EMBEDDING_MODEL=<model>`, and set a matching `EMBEDDING_DIMENSIONS` on the server. If you only ever
  use `EMBEDDER=google`, delete the `fastembed` step in the `Dockerfile` to skip the download.
- **API address.** The web app is built with `VITE_API_BASE_URL=/api`, which suits the single-image layout. Pass
  `--build-arg VITE_API_BASE_URL=...` only if the UI and API are on different hosts.
- **Nothing secret goes into the image.** Passwords, the database URL and any Google key are supplied at run time
  through `.env` and mounts. Keep it that way.

## Running the image without compose

Compose is the recommended route. If you cannot use it, create the tables once (and again after upgrades), because
the image's default command starts only the API:

```bash
docker run --rm --network <database-network> --env-file .env "$APP_IMAGE" python -m app.init_db

docker run -d --name satya-lekha-app --restart unless-stopped \
  --network <database-network> \
  -p 127.0.0.1:8000:8000 \
  --env-file .env \
  "$APP_IMAGE"
```

`-p 127.0.0.1:8000:8000` keeps the port off the public interface: put a reverse proxy in front (see
[DEPLOYMENT.md](DEPLOYMENT.md#6-reverse-proxy-nginx-proxy-manager) for the settings it needs, including the upload
limit). To use Google Document AI, add
`-e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google_credentials -v "$(pwd)/secrets/google-service-account.json:/run/secrets/google_credentials:ro"`.

## Troubleshooting

- **The build fails downloading packages or the embedding model.** The build machine needs internet access to npm,
  PyPI and Hugging Face. Retry; behind a proxy, configure Docker's build proxy settings.
- **`required variable APP_IMAGE is missing a value`.** Set `APP_IMAGE` in `.env` or the environment before running
  compose.
- **`denied` or `unauthorized` on push.** `docker login` to the registry, and check you may push to that repository.
- **Blank page or 404 on `/` after deploying.** The image has no web app. Rebuild with `--no-cache` and push again.
- **`/api/...` returns 404 behind a proxy.** A proxy rule is rewriting paths. Forward `/` to the container unchanged.
