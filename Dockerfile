# Stage 1: Build Frontend
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# "/" = the same origin: the API serves the UI, so calls go to /api/v1/... on whatever host serves the page.
ARG VITE_API_BASE_URL=/
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Stage 2: Build Backend & Combine
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install backend dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the local embedding model into the image so the first request does not download it
# from Hugging Face. Change EMBEDDING_MODEL at build time to use a different model, and
# remove this step if you only ever use EMBEDDER=google.
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV FASTEMBED_CACHE_PATH=/opt/fastembed
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBEDDING_MODEL}')"

# Copy backend application code
COPY app ./app
COPY tests ./tests

# Copy the built frontend static files from Stage 1
COPY --from=frontend-build /app/frontend/dist ./static

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
