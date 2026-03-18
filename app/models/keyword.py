from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, UniqueConstraint, func
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

    user = relationship("User", back_populates="keywords")
    crawl_runs = relationship("CrawlRun", back_populates="keyword", cascade="all, delete-orphan")
    article_matches = relationship("ArticleMatch", back_populates="keyword", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "keyword_text", name="uq_keywords_user_keyword_text"),
        Index("ux_keywords_user_keyword_lower", "user_id", func.lower(keyword_text), unique=True),
        Index("ix_keywords_user_active", "user_id", "is_active"),
    )