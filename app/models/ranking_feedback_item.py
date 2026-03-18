from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RankingFeedbackItem(Base):
    __tablename__ = "ranking_feedback_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ranking_feedback_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ranking_feedbacks.id", ondelete="CASCADE"),
        nullable=False,
    )
    article_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    rank_order: Mapped[int] = mapped_column(Integer, nullable=False)