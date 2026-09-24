from dataclasses import dataclass


@dataclass(frozen=True)
class RegulationChunk:
    regulation_id: str
    title: str
    text: str
    source_uri: str
    effective_from: str | None = None
    effective_to: str | None = None
    embedding: list[float] | None = None


class RegulationRetriever:
    """
    Retrieval contract for a future PostgreSQL/pgvector implementation.

    Production retrieval should filter by jurisdiction, regulator, framework,
    effective date and document context before vector similarity search.
    """

    def __init__(self, chunks: list[RegulationChunk] | None = None):
        self.chunks = chunks or []

    def retrieve(self, query: str, top_k: int = 5) -> list[RegulationChunk]:
        tokens = {token.lower() for token in query.split() if len(token) > 2}
        scored = []

        for chunk in self.chunks:
            haystack = f"{chunk.title} {chunk.text}".lower()
            score = sum(token in haystack for token in tokens)
            if score:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]
