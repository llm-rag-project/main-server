from app.repositories.article_repository import ArticleRepository
from app.schemas.articles import (
    ArticleDetailResponse,
    ArticleListItem,
    ArticleListQuery,
    ArticleListResponse,
    PageInfo,
)
from app.schemas.articles import (
    ArticleFeedbackRequest,
    ArticleFeedbackResponse,
    ArticleImportanceResponse,
)
from app.schemas.feedbacks import (
    ArticleFeedbackGetResponse,
    DeleteFeedbackResponse,
)


class ArticleService:
    def __init__(self, repository: ArticleRepository):
        self.repository = repository

    async def get_article_list(self, user_id: int, query: ArticleListQuery) -> ArticleListResponse:
        rows, total = await self.repository.get_article_list(user_id=user_id, query=query)

        items = [ArticleListItem(**row) for row in rows]
        has_next = query.page * query.size < total

        return ArticleListResponse(
            items=items,
            page_info=PageInfo(
                page=query.page,
                size=query.size,
                total=total,
                has_next=has_next,
            ),
        )

    async def get_article_detail(self, user_id: int, article_id: int) -> ArticleDetailResponse:
        exists = await self.repository.article_exists(article_id)
        if not exists:
            raise ValueError("NOT_FOUND")

        has_access = await self.repository.has_article_access(user_id=user_id, article_id=article_id)
        if not has_access:
            raise PermissionError("FORBIDDEN")

        article = await self.repository.get_article_detail(user_id=user_id, article_id=article_id)
        if not article:
            raise ValueError("NOT_FOUND")

        return ArticleDetailResponse(**article)
    
    async def get_article_importance(
        self,
        user_id: int,
        article_id: int,
    ) -> ArticleImportanceResponse:
        exists = await self.repository.article_exists(article_id)
        if not exists:
            raise ValueError("NOT_FOUND")

        has_access = await self.repository.has_article_access(
            user_id=user_id,
            article_id=article_id,
        )
        if not has_access:
            raise PermissionError("FORBIDDEN")

        importance = await self.repository.get_article_importance(
            user_id=user_id,
            article_id=article_id,
        )

        if not importance:
            # 명세에서 권장한 운영 규칙 반영
            # importance 레코드가 아직 없으면 200 + PENDING
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            return ArticleImportanceResponse(
                article_id=article_id,
                status="PENDING",
                score=None,
                model=None,
                scored_at=None,
                created_at=now,
                updated_at=now,
            )

        return ArticleImportanceResponse(**importance)

    async def upsert_article_feedback(
        self,
        user_id: int,
        article_id: int,
        payload: ArticleFeedbackRequest,
    ) -> ArticleFeedbackResponse:
        exists = await self.repository.article_exists(article_id)
        if not exists:
            raise ValueError("NOT_FOUND")

        has_access = await self.repository.has_article_access(
            user_id=user_id,
            article_id=article_id,
        )
        if not has_access:
            raise PermissionError("FORBIDDEN")

        result = await self.repository.upsert_article_feedback(
            user_id=user_id,
            article_id=article_id,
            action=payload.action.value,
        )

        return ArticleFeedbackResponse(**result)
    async def get_my_feedback_by_article(
        self,
        user_id: int,
        article_id: int,
    ) -> ArticleFeedbackGetResponse | None:
        exists = await self.repository.article_exists(article_id)
        if not exists:
            raise ValueError("NOT_FOUND")

        has_access = await self.repository.has_article_access(
            user_id=user_id,
            article_id=article_id,
        )
        if not has_access:
            raise PermissionError("FORBIDDEN")

        feedback = await self.repository.get_my_feedback_by_article(
            user_id=user_id,
            article_id=article_id,
        )
        if feedback is None:
            return None

        return ArticleFeedbackGetResponse(**feedback)

    async def delete_my_feedback_by_article(
        self,
        user_id: int,
        article_id: int,
    ) -> DeleteFeedbackResponse:
        exists = await self.repository.article_exists(article_id)
        if not exists:
            raise ValueError("NOT_FOUND")

        has_access = await self.repository.has_article_access(
            user_id=user_id,
            article_id=article_id,
        )
        if not has_access:
            raise PermissionError("FORBIDDEN")

        result = await self.repository.delete_my_feedback_by_article(
            user_id=user_id,
            article_id=article_id,
        )

        return DeleteFeedbackResponse(**result)