"""
크롤링 완료 후 AI 감성/홍보성 분석 배치 서비스.
매일 오전 8시 크롤링 완료 후 자동 호출.
"""
import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_analysis import ArticleAnalysis
from app.services.dify_service import DifyService

logger = logging.getLogger(__name__)

_BATCH_SIZE = 30          # Dify 1회 호출당 최대 기사 수
_RETRY_SERVER_DOWN = 3    # 서버 다운 시 재시도 횟수
_RETRY_TIMEOUT = 1        # 타임아웃 시 재시도 횟수
_RETRY_DELAY = 5          # 재시도 간격(초)

_DEFAULT_SENTIMENT = "분석실패"
_DEFAULT_IS_PROMOTION = None


class AnalysisService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.dify = DifyService.from_settings()

    async def _get_unanalyzed_articles(self) -> list[dict]:
        """article_analysis 레코드가 없는 기사만 조회."""
        stmt = (
            select(Article.id, Article.title, Article.content)
            .outerjoin(ArticleAnalysis, ArticleAnalysis.article_id == Article.id)
            .where(ArticleAnalysis.id.is_(None))
            .order_by(Article.id.desc())
        )
        result = await self.db.execute(stmt)
        return [
            {"article_id": r.id, "title": r.title or "", "content": r.content or ""}
            for r in result.all()
        ]

    async def _call_dify_with_retry(self, articles_json: str) -> list[dict]:
        """Dify 호출 + 재시도 로직. 실패 시 빈 리스트 반환."""
        last_error = None

        for attempt in range(_RETRY_SERVER_DOWN):
            try:
                result = await self.dify.run_analysis_workflow(articles=articles_json)
                items = result.get("data", {}).get("items", [])
                return items if isinstance(items, list) else []
            except RuntimeError as e:
                err_str = str(e)
                last_error = e

                is_timeout = "DIFY_TIMEOUT" in err_str
                is_server_down = any(k in err_str for k in ("503", "UNAVAILABLE", "DIFY_CONNECTION_ERROR"))

                if is_timeout:
                    # 타임아웃은 1회만 재시도
                    if attempt < _RETRY_TIMEOUT:
                        logger.warning("분석 워크플로우 타임아웃, 재시도 %d/%d", attempt + 1, _RETRY_TIMEOUT)
                        await asyncio.sleep(_RETRY_DELAY)
                        continue
                    break
                elif is_server_down:
                    logger.warning("분석 워크플로우 서버 다운, 재시도 %d/%d", attempt + 1, _RETRY_SERVER_DOWN)
                    await asyncio.sleep(_RETRY_DELAY)
                    continue
                else:
                    logger.error("분석 워크플로우 파싱 실패: %s", e)
                    break

        logger.error("분석 워크플로우 최종 실패: %s", last_error)
        return []

    async def _save_batch_results(
        self,
        batch_articles: list[dict],
        dify_items: list[dict],
    ) -> int:
        """Dify 결과를 article_analysis 테이블에 저장 (upsert)."""
        # article_id → dify 결과 매핑
        result_map: dict[int, dict] = {
            item["article_id"]: item
            for item in dify_items
            if isinstance(item.get("article_id"), int)
        }

        saved = 0
        for article in batch_articles:
            article_id = article["article_id"]
            dify_item = result_map.get(article_id)

            if dify_item:
                sentiment = dify_item.get("sentiment", _DEFAULT_SENTIMENT)
                is_promotion = dify_item.get("is_promotion", _DEFAULT_IS_PROMOTION)
            else:
                # Dify 결과에 해당 기사 없으면 기본값
                sentiment = _DEFAULT_SENTIMENT
                is_promotion = _DEFAULT_IS_PROMOTION

            # 기존 레코드 확인 (unique: article_id)
            existing = await self.db.execute(
                select(ArticleAnalysis).where(ArticleAnalysis.article_id == article_id)
            )
            row = existing.scalar_one_or_none()

            if row:
                row.sentiment = sentiment
                row.is_promotion = is_promotion
            else:
                self.db.add(ArticleAnalysis(
                    article_id=article_id,
                    sentiment=sentiment,
                    is_promotion=is_promotion,
                ))
            saved += 1

        return saved

    async def run_analysis(self) -> dict:
        """미분석 기사 전체를 배치로 처리."""
        articles = await self._get_unanalyzed_articles()
        if not articles:
            logger.info("분석할 새 기사 없음")
            return {"analyzed_count": 0, "total": 0}

        logger.info("AI 분석 시작: 총 %d건", len(articles))
        total_saved = 0

        batches = [
            articles[i: i + _BATCH_SIZE]
            for i in range(0, len(articles), _BATCH_SIZE)
        ]

        for idx, batch in enumerate(batches):
            logger.info("배치 %d/%d 처리 중 (%d건)", idx + 1, len(batches), len(batch))

            articles_json = json.dumps(
                [
                    {
                        "article_id": a["article_id"],
                        "title": a["title"],
                        "content": a["content"],
                    }
                    for a in batch
                ],
                ensure_ascii=False,
            )

            dify_items = await self._call_dify_with_retry(articles_json)
            saved = await self._save_batch_results(batch, dify_items)
            total_saved += saved

        await self.db.commit()
        logger.info("AI 분석 완료: %d건 저장", total_saved)
        return {"analyzed_count": total_saved, "total": len(articles)}
