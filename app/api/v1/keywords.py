from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.transnews_client import TransNewsClient
from app.services.crawl_run_service import CrawlRunService

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.keyword import (
    BatchCreateKeywordRequest,
    CreateKeywordRequest,
    UpdateKeywordStatusRequest,
)
from app.services.crawl_run_service import CrawlRunService
from app.services.keyword_service import (
    batch_create_user_keywords,
    create_user_keyword,
    get_my_keywords,
    patch_keyword_is_active,
    remove_keyword,
)

router = APIRouter(prefix="/keywords", tags=["keywords"])

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_keyword_api(
    request: Request,
    payload: CreateKeywordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await create_user_keyword(
        db=db,
        current_user=current_user,
        keyword=payload.keyword,
        language=payload.language,
    )

    crawl_service = CrawlRunService(db=db, transnews_client=TransNewsClient())
    crawl_result = await crawl_service.create_crawl_run(
        user_id=current_user.id,
        keyword_ids=[data.id],
        force=False,
    )

    return success_response(
        request,
        data={
            "keyword": data.model_dump(),
            "crawl_result": crawl_result,
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.get("")
async def get_keyword_list_api(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    is_active: bool | None = Query(None),
    language: str | None = Query(None),
    q: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
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
    return success_response(request, data=data.model_dump())


@router.patch("/{keyword_id}")
async def update_keyword_status_api(
    request: Request,
    keyword_id: int,
    payload: UpdateKeywordStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await patch_keyword_is_active(
        db=db,
        current_user=current_user,
        keyword_id=keyword_id,
        is_active=payload.is_active,
    )
    return success_response(request, data=data.model_dump())


@router.delete("/{keyword_id}")
async def delete_keyword_api(
    request: Request,
    keyword_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await remove_keyword(
        db=db,
        current_user=current_user,
        keyword_id=keyword_id,
    )
    return success_response(request, data=data.model_dump())


@router.post("/batch", status_code=status.HTTP_201_CREATED)
async def batch_create_keywords_api(
    request: Request,
    payload: BatchCreateKeywordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await batch_create_user_keywords(
        db=db,
        current_user=current_user,
        keywords=payload.keywords,
        language=payload.language,
    )
    return success_response(request, data=data.model_dump(), status_code=status.HTTP_201_CREATED)