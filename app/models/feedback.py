from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedbacks"

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
    label: Mapped[str] = mapped_column(String(10), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    article = relationship("Article", back_populates="feedbacks")
    user = relationship("User", back_populates="feedbacks")
    triggered_scores = relationship("ImportanceScore", back_populates="trigger_feedback")

    __table_args__ = (
        CheckConstraint("label IN ('LIKE', 'DISLIKE')", name="chk_feedback_label"),
        Index("ix_feedbacks_article_user", "article_id", "user_id"),
    )