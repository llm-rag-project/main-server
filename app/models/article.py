from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Article(Base, TimestampMixin):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_article_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    matches = relationship("ArticleMatch", back_populates="article", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="article", cascade="all, delete-orphan")
    translations = relationship("Translation", back_populates="article", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="article", cascade="all, delete-orphan")
    importance_scores = relationship("ImportanceScore", back_populates="article", cascade="all, delete-orphan")

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
    )