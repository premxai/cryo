"""ORM model for the full-text document store backing /v1/contents."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class Document(Base):
    """A full-text document — corpus JSONL rows plus live-fetched Wayback pages.

    Unlike the Meilisearch index (text truncated to 2000 chars), this table
    holds complete page text. Every live Wayback fetch is written through here,
    permanently growing the frozen corpus.
    """

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # make_doc_id(url, ts)
    url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[str] = mapped_column(String(14), nullable=False)  # YYYYMMDDHHMMSS
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    word_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="corpus")
    links: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Authenticity verification (judge-scored; human_score = judge authenticity for now)
    human_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    judge_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
