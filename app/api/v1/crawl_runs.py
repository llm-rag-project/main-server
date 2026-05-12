from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.errors import ErrorCode, build_error
from app.core.response import success_response
from app.core.transnews_client import TransNewsClient, TransNewsClientError
from app.models.user import User
from app.services.crawl_run_service import CrawlRunService

router = APIRouter(prefix="/crawl-runs", tags=["crawl-runs"])


class CreateCrawlRunRequest(BaseModel):
    keyword_ids: list[int] | None = None
    force: bool = False


@router.post("")
async def create_crawl_run(
    request: Request,
    body: CreateCrawlRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = CrawlRunService(db=db, transnews_client=TransNewsClient())

    try:
        result = await service.create_crawl_run(
            user_id=current_user.id,
            keyword_ids=body.keyword_ids,
            force=body.force,
        )
    except TransNewsClientError as e:
        raise build_error(ErrorCode.UPSTREAM_ERROR, str(e))

    return success_response(request, status_code=202, data=result)
