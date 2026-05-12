from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.repositories.credit_repository import CreditRepository
from app.schemas.credits import CreditTransactionListQuery, CreditTransactionType
from app.services.credit_service import CreditService

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("")
async def get_credit_balance(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = CreditService(CreditRepository(db))
    result = await service.get_credit_balance(user_id=current_user.id)
    return success_response(request, data=result.model_dump())


@router.get("/transactions")
async def get_credit_transactions(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    type: CreditTransactionType | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = CreditService(CreditRepository(db))
    query = CreditTransactionListQuery(page=page, size=size, type=type)
    result = await service.get_credit_transactions(user_id=current_user.id, query=query)
    return success_response(request, data=result.model_dump())
