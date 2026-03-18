from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.repositories.importance_repository import ImportanceRepository
from app.schemas.importance import (
    ImportanceListQuery,
    ImportanceSort,
    ImportanceStatus,
)
from app.services.importance_service import ImportanceService

router = APIRouter(prefix="/importance", tags=["importance"])


@router.get("")
async def get_importance_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword_id: int | None = Query(None, ge=1),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    min_score: float | None = Query(None, ge=0.0, le=1.0),
    max_score: float | None = Query(None, ge=0.0, le=1.0),
    status_filter: ImportanceStatus | None = Query(None, alias="status"),
    sort: ImportanceSort = Query(ImportanceSort.scored_at_desc),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        query = ImportanceListQuery(
            page=page,
            size=size,
            keyword_id=keyword_id,
            **{
                "from": from_date,
                "to": to_date,
                "min_score": min_score,
                "max_score": max_score,
                "status": status_filter,
                "sort": sort,
            },
        )

        service = ImportanceService(ImportanceRepository(db))
        result = await service.get_importance_list(user_id=current_user.id, query=query)
        return success_response(data=result.model_dump())

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )