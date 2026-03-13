from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.errors import ErrorCode, build_error
from app.core.response import success_response
from app.models.credit import CreditWallet, CreditTransaction
from app.models.user import User

router = APIRouter()


class ChargeCreditRequest(BaseModel):
    amount: int
    payment_method: Literal["CARD", "KAKAO_PAY", "NAVER_PAY", "ADMIN_GRANT"] | None = None


@router.get("")
async def get_my_credits(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CreditWallet).where(CreditWallet.user_id == current_user.id))
    CreditWallet = result.scalar_one_or_none()

    if CreditWallet is None:
        raise build_error(ErrorCode.NOT_FOUND, "credit not found")

    return success_response(
        request,
        data={
            "user_id": current_user.id,
            "balance": CreditWallet.balance,
            "updated_at": CreditTransaction.updated_at.isoformat() if CreditTransaction.updated_at else None,
        },
    )


@router.get("/transaction")
async def list_credit_transactions(
    request: Request,
    page: int = 1,
    size: int = 20,
    type: Literal["LLM_USAGE", "BONUS", "PURCHASE", "REFUND", "CHARGE"] | None = None,
    current_user: User = Depends(get_current_user),
):
    items = [
        {
            "id": 101,
            "type": "LLM_USAGE",
            "amount": -3,
            "balance_after": 87,
            "description": "AI 뉴스 요약 요청",
            "created_at": "2026-02-21T14:10:00Z",
        },
        {
            "id": 100,
            "type": "BONUS",
            "amount": 50,
            "balance_after": 90,
            "description": "신규 가입 보너스",
            "created_at": "2026-02-20T10:00:00Z",
        },
    ]

    return success_response(
        request,
        data={
            "items": items,
            "page_info": {
                "page": page,
                "size": size,
                "total": len(items),
                "has_next": False,
            },
        },
    )


@router.post("/charge")
async def charge_credits(
    request: Request,
    body: ChargeCreditRequest,
    current_user: User = Depends(get_current_user),
):
    return success_response(
        request,
        status_code=201,
        data={
            "transaction_id": 120,
            "amount": body.amount,
            "balance_after": 187,
            "created_at": "2026-02-21T15:00:00Z",
        },
    )