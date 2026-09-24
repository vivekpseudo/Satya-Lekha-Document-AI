from google import genai
from google.genai.types import EmbedContentConfig

from app.config import get_settings


class EmbeddingService:
    def __init__(self):
        settings = get_settings()
        self.client = genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    def embed_document(self, text: str) -> list[float]:
        response = self.client.models.embed_content(
            model=self.model,
            contents=text,
            config=EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=self.dimensions,
            ),
        )
        return list(response.embeddings[0].values)

    def embed_query(self, text: str) -> list[float]:
        response = self.client.models.embed_content(
            model=self.model,
            contents=text,
            config=EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=self.dimensions,
            ),
        )
        return list(response.embeddings[0].values)
