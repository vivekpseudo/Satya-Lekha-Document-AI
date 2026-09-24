from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.embeddings import EmbeddingService
from app.rules_engine import RegulationEvidence


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
    as_of: str | None = None,
) -> list[dict]:
    embedding = EmbeddingService().embed_query(query)
    params = {
        "embedding": _vector_literal(embedding),
        "top_k": top_k,
        "as_of": as_of or date.today().isoformat(),
    }
    rows = session.execute(
        text("""
            SELECT id, regulation_id, title, text, source_uri,
                   effective_from, effective_to,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM regulation_chunks
            WHERE
                (effective_from IS NULL OR effective_from <= CAST(:as_of AS date))
                AND
                (effective_to IS NULL OR effective_to >= CAST(:as_of AS date))
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """),
        params,
    ).mappings()
    return [dict(row) for row in rows]


def regulation_provider(
    session: Session,
    *,
    as_of: str | None = None,
    top_k: int = 3,
):
    def provider(rule_id: str, context) -> list[RegulationEvidence]:
        query = (
            f"India {context.framework} compliance rule {rule_id} "
            f"for {context.document_type}"
        )
        rows = retrieve_regulations(session, query=query, top_k=top_k, as_of=as_of)
        return [RegulationEvidence(**row) for row in rows]

    return provider
