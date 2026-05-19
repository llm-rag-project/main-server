from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.importance import ImportanceListQuery, ImportanceRunRequest, ScoringFeedbackRequest
from app.services.importance_service import ImportanceService

router = APIRouter(prefix="/importance", tags=["importance"])


@router.get("")
async def list_importance(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword_id: int | None = Query(None, ge=1),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    min_score: float | None = Query(None, ge=0.0, le=1.0),
    max_score: float | None = Query(None, ge=0.0, le=1.0),
    status: str | None = Query(None),
    sort: str = Query("scored_at_desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    query = ImportanceListQuery(
        page=page,
        size=size,
        keyword_id=keyword_id,
        **{
            "from": from_date,
            "to": to_date,
            "min_score": min_score,
            "max_score": max_score,
            "status": status,
            "sort": sort,
        },
    )
    service = ImportanceService(db)
    result = await service.get_importance_list(user_id=current_user.id, query=query)
    return success_response(request, data=result)


@router.post("/run")
async def run_importance(
    request: Request,
    payload: ImportanceRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    from app.repositories.article_repository import ArticleRepository
    article_repo = ArticleRepository(db)
    article_ids = await article_repo.get_article_ids_by_keyword(
        user_id=current_user.id,
        keyword_id=payload.keyword_id,
    )
    if not article_ids:
        return success_response(request=request, data={
            "items": [],
            "already_scored_count": 0,
            "remaining_count": 0,
        })
    service = ImportanceService(db)
    result = await service.run_importance_scoring(
        user_id=current_user.id,
        article_ids=article_ids,
    )
    return success_response(request=request, data=result)


@router.post("/feedback")
async def submit_scoring_feedback(
    request: Request,
    payload: ScoringFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = ImportanceService(db)
    row = await service.save_scoring_feedback(
        user_id=current_user.id,
        article_id=payload.article_id,
        original_score=payload.original_score,
        user_score=payload.user_score,
        reason=payload.reason,
    )
    return success_response(request, data={
        "id": row.id,
        "article_id": row.article_id,
        "original_score": row.original_score,
        "user_score": row.user_score,
        "reason": row.reason,
        "created_at": row.created_at.isoformat(),
    })
