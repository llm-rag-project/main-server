from datetime import date
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, Date, Index, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_type: Mapped[str] = mapped_column(String(20), nullable=False, default="MONTHLY", server_default="MONTHLY")
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    user = relationship("User", back_populates="reports")

    __table_args__ = (
        CheckConstraint(
            "report_type IN ('MONTHLY', 'WEEKLY', 'DAILY', 'CUSTOM')",
            name="chk_reports_report_type",
        ),
        UniqueConstraint("user_id", "report_type", "period_start", "period_end", name="uq_reports_user_type_period"),
        Index("ix_reports_user_created_at", "user_id", "created_at"),
        Index("ix_reports_period", "report_type", "period_start", "period_end"),
    )