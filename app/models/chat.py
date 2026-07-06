from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Chat(Base, TimestampMixin):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_conversation_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="chats")
    keyword = relationship("Keyword")
    messages = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "keyword_id", name="uq_chats_user_keyword"),
        Index("ix_chats_user_keyword", "user_id", "keyword_id"),
    )
