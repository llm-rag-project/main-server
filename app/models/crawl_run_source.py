from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CrawlRunSource(Base):
    __tablename__ = "crawl_run_sources"

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
    source_name: Mapped[str] = mapped_column(String(60), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stored_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_date_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_relevance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_reconstructed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    crawl_run = relationship("CrawlRun", back_populates="source_records")
    keyword = relationship("Keyword")

    __table_args__ = (
        UniqueConstraint(
            "crawl_run_id",
            "keyword_id",
            "source_name",
            name="uq_crawl_run_source_run_keyword_source",
        ),
        Index("ix_crawl_run_sources_keyword_created", "keyword_id", "created_at"),
        Index("ix_crawl_run_sources_status_created", "status", "created_at"),
    )
