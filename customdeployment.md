# Custom Deployment Guide for Satya-Lekha Document AI

This guide descibes the process to deploy the Satya-Lekha application using a single Docker image connected to an already running PostgreSQL container, and building/pushing to a private Docker registry.

## Prerequisites

1. **Docker and Docker Compose** installed on your build machine and deployment server.
2. **Access to a Private Docker Registry** (e.g. `registry.example.com`, AWS ECR, GCP Artifact Registry).
3. **Existing PostgreSQL Container** running on a known Docker network.
4. **Google Cloud Credentials File** (e.g., `google-service-account.json`) for Document AI functionality.

## 1. Environment Configuration

You must configure the `.env` file or environment variables on the deployment server:

```env
# Google Cloud configuration
GOOGLE_CLOUD_PROJECT=your-project-id
DOCUMENT_AI_LOCATION=us
DOCUMENT_AI_PROCESSOR_ID=your-processor-id
GOOGLE_CLOUD_LOCATION=global

# Database configuration (connecting to the existing Postgres container)
# Format: postgresql+psycopg://username:password@container_name:5432/database_name
DATABASE_URL=postgresql+psycopg://satya:yourpassword@postgres_external_container_name:5432/satya_lekha
POSTGRES_NETWORK=name_of_your_existing_postgres_network

# File settings
MAX_UPLOAD_MB=20

# Embedding settings
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSIONS=768
```

## 2. Authenticating with your Private Docker Registry

Before building and pushing the image, authenticate with your private registry:

```bash
docker login registry.example.com
```
*You will be prompted for your username and password/token. Do not use hard-coded passwords in scripts.*

## 3. Building and Tagging the Image

The codebase now utilizes a **multi-stage Dockerfile** which compiles the Vite/React frontend and the Python/FastAPI backend into a single unified image. 

Build the image locally and tag it with your registry URL:

```bash
docker build -t registry.example.com/satya-lekha-app:latest .
```

*(Alternatively, you can tag an existing local image via: `docker tag satya-lekha-app registry.example.com/satya-lekha-app:latest`)*

## 4. Pushing the Image to the Registry

Once built and tagged correctly, push the image to your private registry:

```bash
docker push registry.example.com/satya-lekha-app:latest
```

## 5. Deployment Server Execution

On your deployment server:

### A. Network and Dependencies Verification
Ensure your existing PostgreSQL database is running. Determine its Docker network name using:
```bash
docker network ls
```
*(Configure the `POSTGRES_NETWORK` environment variable in your `.env` file to match this exact network name).*

### B. Pull the Docker Image
Authenticate logic applies here as well, if required:
```bash
docker login registry.example.com
docker pull registry.example.com/satya-lekha-app:latest
```

### C. Run the Application
You can run the application utilizing `docker-compose` if you modified the image tag in `docker-compose.yml`, or bypass it entirely using raw Docker commands connecting to the database network:

**Method 1. Using Docker Compose (Preferred):**
Ensure your `docker-compose.yml` specifies the correct image:
```yaml
services:
  app:
    image: registry.example.com/satya-lekha-app:latest
    # ... remaining configuration
```
Then run:
```bash
docker-compose up -d
```

**Method 2. Using Docker Run (Standalone):**
```bash
docker run -d \
  --name satya-lekha-app \
  --network name_of_your_existing_postgres_network \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/secrets/google-service-account.json:/run/secrets/google_credentials:ro \
  registry.example.com/satya-lekha-app:latest
```
*Note: Make sure your `DATABASE_URL` accurately references the PostgreSQL DB container's reachable hostname within that network.*

## 6. Reverse Proxy Setup

Because the application serves both frontend static assets and backend `/api/...` routes from a single 8000 port, setting up a reverse proxy (like NGINX, Traefik, or Cloudflare Tunnels) is straight-forward.

### NGINX Example `nginx.conf`:
```nginx
server {
    listen 80;
    server_name satyalekha.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 7. Troubleshooting

- **Container fails to start (Connection Refused DB):**
  Check that `DATABASE_URL` resolves to the correct internal Docker domain, and ensure your new app container is running on the *exact same Docker network* as PostgreSQL.
- **Frontend loads as a blank screen or 404:**
  Ensure the multi-stage build succeeded without failures. Connect to the container (`docker exec -it <container_id> /bin/sh`) and verify the presence of HTML and assets within `/app/static`.
- **API routes returning 404:**
  API calls expect `/api/...` prefixes. Make sure you don't override FastAPI's route definitions. 
