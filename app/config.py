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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
