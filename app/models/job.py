from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED", server_default="QUEUED")
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="jobs")
    credit_transactions = relationship("CreditTransaction", back_populates="related_job")
    email_deliveries = relationship("EmailDelivery", back_populates="job")

    __table_args__ = (
        CheckConstraint(
            "job_type IN ('REPORT_EMAIL', 'SUMMARY_EMAIL', 'CRAWL', 'OTHER')",
            name="chk_jobs_job_type",
        ),
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'SUCCESS', 'FAIL', 'CANCELLED')",
            name="chk_jobs_status",
        ),
        Index("ix_jobs_user_created_at", "user_id", "created_at"),
        Index("ix_jobs_status_scheduled_for", "status", "scheduled_for"),
    )