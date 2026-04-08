from datetime import datetime, timezone
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.importance_score import ImportanceScore
from app.repositories.importance_repository import ImportanceRepository
from app.repositories.article_repository import ArticleRepository
from app.services.dify_service import DifyService


class ImportanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.importance_repository = ImportanceRepository(db)
        self.article_repository = ArticleRepository(db)
        self.dify_service = DifyService.from_settings()

    async def save_score(
        self,
        *,
        article_id: int,
        user_id: int,
        score: float,
        reason: str | None,
        engine: str = "dify-importance-workflow",
        version: int = 1,
    ) -> ImportanceScore:
        await self.db.execute(
            update(ImportanceScore)
            .where(
                ImportanceScore.article_id == article_id,
                ImportanceScore.user_id == user_id,
                ImportanceScore.is_current.is_(True),
            )
            .values(is_current=False)
        )

        row = ImportanceScore(
            article_id=article_id,
            user_id=user_id,
            score=score,
            reason=reason,
            status="COMPLETED",
            scored_at=datetime.now(timezone.utc),
            engine=engine,
            version=version,
            is_current=True,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def get_importance_list(self, user_id: int, query):
        return await self.importance_repository.get_importance_list(
            user_id=user_id,
            query=query,
        )

    async def run_importance_scoring(self, user_id: int, article_ids: list[int]):
        await self.article_repository.validate_articles_exist_and_accessible(
            user_id=user_id,
            article_ids=article_ids,
        )

        articles = await self.article_repository.get_articles_for_importance_scoring(
            user_id=user_id,
            article_ids=article_ids,
        )

        dify_articles = []
        for article in articles:
            dify_articles.append(
                {
                    "article_id": article["article_id"],
                    "title": article["title"],
                    "content": article["content"],
                }
            )

        import json
        dify_result = await self.dify_service.run_importance_workflow(
            user_id=user_id,
            articles=json.dumps(dify_articles, ensure_ascii=False),
        )

        items = dify_result.get("data", {}).get("items", [])

        saved_items = []
        for item in items:
            row = await self.save_score(
                article_id=item["article_id"],
                user_id=user_id,
                score=float(item["score"]),
                reason=item.get("reason"),
            )
            saved_items.append(
                {
                    "article_id": row.article_id,
                    "score": row.score,
                    "reason": row.reason,
                    "status": row.status,
                }
            )

        await self.db.commit()

        return {
            "items": saved_items,
            "count": len(saved_items),
        }
        
    async def get_article_importance(self, user_id: int, article_id: int):
        return await self.importance_repository.get_current_score(
            user_id=user_id,
            article_id=article_id,
        )