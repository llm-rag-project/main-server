from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class DonggukPreviewCache(Base, TimestampMixin):
    __tablename__ = "dongguk_preview_caches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mail_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    response_body: Mapped[str] = mapped_column(Text, nullable=False)

    user = relationship("User")

    __table_args__ = (
        Index("ix_dongguk_preview_user_date", "user_id", "mail_date"),
        Index("ix_dongguk_preview_cache_key", "cache_key"),
    )
