from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ArticleMatch(Base):
    __tablename__ = "article_matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
    )
    crawl_run_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("crawl_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    article = relationship("Article", back_populates="matches")
    keyword = relationship("Keyword", back_populates="article_matches")
    crawl_run = relationship("CrawlRun", back_populates="article_matches")

    __table_args__ = (
        UniqueConstraint("article_id", "keyword_id", name="uq_article_matches_article_keyword"),
        Index("ix_article_matches_keyword", "keyword_id"),
        Index("ix_article_matches_article", "article_id"),
    )