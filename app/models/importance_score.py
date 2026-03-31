from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ImportanceScore(Base, TimestampMixin):
    __tablename__ = "importance_scores"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    article_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETED", server_default="COMPLETED")
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    engine: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    trigger_feedback_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("feedbacks.id", ondelete="SET NULL"),
        nullable=True,
    )

    article = relationship("Article", back_populates="importance_scores")
    user = relationship("User", back_populates="importance_scores")
    trigger_feedback = relationship("Feedback", back_populates="triggered_scores")

    __table_args__ = (
        Index(
            "ux_importance_current",
            "article_id",
            "user_id",
            unique=True,
            postgresql_where=(is_current.is_(True)),
        ),
        Index("ix_importance_scores_user_current", "user_id", "is_current", "created_at"),
    )