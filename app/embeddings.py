from functools import lru_cache

from app.config import get_settings

@lru_cache
def _local_model(name: str):
    from fastembed import TextEmbedding  # lazy; ONNX runtime, no PyTorch needed

    return TextEmbedding(name)


@lru_cache
def _google_client(project: str, location: str):
    from google import genai

    return genai.Client(vertexai=True, project=project, location=location)


class EmbeddingService:
    def __init__(self):
        settings = get_settings()
        self.provider = settings.embedder
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self._settings = settings

    def _local(self, text: str, query: bool) -> list[float]:
        model = _local_model(self.model)
        embed = model.query_embed if query else model.passage_embed
        values = [float(v) for v in next(iter(embed(text)))]
        if len(values) != self.dimensions:
            raise ValueError(
                f"Model {self.model} returns {len(values)} dims but EMBEDDING_DIMENSIONS="
                f"{self.dimensions}. Update the setting and the regulation_chunks table."
            )
        return values

    def _google(self, text: str, task_type: str) -> list[float]:
        from google.genai.types import EmbedContentConfig

        client = _google_client(self._settings.google_cloud_project, self._settings.google_cloud_location)
        response = client.models.embed_content(
            model=self.model,
            contents=text,
            config=EmbedContentConfig(task_type=task_type, output_dimensionality=self.dimensions),
        )
        return list(response.embeddings[0].values)

    def embed_document(self, text: str) -> list[float]:
        if self.provider == "local":
            return self._local(text, query=False)
        return self._google(text, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        if self.provider == "local":
            return self._local(text, query=True)
        return self._google(text, "RETRIEVAL_QUERY")
