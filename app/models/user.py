from typing import Optional

from sqlalchemy import BigInteger, String, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    keywords = relationship("Keyword", back_populates="user", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")
    importance_scores = relationship("ImportanceScore", back_populates="user", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user", cascade="all, delete-orphan")
    email_deliveries = relationship("EmailDelivery", back_populates="user", cascade="all, delete-orphan")
    token_records = relationship("UserToken", back_populates="user", cascade="all, delete-orphan")
    credit_wallet = relationship("CreditWallet", back_populates="user", uselist=False, cascade="all, delete-orphan")
    credit_transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ux_users_email_lower", func.lower(email), unique=True),
    )