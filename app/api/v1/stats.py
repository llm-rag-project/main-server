from fastapi import APIRouter, Depends, Query, Request
from datetime import date
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


@router.get("/analysis")
async def get_analysis_stats(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="최근 며칠 기준 (1~90)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = StatsService(StatsRepository(db))
    result = await service.get_analysis_stats(user_id=current_user.id, days=days)
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
    await db.commit()
    return success_response(request, data=result)


@router.get("/articles/hourly")
async def get_article_hourly_stats(
    request: Request,
    target_date: date = Query(..., alias="date"),
    keyword_id: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = StatsService(StatsRepository(db))
    result = await service.get_article_hourly_stats(
        user_id=current_user.id,
        target_date=target_date,
        keyword_id=keyword_id,
    )
    return success_response(request, data=result)


@router.get("/social/daily")
async def get_daily_social_stats(
    request: Request,
    target_date: date = Query(..., alias="date"),
    keyword_id: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = StatsService(
        repo=StatsRepository(db),
        transnews_client=TransNewsClient(),
    )
    result = await service.get_daily_social_stats(
        user_id=current_user.id,
        target_date=target_date,
        keyword_id=keyword_id,
    )
    await db.commit()
    return success_response(request, data=result)


@router.get("/search-volume/trend")
async def get_search_volume_trend(
    request: Request,
    hours: int = Query(48, ge=1, le=24 * 30, description="Recent hours to include"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = StatsService(repo=StatsRepository(db))
    result = await service.get_keyword_search_volume_trend(user_id=current_user.id, hours=hours)
    return success_response(request, data=result)
