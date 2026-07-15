from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class DonggukMailDraft(Base, TimestampMixin):
    __tablename__ = "dongguk_mail_drafts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mail_date: Mapped[str] = mapped_column(String(10), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    selected_article_keys: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    selected_articles: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    removed_article_keys: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    removed_articles: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    preview_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "keyword_id", "mail_date", name="uq_dongguk_mail_draft_user_keyword_date"),
        Index("ix_dongguk_mail_draft_user_date", "user_id", "mail_date"),
    )
