from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_cloud_project: str
    document_ai_location: str = "us"
    document_ai_processor_id: str
    max_upload_mb: int = 20
    database_url: str = "postgresql+psycopg://satya:satya@localhost:5432/satya_lekha"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    google_cloud_location: str = "global"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
