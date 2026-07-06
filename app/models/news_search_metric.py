from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NewsSearchMetric(Base):
    __tablename__ = "news_search_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    keyword_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    keyword_text: Mapped[str] = mapped_column(String(255), nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    min_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sampled_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User")
    keyword = relationship("Keyword")

    __table_args__ = (
        Index("ix_news_search_metrics_keyword_sampled", "keyword_id", "sampled_at"),
        Index("ix_news_search_metrics_user_sampled", "user_id", "sampled_at"),
    )
