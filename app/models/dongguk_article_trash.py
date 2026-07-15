from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class DonggukArticleTrash(Base, TimestampMixin):
    __tablename__ = "dongguk_article_trash"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mail_date: Mapped[str] = mapped_column(String(10), nullable=False)
    article_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    article_body: Mapped[str] = mapped_column(Text, nullable=False)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "keyword_id", "mail_date", "article_id", name="uq_dongguk_trash_user_keyword_date_article"),
        Index("ix_dongguk_trash_user_date", "user_id", "mail_date"),
    )
