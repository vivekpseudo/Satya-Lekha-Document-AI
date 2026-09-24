from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    classification_confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    facts: Mapped[list["FinancialFact"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class FinancialFact(Base):
    __tablename__ = "financial_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    statement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    period: Mapped[str | None] = mapped_column(String(20))
    value: Mapped[float | None] = mapped_column(Numeric(20, 4))
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_text: Mapped[str | None] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="facts")
