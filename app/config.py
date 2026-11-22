from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # "local" (PyMuPDF / sentence-transformers) or "google" (Document AI / Vertex AI)
    extractor: str = "local"
    embedder: str = "local"
    google_cloud_project: str = ""
    document_ai_location: str = "us"
    document_ai_processor_id: str = ""
    max_upload_mb: int = 20
    database_url: str = "postgresql+psycopg://satya:satya@localhost:5432/satya_lekha"
    # local default: BAAI/bge-small-en-v1.5 (384 dims). For google use
    # gemini-embedding-001 with EMBEDDING_DIMENSIONS=768.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    google_cloud_location: str = "global"
    # Browser origins allowed to call the API (comma separated). Only needed when the
    # frontend is served from a different origin, such as the Vite dev server.
    # Signs login tokens. Set a long random value in production (e.g. `openssl rand -hex 32`).
    auth_secret: str = "change-me-in-production"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
