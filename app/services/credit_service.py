from app.core.errors import ErrorCode, build_error
from app.repositories.credit_repository import CreditRepository
from app.schemas.credits import (
    CreditBalanceResponse,
    CreditTransactionItem,
    CreditTransactionListQuery,
    CreditTransactionListResponse,
    PageInfo,
)


class CreditService:
    def __init__(self, repository: CreditRepository):
        self.repository = repository

    async def get_credit_balance(self, user_id: int) -> CreditBalanceResponse:
        if not await self.repository.user_exists(user_id):
            raise build_error(ErrorCode.NOT_FOUND, "user not found")
        result = await self.repository.get_credit_balance(user_id)
        return CreditBalanceResponse(**result)

    async def get_credit_transactions(
        self,
        user_id: int,
        query: CreditTransactionListQuery,
    ) -> CreditTransactionListResponse:
        if not await self.repository.user_exists(user_id):
            raise build_error(ErrorCode.NOT_FOUND, "user not found")

        rows, total = await self.repository.get_credit_transactions(
            user_id=user_id,
            query=query,
        )

        return CreditTransactionListResponse(
            items=[CreditTransactionItem(**row) for row in rows],
            page_info=PageInfo(
                page=query.page,
                size=query.size,
                total=total,
                has_next=query.page * query.size < total,
            ),
        )
