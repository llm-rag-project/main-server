from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Keyword(Base, TimestampMixin):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword_text: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="ko", server_default="ko")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monitoring_type: Mapped[str] = mapped_column(String(40), nullable=False, default="brand", server_default="brand")
    priority_level: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", server_default="normal")
    crawl_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440, server_default="1440")
    crawl_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    email_auto_send: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    email_recipients: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_send_time: Mapped[str] = mapped_column(String(5), nullable=False, default="08:30", server_default="08:30")
    email_condition_type: Mapped[str] = mapped_column(String(40), nullable=False, default="daily_summary", server_default="daily_summary")
    alert_negative_rate_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=25, server_default="25")
    alert_importance_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=80, server_default="80")
    alert_article_count_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    importance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="keywords")
    
    crawl_run_keywords = relationship(
        "CrawlRunKeyword",
        back_populates="keyword",
        passive_deletes=True,
        cascade="all, delete-orphan",
    )
   
    article_matches = relationship("ArticleMatch", back_populates="keyword", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "keyword_text", name="uq_keywords_user_keyword_text"),
        Index("ux_keywords_user_keyword_lower", "user_id", func.lower(keyword_text), unique=True),
        Index("ix_keywords_user_active", "user_id", "is_active"),
        Index("ix_keywords_user_group", "user_id", "group_name"),
        Index("ix_keywords_user_monitoring_type", "user_id", "monitoring_type"),
    )
