from typing import Literal

from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import success_response
from app.models.user import User
from app.core.deps import get_current_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.repositories.article_repository import ArticleRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.schemas.feedbacks import RankingFeedbackRequest
from app.services.article_service import ArticleService
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedbacks", tags=["feedbacks"])


@router.get("")
async def list_importance(
    request: Request,
    page: int = 1,
    size: int = 20,
    keyword_id: int | None = None,
    from_date: str | None = None,
    to: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    status: Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"] | None = None,
    sort: Literal["scored_at_desc", "scored_at_asc", "score_desc", "score_asc"] = "scored_at_desc",
    current_user: User = Depends(get_current_user),
):
    items = [
        {
            "article_id": 101,
            "title": "OpenAI releases new model",
            "url": "https://example.com/articles/101",
            "keyword_id": 12,
            "score": 0.82,
            "status": "COMPLETED",
            "scored_at": "2026-02-21T10:40:00Z",
            "created_at": "2026-02-21T10:39:10Z",
        }
    ]

    return success_response(
        request,
        data={
            "items": items,
            "page_info": {
                "page": page,
                "size": size,
                "total": len(items),
                "has_next": False,
            },
        },
    )


@router.get("/articles/{article_id}/importance")
async def get_article_importance(
    article_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return success_response(
        request,
        data={
            "article_id": article_id,
            "status": "COMPLETED",
            "score": 0.82,
            "model": "importance-v1",
            "scored_at": "2026-02-21T10:40:00Z",
            "created_at": "2026-02-21T10:39:10Z",
            "updated_at": "2026-02-21T10:40:00Z",
        },
    )
@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ArticleService(ArticleRepository(db))

    try:
        result = await service.delete_feedback(
            user_id=current_user.id,
            feedback_id=feedback_id,
        )
        await db.commit()
        return success_response(data=result.model_dump())

    except ValueError as e:
        await db.rollback()
        if str(e) == "NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="feedback not found",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except PermissionError as e:
        await db.rollback()
        if str(e) == "FORBIDDEN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this feedback",
            )
        raise

    except Exception:
        await db.rollback()
        raise

@router.post("/ranking")
async def save_ranking_feedback(
    payload: RankingFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = FeedbackService(FeedbackRepository(db))

    try:
        result = await service.save_ranking_feedback(
            user_id=current_user.id,
            payload=payload,
        )
        await db.commit()
        return success_response(data=result.model_dump())

    except ValueError as e:
        await db.rollback()

        if str(e) == "NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="article not found",
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except Exception:
        await db.rollback()
        raise