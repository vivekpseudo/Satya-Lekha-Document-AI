from sqlalchemy import text
from sqlalchemy.orm import Session

from app.embeddings import EmbeddingService


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(float(v)) for v in values) + "]"


def add_regulation(
    session: Session,
    *,
    regulation_id: str,
    title: str,
    content: str,
    source_uri: str,
    effective_from: str | None = None,
    effective_to: str | None = None,
) -> None:
    embedding = EmbeddingService().embed_document(content)
    session.execute(
        text("""
            INSERT INTO regulation_chunks
                (regulation_id, title, text, source_uri, effective_from, effective_to, embedding)
            VALUES
                (:regulation_id, :title, :content, :source_uri,
                 :effective_from, :effective_to, CAST(:embedding AS vector))
        """),
        {
            "regulation_id": regulation_id,
            "title": title,
            "content": content,
            "source_uri": source_uri,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "embedding": _vector_literal(embedding),
        },
    )
    session.commit()


def retrieve_regulations(
    session: Session,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    embedding = EmbeddingService().embed_query(query)
    rows = session.execute(
        text("""
            SELECT id, regulation_id, title, text, source_uri,
                   effective_from, effective_to,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM regulation_chunks
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """),
        {"embedding": _vector_literal(embedding), "top_k": top_k},
    ).mappings()

    return [dict(row) for row in rows]
