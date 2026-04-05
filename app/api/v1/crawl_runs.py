from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import success_response
from app.core.transnews_client import TransNewsClient, TransNewsClientError
from app.models.user import User
from app.services.crawl_run_service import CrawlRunService

router = APIRouter(
    prefix="/crawl-runs",
    tags=["crawl-runs"],
)


class CreateCrawlRunRequest(BaseModel):
    keyword_ids: list[int] | None = None
    force: bool = False


@router.post("")
async def create_crawl_run(
    request: Request,
    body: CreateCrawlRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CrawlRunService(db=db, transnews_client=TransNewsClient())

    try:
        result = await service.create_crawl_run(
            user_id=current_user.id,
            keyword_ids=body.keyword_ids,
            force=body.force,
        )
        return success_response(request, status_code=202, data=result)

    except TransNewsClientError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))