from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.response import success_response
from app.core.transnews_client import TransNewsClient
from app.models.user import User
from app.repositories.stats_repository import StatsRepository
from app.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/articles")
async def get_article_stats(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="최근 며칠 기준 (1~90)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = StatsService(StatsRepository(db))
    result = await service.get_article_stats(user_id=current_user.id, days=days)
    return success_response(request, data=result)


@router.get("/search-volume")
async def get_search_volume(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = StatsService(
        repo=StatsRepository(db),
        transnews_client=TransNewsClient(),
    )
    result = await service.get_keyword_search_volume(user_id=current_user.id)
    return success_response(request, data=result)