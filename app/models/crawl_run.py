from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.crawl_run import CreateCrawlRunRequest
from app.services.crawl_run_service import (
    get_crawl_run_detail,
    request_crawl_run,
)

router = APIRouter(prefix="/crawl-runs", tags=["crawl-runs"])


@router.post("", status_code=202)
async def create_crawl_run(
    request: Request,
    payload: CreateCrawlRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await request_crawl_run(
        db=db,
        current_user=current_user,
        keyword_ids=payload.keyword_ids,
        force=payload.force,
    )
    return success_response(request, data=data, status_code=202)


@router.get("/{run_id}")
async def get_crawl_run(
    request: Request,
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await get_crawl_run_detail(
        db=db,
        current_user=current_user,
        run_id=run_id,
    )
    return success_response(request, data=data)