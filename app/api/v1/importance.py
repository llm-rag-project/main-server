from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_or_dev_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.repositories.article_repository import ArticleRepository
from app.repositories.importance_repository import ImportanceRepository
from app.schemas.importance import ImportanceListQuery, ImportanceRunRequest
from app.services.importance_service import ImportanceService

router = APIRouter(prefix="/importance", tags=["importance"])


@router.get("")
async def list_importance(
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
    return success_response(data=result.model_dump())


@router.post("/run")
async def run_importance(
    payload: ImportanceRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_dev_user),
):
    service = ImportanceService(db)
    result = await service.run_importance_scoring(
        user_id=current_user.id,
        article_ids=payload.article_ids,
    )
    await db.commit()
    return success_response(data=result.model_dump())