from fastapi import APIRouter, Depends, HTTPException, Query, status
from requests import request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.repositories.article_repository import ArticleRepository
from app.schemas.articles import (
    ArticleFeedbackRequest,
    ArticleLanguage,
    ArticleListQuery,
    ArticleSort,
)
from app.services.article_service import ArticleService

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("")
async def get_articles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword_id: int | None = Query(None, ge=1),
    q: str | None = Query(None),
    language: ArticleLanguage | None = Query(None),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    min_importance: float | None = Query(None, ge=0.0, le=1.0),
    max_importance: float | None = Query(None, ge=0.0, le=1.0),
    has_feedback: bool | None = Query(None),
    liked: bool | None = Query(None),
    sort: ArticleSort = Query(ArticleSort.published_at_desc),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        query = ArticleListQuery(
            page=page,
            size=size,
            keyword_id=keyword_id,
            q=q,
            language=language,
            **{
                "from": from_date,
                "to": to_date,
                "min_importance": min_importance,
                "max_importance": max_importance,
                "has_feedback": has_feedback,
                "liked": liked,
                "sort": sort,
            },
        )

        service = ArticleService(ArticleRepository(db))
        result = await service.get_article_list(user_id=current_user.id, query=query)
        return success_response(request=request, data=result.model_dump())

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{article_id}")
async def get_article_detail(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ArticleService(ArticleRepository(db))

    try:
        result = await service.get_article_detail(
            user_id=current_user.id,
            article_id=article_id,
        )
        return success_response(data=result.model_dump())

    except ValueError as e:
        if str(e) == "NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="article not found",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except PermissionError as e:
        if str(e) == "FORBIDDEN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this article",
            )
        raise


@router.get("/{article_id}/importance")
async def get_article_importance(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ArticleService(ArticleRepository(db))

    try:
        result = await service.get_article_importance(
            user_id=current_user.id,
            article_id=article_id,
        )
        return success_response(data=result.model_dump())

    except ValueError as e:
        if str(e) == "NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="article not found",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except PermissionError as e:
        if str(e) == "FORBIDDEN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this article",
            )
        raise



@router.get("/{article_id}/feedback")
async def get_my_article_feedback(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ArticleService(ArticleRepository(db))

    try:
        result = await service.get_my_feedback_by_article(
            user_id=current_user.id,
            article_id=article_id,
        )
        return success_response(data=result.model_dump() if result else None)

    except ValueError as e:
        if str(e) == "NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="article not found",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except PermissionError as e:
        if str(e) == "FORBIDDEN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this article",
            )
        raise


@router.delete("/{article_id}/feedback")
async def delete_my_article_feedback(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ArticleService(ArticleRepository(db))

    try:
        result = await service.delete_my_feedback_by_article(
            user_id=current_user.id,
            article_id=article_id,
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

        if str(e) == "FEEDBACK_NOT_FOUND":
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