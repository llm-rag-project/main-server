import json
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

    async def get_article_importance(self, user_id: int, article_id: int):
        await self.article_repository.validate_articles_exist_and_accessible(
            user_id=user_id,
            article_ids=[article_id],
        )

        result = await self.importance_repository.get_current_score(
            user_id=user_id,
            article_id=article_id,
        )

        if result is None:
            return {
                "article_id": article_id,
                "score": None,
                "reason": None,
                "status": "NOT_FOUND",
            }

        return result

    async def run_importance_scoring(self, user_id: int, article_ids: list[int]):
        await self.article_repository.validate_articles_exist_and_accessible(
            user_id=user_id,
            article_ids=article_ids,
        )

        articles = await self.article_repository.get_articles_for_importance_scoring(
            user_id=user_id,
            article_ids=article_ids,
        )

        # Dify 명세에 맞게 articles를 JSON 직렬화된 문자열로 전달
        articles_payload = json.dumps(
            [
                {
                    "article_id": article["article_id"],
                    "title": article["title"],
                    "content": article["content"],
                }
                for article in articles
            ],
            ensure_ascii=False,
        )

        try:
            dify_result = await self.dify_service.run_importance_workflow(
                user_id=user_id,
                articles=articles_payload,
            )

            data = dify_result.get("data") or {}
            items = data.get("items") or []
            if not items:
                raise RuntimeError("Dify returned empty items")

            if not isinstance(items, list):
                raise RuntimeError("Dify importance response items is not a list.")

            saved_items = []
            for item in items:
                article_id = item.get("article_id")
                score = item.get("score")
                reason = item.get("reason")

                if article_id is None or score is None:
                    raise RuntimeError(
                        f"Invalid importance item from Dify: {item}"
                    )

                row = await self.save_score(
                    article_id=int(article_id),
                    user_id=user_id,
                    score=float(score),
                    reason=reason,
                )

                saved_items.append(
                    {
                        "article_id": row.article_id,
                        "score": row.score,
                        "reason": row.reason,
                    }
                )

            await self.db.commit()

            return {
                "success": True,
                "data": {
                    "workflow_run_id": data.get("workflow_run_id"),
                    "task_id": data.get("task_id"),
                    "items": saved_items,
                },
                "error": None,
                "meta": dify_result.get("meta"),
            }

        except Exception as e:
            await self.db.rollback()
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "UPSTREAM_ERROR",
                    "message": f"Failed to execute importance workflow: {str(e)}",
                },
                "meta": None,
            }