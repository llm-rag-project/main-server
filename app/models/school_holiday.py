from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class SchoolHoliday(Base, TimestampMixin):
    __tablename__ = "school_holidays"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    holiday_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="school",
        server_default="school",
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    user = relationship("User")

    __table_args__ = (
        Index("ix_school_holidays_user_dates", "user_id", "start_date", "end_date"),
    )
