from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Article(Base, TimestampMixin):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_article_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    collection_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=True)
    section: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pool: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    trusted_source: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    priority_boost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    board: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    board_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    
    matches = relationship("ArticleMatch", back_populates="article", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="article", cascade="all, delete-orphan")
    translations = relationship("Translation", back_populates="article", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="article", cascade="all, delete-orphan")
    importance_scores = relationship("ImportanceScore", back_populates="article", cascade="all, delete-orphan")
    analysis = relationship("ArticleAnalysis", back_populates="article", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ux_articles_url", "url", unique=True),
        Index(
            "ux_articles_source_article_id",
            "source_type",
            "source_article_id",
            unique=True,
            postgresql_where=(source_article_id.is_not(None)),
        ),
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_created_at", "created_at"),
        Index("ix_articles_canonical_url", "canonical_url"),
        Index("ix_articles_content_fingerprint", "content_fingerprint"),
    )
