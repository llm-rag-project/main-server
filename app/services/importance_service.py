import json
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, build_error
from app.models.importance_score import ImportanceScore
from app.repositories.article_repository import ArticleRepository
from app.repositories.importance_repository import ImportanceRepository
from app.services.dify_service import DifyService

_MIN_PREFERENCE_SAMPLES = 3


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

    async def save_user_score(
        self,
        *,
        user_id: int,
        article_id: int,
        score: float,
        reason: str | None,
    ) -> ImportanceScore:
        await self.article_repository.validate_articles_exist_and_accessible(
            user_id=user_id,
            article_ids=[article_id],
        )
        row = await self.importance_repository.save_user_score(
            user_id=user_id,
            article_id=article_id,
            score=score,
            reason=reason,
        )
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def get_user_preference_hint(self, user_id: int) -> str | None:
        """
        Compares user manual scores vs prior AI scores for the same articles.
        Returns a Korean-language hint string for Dify, or None if insufficient data.
        """
        pairs = await self.importance_repository.get_paired_scores(user_id)

        if len(pairs) < _MIN_PREFERENCE_SAMPLES:
            return None

        deltas = [p["user_score"] - p["ai_score"] for p in pairs]
        avg_delta = sum(deltas) / len(deltas)

        user_scores = [p["user_score"] for p in pairs]
        high_count = sum(1 for s in user_scores if s >= 70)
        low_count = sum(1 for s in user_scores if s < 30)
        high_ratio = high_count / len(user_scores) * 100
        low_ratio = low_count / len(user_scores) * 100

        lines = [f"[사용자 개인 점수 기준 — {len(pairs)}건 분석]"]

        if avg_delta > 5:
            lines.append(f"- AI 점수 대비 평균 {avg_delta:+.0f}점 높게 평가하는 경향")
        elif avg_delta < -5:
            lines.append(f"- AI 점수 대비 평균 {avg_delta:+.0f}점 낮게 평가하는 경향")
        else:
            lines.append("- AI 점수와 유사한 기준으로 평가하는 경향")

        if high_ratio >= 50:
            lines.append(f"- 고중요도(70점 이상) 기사를 {high_ratio:.0f}% 비율로 선택하는 편")
        elif low_ratio >= 40:
            lines.append(f"- 저중요도(30점 미만) 기사를 {low_ratio:.0f}% 비율로 선택하는 편")

        lines.append("위 기준을 참고하여 이 사용자의 관심 성향에 맞게 점수를 조정하세요.")
        return "\n".join(lines)

    async def get_user_preference_summary(self, user_id: int) -> dict:
        pairs = await self.importance_repository.get_paired_scores(user_id)

        if len(pairs) < _MIN_PREFERENCE_SAMPLES:
            return {
                "pattern_summary": f"분석 데이터 부족 (현재 {len(pairs)}건, 최소 {_MIN_PREFERENCE_SAMPLES}건 필요)",
                "sample_count": len(pairs),
                "avg_delta": None,
            }

        deltas = [p["user_score"] - p["ai_score"] for p in pairs]
        avg_delta = sum(deltas) / len(deltas)
        hint = await self.get_user_preference_hint(user_id)

        return {
            "pattern_summary": hint or "",
            "sample_count": len(pairs),
            "avg_delta": round(avg_delta, 2),
        }

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

    async def run_importance_scoring(self, user_id: int, article_ids: list[int]) -> dict:
        await self.article_repository.validate_articles_exist_and_accessible(
            user_id=user_id,
            article_ids=article_ids,
        )

        # Skip articles already manually scored by the user
        user_scored_ids = await self.importance_repository.get_user_scored_article_ids(user_id)
        ai_article_ids = [aid for aid in article_ids if aid not in user_scored_ids]

        articles = await self.article_repository.get_articles_for_importance_scoring(
            user_id=user_id,
            article_ids=ai_article_ids,
        ) if ai_article_ids else []

        saved_items = []

        if articles:
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

            user_preference = await self.get_user_preference_hint(user_id)

            dify_result = await self.dify_service.run_importance_workflow(
                user_id=user_id,
                articles=articles_payload,
                user_preference=user_preference,
            )

            data = dify_result.get("data") or {}
            items = data.get("items") or []

            if not items or not isinstance(items, list):
                raise build_error(ErrorCode.UPSTREAM_ERROR, "Dify returned empty or invalid items")

            for item in items:
                article_id = item.get("article_id")
                score = item.get("score")
                reason = item.get("reason")

                if article_id is None or score is None:
                    raise build_error(
                        ErrorCode.UPSTREAM_ERROR,
                        f"Invalid importance item from Dify: {item}",
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
                        "source": "ai",
                    }
                )

        await self.db.commit()

        skipped = [{"article_id": aid, "source": "user"} for aid in user_scored_ids if aid in article_ids]

        return {
            "items": saved_items,
            "skipped_user_scored": skipped,
        }
