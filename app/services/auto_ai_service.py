import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_match import ArticleMatch
from app.models.keyword import Keyword
from app.models.summary import Summary
from app.services.dify_service import DifyService
from app.services.importance_service import ImportanceService
from app.services.summary_service import SummaryService

logger = logging.getLogger(__name__)


class AutoAiService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.dify = DifyService.from_settings()
        self.summary_service = SummaryService(db)
        self.importance_service = ImportanceService(db)

    async def run_for_crawl_run(self, *, user_id: int, crawl_run_id: int) -> dict:
        article_ids = await self._get_crawl_run_article_ids(
            user_id=user_id,
            crawl_run_id=crawl_run_id,
        )
        return await self.run_for_articles(user_id=user_id, article_ids=article_ids)

    async def run_for_articles(self, *, user_id: int, article_ids: list[int]) -> dict:
        if not article_ids:
            return {"summary_count": 0, "importance_count": 0}

        summary_count = await self._summarize_missing_articles(
            user_id=user_id,
            article_ids=article_ids,
        )
        importance_result = await self.importance_service.run_importance_scoring(
            user_id=user_id,
            article_ids=article_ids,
        )

        return {
            "summary_count": summary_count,
            "importance_count": len(importance_result.get("items", [])),
            "already_scored_count": importance_result.get("already_scored_count", 0),
            "remaining_count": importance_result.get("remaining_count", 0),
        }

    async def _get_crawl_run_article_ids(self, *, user_id: int, crawl_run_id: int) -> list[int]:
        stmt = (
            select(ArticleMatch.article_id)
            .join(Keyword, Keyword.id == ArticleMatch.keyword_id)
            .where(
                Keyword.user_id == user_id,
                ArticleMatch.crawl_run_id == crawl_run_id,
            )
            .distinct()
            .order_by(ArticleMatch.article_id.desc())
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def _summarize_missing_articles(self, *, user_id: int, article_ids: list[int]) -> int:
        summarized_result = await self.db.execute(
            select(Summary.article_id).where(Summary.article_id.in_(article_ids))
        )
        summarized_ids = {row[0] for row in summarized_result.all()}
        target_ids = [article_id for article_id in article_ids if article_id not in summarized_ids]

        if not target_ids:
            return 0

        article_result = await self.db.execute(
            select(Article).where(Article.id.in_(target_ids)).order_by(Article.id.asc())
        )
        articles = list(article_result.scalars().all())

        saved_count = 0
        for article in articles:
            try:
                result = await self.dify.run_summary_workflow(
                    user_id=user_id,
                    article_id=article.id,
                    title=article.title or "",
                    content=article.content or "",
                )
                summary_text = result.get("summary")
                if not summary_text:
                    continue

                await self.summary_service.save_summary(
                    article_id=article.id,
                    summary_text=summary_text,
                    language="ko",
                    model_name="dify-summary-workflow",
                )
                saved_count += 1
            except Exception:
                logger.exception("자동 요약 실패 article_id=%s", article.id)

        await self.db.commit()
        return saved_count
