from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class DonggukPriorityAction(Base, TimestampMixin):
    __tablename__ = "dongguk_priority_actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=True,
    )
    article_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
    )
    mail_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_screen: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    article_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    article_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    article_priority: Mapped[str | None] = mapped_column(String(30), nullable=True)
    before_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User")
    keyword = relationship("Keyword")
    article = relationship("Article")

    __table_args__ = (
        Index("ix_dongguk_priority_action_user_keyword_created", "user_id", "keyword_id", "created_at"),
        Index("ix_dongguk_priority_action_type_created", "action_type", "created_at"),
    )
