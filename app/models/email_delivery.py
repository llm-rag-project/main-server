from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class EmailDelivery(Base, TimestampMixin):
    __tablename__ = "email_deliveries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED", server_default="QUEUED")
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="email_deliveries")
    job = relationship("Job", back_populates="email_deliveries")

    __table_args__ = (
        CheckConstraint("status IN ('QUEUED', 'SENT', 'FAIL')", name="chk_email_deliveries_status"),
        Index("ix_email_user_created_at", "user_id", "created_at"),
        Index("ix_email_status_sent_at", "status", "sent_at"),
        Index("ix_email_job", "job_id"),
    )