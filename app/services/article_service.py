from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, build_error
from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.repositories.article_repository import ArticleRepository
from app.schemas.articles import ArticleDetailResponse, DeleteArticleResponse, DeleteFeedbackResponse, FeedbackResponse


class ArticleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.article_repository = ArticleRepository(db)

    async def get_article_by_id(self, article_id: int) -> Article | None:
        result = await self.db.execute(
            select(Article).where(Article.id == article_id)
        )
        return result.scalar_one_or_none()

    async def get_article_detail(self, user_id: int, article_id: int) -> ArticleDetailResponse:
        article = await self.article_repository.get_article_detail(user_id, article_id)
        if article is None:
            raise build_error(ErrorCode.NOT_FOUND, "article not found")
        return ArticleDetailResponse(**article)

    async def get_articles_by_keyword_id(self, keyword_id: int) -> list[Article]:
        result = await self.db.execute(
            select(Article)
            .join(ArticleMatch, ArticleMatch.article_id == Article.id)
            .where(ArticleMatch.keyword_id == keyword_id)
            .order_by(Article.published_at.desc())
        )
        return list(result.scalars().all())

    async def get_article_list(self, user_id: int, query):
        return await self.article_repository.get_article_list(
            user_id=user_id,
            query=query,
        )

    async def get_my_feedback_by_article(
        self, user_id: int, article_id: int
    ) -> FeedbackResponse | None:
        if not await self.article_repository.article_exists(article_id):
            raise build_error(ErrorCode.NOT_FOUND, "article not found")
        if not await self.article_repository.has_article_access(user_id, article_id):
            raise build_error(ErrorCode.FORBIDDEN, "access denied")
        row = await self.article_repository.get_my_feedback_by_article(user_id, article_id)
        return FeedbackResponse(**row) if row else None

    async def delete_my_feedback_by_article(
        self, user_id: int, article_id: int
    ) -> DeleteFeedbackResponse:
        if not await self.article_repository.article_exists(article_id):
            raise build_error(ErrorCode.NOT_FOUND, "article not found")
        if not await self.article_repository.has_article_access(user_id, article_id):
            raise build_error(ErrorCode.FORBIDDEN, "access denied")
        row = await self.article_repository.delete_my_feedback_by_article(user_id, article_id)
        return DeleteFeedbackResponse(**row)

    async def delete_article(
        self,
        user_id: int,
        article_id: int,
    ) -> DeleteArticleResponse:
        row = await self.article_repository.delete_article_for_user(user_id=user_id, article_id=article_id)
        if row is None:
            raise build_error(ErrorCode.NOT_FOUND, "article not found")
        return DeleteArticleResponse(**row)
