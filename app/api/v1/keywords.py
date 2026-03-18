from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.keyword import (
    BatchCreateKeywordRequest,
    CreateKeywordRequest,
    LanguageEnum,
    UpdateKeywordStatusRequest,
)
from app.services.keyword_service import (
    batch_create_user_keywords,
    create_user_keyword,
    get_my_keywords,
    patch_keyword_is_active,
    remove_keyword,
)

router = APIRouter(prefix="/keywords", tags=["keywords"])


@router.post("", status_code=201)
async def create_keyword(
    request: Request,
    payload: CreateKeywordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await create_user_keyword(
        db=db,
        current_user=current_user,
        keyword=payload.keyword,
        language=payload.language,
    )
    return success_response(request, data=data, status_code=201)


@router.get("")
async def list_keywords(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1),
    is_active: bool | None = Query(None),
    language: LanguageEnum | None = Query(None),
    q: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await get_my_keywords(
        db=db,
        current_user=current_user,
        page=page,
        size=size,
        is_active=is_active,
        language=language,
        q=q,
    )
    return success_response(request, data=data)


@router.patch("/{keyword_id}")
async def patch_keyword(
    request: Request,
    keyword_id: int,
    payload: UpdateKeywordStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await patch_keyword_is_active(
        db=db,
        current_user=current_user,
        keyword_id=keyword_id,
        is_active=payload.is_active,
    )
    return success_response(request, data=data)


@router.delete("/{keyword_id}")
async def delete_keyword(
    request: Request,
    keyword_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await remove_keyword(
        db=db,
        current_user=current_user,
        keyword_id=keyword_id,
    )
    return success_response(request, data=data)


@router.post("/batch")
async def batch_create_keywords(
    request: Request,
    payload: BatchCreateKeywordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await batch_create_user_keywords(
        db=db,
        current_user=current_user,
        keywords=payload.keywords,
        language=payload.language,
    )
    return success_response(request, data=data)