from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import CreditWallet,CreditTransaction
from app.models.user import User
from app.schemas.credits import CreditTransactionListQuery


class CreditRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def user_exists(self, user_id: int) -> bool:
        stmt = select(func.count()).select_from(User).where(User.id == user_id)
        count = await self.db.scalar(stmt)
        return bool(count)

    async def get_or_create_wallet(self, user_id: int) -> CreditWallet:
        stmt = select(CreditWallet).where(CreditWallet.user_id == user_id).limit(1)
        result = await self.db.execute(stmt)
        wallet = result.scalar_one_or_none()

        if wallet is None:
            wallet = CreditWallet(user_id=user_id, balance=0)
            self.db.add(wallet)
            await self.db.flush()
            await self.db.refresh(wallet)

        return wallet

    async def get_credit_balance(self, user_id: int) -> dict[str, Any]:
        wallet = await self.get_or_create_wallet(user_id)

        return {
            "user_id": wallet.user_id,
            "balance": wallet.balance,
            "updated_at": wallet.updated_at,
        }

    async def get_credit_transactions(
        self,
        user_id: int,
        query: CreditTransactionListQuery,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(CreditTransaction).where(CreditTransaction.user_id == user_id)

        if query.type:
            stmt = stmt.where(CreditTransaction.tx_type == query.type.value)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt)
        total = total or 0

        stmt = (
            stmt.order_by(CreditTransaction.created_at.desc(), CreditTransaction.id.desc())
            .offset((query.page - 1) * query.size)
            .limit(query.size)
        )

        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        items = []
        for tx in rows:
            items.append(
                {
                    "id": tx.id,
                    "type": tx.tx_type,
                    "amount": tx.amount,
                    "balance_after": tx.balance_after,
                    "description": tx.reason,
                    "created_at": tx.created_at,
                }
            )

        return items, total