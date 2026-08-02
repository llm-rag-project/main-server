from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class DonggukPriorityInsight(Base, TimestampMixin):
    __tablename__ = "dongguk_priority_insights"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_key: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    cadence: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="applied")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_body: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    criteria_before: Mapped[str] = mapped_column(Text, nullable=False)
    criteria_after: Mapped[str] = mapped_column(Text, nullable=False)
    changes_body: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    generated_by: Mapped[str] = mapped_column(String(30), nullable=False, default="server-analysis")
    workflow_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    keyword = relationship("Keyword")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "keyword_id",
            "period_key",
            "cadence",
            name="uq_dongguk_priority_insight_period",
        ),
        Index("ix_dongguk_priority_insight_user_keyword_period", "user_id", "keyword_id", "period_start"),
        Index("ix_dongguk_priority_insight_status", "status", "period_end"),
    )
