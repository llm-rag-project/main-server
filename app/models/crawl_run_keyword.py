from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CrawlRunKeyword(Base):
    __tablename__ = "crawl_run_keywords"

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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    crawl_run = relationship("CrawlRun", back_populates="run_keywords")
    keyword = relationship("Keyword", back_populates="crawl_run_keywords")

    __table_args__ = (
        UniqueConstraint("crawl_run_id", "keyword_id", name="uq_crawl_run_keywords_run_keyword"),
    )