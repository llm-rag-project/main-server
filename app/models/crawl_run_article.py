from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CrawlRunArticle(Base):
    __tablename__ = "crawl_run_articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    crawl_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("crawl_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
    )
    article_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_name: Mapped[str] = mapped_column(String(60), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    candidate_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_reconstructed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    crawl_run = relationship("CrawlRun", back_populates="article_records")
    keyword = relationship("Keyword")
    article = relationship("Article")

    __table_args__ = (
        Index("ix_crawl_run_articles_run_status", "crawl_run_id", "status"),
        Index("ix_crawl_run_articles_keyword_created", "keyword_id", "created_at"),
        Index("ix_crawl_run_articles_canonical_url", "canonical_url"),
    )
