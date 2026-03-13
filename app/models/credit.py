from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class CreditWallet(Base):
    __tablename__ = "credit_wallets"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    user = relationship("User", back_populates="credit_wallet")

    __table_args__ = (
        CheckConstraint("balance >= 0", name="chk_credit_wallet_balance_nonnegative"),
    )


class CreditTransaction(Base, TimestampMixin):
    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tx_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_job_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    user = relationship("User", back_populates="credit_transactions")
    related_job = relationship("Job", back_populates="credit_transactions")

    __table_args__ = (
        CheckConstraint(
            "tx_type IN ('CHARGE', 'SPEND', 'REFUND', 'ADJUST')",
            name="chk_credit_transactions_tx_type",
        ),
        CheckConstraint("amount <> 0", name="chk_credit_transactions_amount_nonzero"),
        CheckConstraint(
            """
            (tx_type IN ('CHARGE', 'REFUND') AND amount > 0)
            OR (tx_type = 'SPEND' AND amount < 0)
            OR (tx_type = 'ADJUST' AND amount <> 0)
            """,
            name="chk_credit_transactions_amount_sign",
        ),
        Index(
            "ux_credit_tx_external_ref",
            "external_ref",
            unique=True,
            postgresql_where=(external_ref.is_not(None)),
        ),
        Index("ix_credit_tx_user_created_at", "user_id", "created_at"),
        Index("ix_credit_tx_job", "related_job_id"),
    )