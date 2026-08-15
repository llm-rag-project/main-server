from fastapi import APIRouter, Depends, HTTPException, Query, Request
from datetime import date, datetime, timedelta
from typing import Literal
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.response import success_response
from app.core.transnews_client import TransNewsClient
from app.core.ttl_cache import stats_cache
from app.models.user import User
from app.repositories.stats_repository import StatsRepository
from app.services.stats_service import StatsService
from app.services.hongbo_evaluation_service import HongboEvaluationService
from app.services.priority_insight_service import (
    PriorityInsightService,
    previous_month_period,
)

router = APIRouter(prefix="/stats", tags=["stats"])


class PriorityInsightRunRequest(BaseModel):
    keyword_id: int = Field(..., ge=1)
    cadence: Literal["monthly", "quarterly"] = "monthly"
    force: bool = False


class PriorityActionRequest(BaseModel):
    keyword_id: int = Field(..., ge=1)
    action_type: Literal["criteria_edit"]
    source_screen: str = Field(default="settings", max_length=40)
    mail_date: str | None = Field(default=None, max_length=10)
    before: dict | None = None
    after: dict | None = None
    reason: str | None = Field(default=None, max_length=1000)


@router.get("/articles")
async def get_article_stats(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="최근 며칠 기준 (1~90)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = StatsService(StatsRepository(db))
    result = await stats_cache.get_or_load(
        ("article-stats", current_user.id, days),
        lambda: service.get_article_stats(user_id=current_user.id, days=days),
    )
    return success_response(request, data=result)


@router.get("/analysis")
async def get_analysis_stats(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="최근 며칠 기준 (1~90)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = StatsService(StatsRepository(db))
    result = await stats_cache.get_or_load(
        ("analysis-stats", current_user.id, days),
        lambda: service.get_analysis_stats(user_id=current_user.id, days=days),
    )
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

    async def load_search_volume():
        value = await service.get_keyword_search_volume(user_id=current_user.id)
        await db.commit()
        return value

    result = await stats_cache.get_or_load(
        ("search-volume", current_user.id),
        load_search_volume,
    )
    return success_response(request, data=result)


@router.get("/articles/hourly")
async def get_article_hourly_stats(
    request: Request,
    target_date: date = Query(..., alias="date"),
    from_at: datetime | None = Query(None),
    to_at: datetime | None = Query(None),
    keyword_id: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = StatsService(StatsRepository(db))
    result = await stats_cache.get_or_load(
        ("article-hourly", current_user.id, target_date, from_at, to_at, keyword_id),
        lambda: service.get_article_hourly_stats(
            user_id=current_user.id,
            target_date=target_date,
            from_at=from_at,
            to_at=to_at,
            keyword_id=keyword_id,
        ),
    )
    return success_response(request, data=result)


@router.get("/social/daily")
async def get_daily_social_stats(
    request: Request,
    target_date: date = Query(..., alias="date"),
    from_at: datetime | None = Query(None),
    to_at: datetime | None = Query(None),
    keyword_id: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = StatsService(
        repo=StatsRepository(db),
        transnews_client=TransNewsClient(),
    )
    async def load_daily_social_stats():
        value = await service.get_daily_social_stats(
            user_id=current_user.id,
            target_date=target_date,
            from_at=from_at,
            to_at=to_at,
            keyword_id=keyword_id,
        )
        await db.commit()
        return value

    result = await stats_cache.get_or_load(
        ("daily-social", current_user.id, target_date, from_at, to_at, keyword_id),
        load_daily_social_stats,
    )
    return success_response(request, data=result)


@router.get("/search-volume/trend")
async def get_search_volume_trend(
    request: Request,
    hours: int = Query(48, ge=1, le=24 * 30, description="Recent hours to include"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = StatsService(repo=StatsRepository(db))
    result = await stats_cache.get_or_load(
        ("search-volume-trend", current_user.id, hours),
        lambda: service.get_keyword_search_volume_trend(user_id=current_user.id, hours=hours),
    )
    return success_response(request, data=result)


@router.get("/priority-insights")
async def list_priority_insights(
    request: Request,
    keyword_id: int = Query(..., ge=1),
    limit: int = Query(24, ge=1, le=60),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = await PriorityInsightService(db).list_insights(
        user_id=current_user.id,
        keyword_id=keyword_id,
        limit=limit,
    )
    return success_response(request, data=data)


@router.get("/hongbo-evaluation")
async def get_hongbo_evaluation(
    request: Request,
    keyword_id: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    data = HongboEvaluationService().load()
    insights = await PriorityInsightService(db).list_insights(
        user_id=current_user.id,
        keyword_id=keyword_id,
        limit=24,
    )
    monthly_items = [item for item in insights.get("items") or [] if item.get("cadence") == "monthly"]
    latest_monthly = monthly_items[0] if monthly_items else None
    data["monthly_learning"] = {
        "enabled": True,
        "active_rule_count": len(insights.get("active_rules") or []),
        "monthly_run_count": len(monthly_items),
        "latest_period_key": latest_monthly.get("period_key") if latest_monthly else None,
        "latest_status": latest_monthly.get("status") if latest_monthly else None,
        "latest_change_count": len(latest_monthly.get("changes") or []) if latest_monthly else 0,
        "description": (insights.get("cadence") or {}).get("monthly"),
    }
    return success_response(request, data=data)


@router.get("/priority-insights/{insight_id}")
async def get_priority_insight(
    insight_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    try:
        data = await PriorityInsightService(db).insight_detail(
            user_id=current_user.id,
            insight_id=insight_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="AI 인사이트를 찾을 수 없습니다.") from exc
    return success_response(request, data=data)


@router.post("/priority-insights/run")
async def run_priority_insight(
    request: Request,
    body: PriorityInsightRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    today = datetime.now().date()
    if body.cadence == "monthly":
        period_start, period_end, period_key = previous_month_period(today)
    else:
        current_quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        current_quarter_start = date(today.year, current_quarter_start_month, 1)
        period_end = current_quarter_start - timedelta(days=1)
        quarter_start_month = period_end.month - ((period_end.month - 1) % 3)
        period_start = date(period_end.year, quarter_start_month, 1)
        period_key = f"{period_start.year}-Q{((period_start.month - 1) // 3) + 1}"
    try:
        row = await PriorityInsightService(db).generate_insight(
            user_id=current_user.id,
            keyword_id=body.keyword_id,
            period_start=period_start,
            period_end=period_end,
            period_key=period_key,
            cadence=body.cadence,
            force=body.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다.") from exc
    return success_response(request, data=PriorityInsightService.serialize_insight(row))


@router.delete("/priority-insights/{insight_id}")
async def delete_priority_insight(
    insight_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    try:
        row = await PriorityInsightService(db).delete_insight(
            user_id=current_user.id,
            insight_id=insight_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="AI 인사이트를 찾을 수 없습니다.") from exc
    return success_response(
        request,
        data={
            "deleted": True,
            "insight": PriorityInsightService.serialize_insight(row),
            "message": "기준 반영은 취소됐고 근거 로그는 감사 기록으로 보존됩니다.",
        },
    )


@router.post("/priority-actions")
async def record_priority_action(
    request: Request,
    body: PriorityActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    row = await PriorityInsightService(db).record_action(
        user_id=current_user.id,
        keyword_id=body.keyword_id,
        mail_date=body.mail_date,
        action_type=body.action_type,
        source_screen=body.source_screen,
        before=body.before,
        after=body.after,
        reason=body.reason,
    )
    await db.commit()
    await db.refresh(row)
    return success_response(request, data={"saved": True, "id": row.id})
