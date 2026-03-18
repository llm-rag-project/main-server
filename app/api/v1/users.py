from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.user import MeResponse, UpdateMeRequest
from app.services.user_service import patch_me

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    data = MeResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        created_at=current_user.created_at,
    )
    return success_response(request, data=data)


@router.patch("/me")
async def update_me(
    request: Request,
    payload: UpdateMeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_data = payload.model_dump(exclude_unset=True)

    data = await patch_me(
        db=db,
        current_user=current_user,
        update_data=update_data,
    )
    return success_response(request, data=data)