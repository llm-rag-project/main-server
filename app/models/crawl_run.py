from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.article_match import ArticleMatch
from app.models.crawl_run_keyword import CrawlRunKeyword


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    force_run: Mapped[bool] = mapped_column(Boolean, default=False)
    article_count: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="crawl_runs")
    run_keywords: Mapped[list["CrawlRunKeyword"]] = relationship(
        "CrawlRunKeyword",
        back_populates="crawl_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    article_matches: Mapped[list["ArticleMatch"]] = relationship(
        "ArticleMatch",
        back_populates="crawl_run"
    )