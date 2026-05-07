import asyncio
import logging

from app.core.transnews_client import TransNewsClient, TransNewsClientError
from app.repositories.stats_repository import StatsRepository

logger = logging.getLogger(__name__)


class StatsService:
    def __init__(self, repo: StatsRepository, transnews_client: TransNewsClient | None = None):
        self.repo = repo
        self.transnews_client = transnews_client

    async def get_article_stats(self, user_id: int, days: int = 7) -> dict:
        # 3개 쿼리 병렬 실행
        by_keyword, by_date, by_keyword_date = await asyncio.gather(
            self.repo.get_article_count_by_keyword(user_id=user_id, days=days),
            self.repo.get_article_count_by_date(user_id=user_id, days=days),
            self.repo.get_article_count_by_date_per_keyword(user_id=user_id, days=days),
        )

        return {
            "days": days,
            "by_keyword": by_keyword,
            "by_date": by_date,
            "by_keyword_date": by_keyword_date,
        }

    async def get_keyword_search_volume(self, user_id: int) -> list[dict]:
        if not self.transnews_client:
            return []

        keywords = await self.repo.get_active_keywords(user_id=user_id)
        if not keywords:
            return []

        # 모든 키워드 병렬 호출
        results = await asyncio.gather(
            *[self.transnews_client.get_news_stats(kw.keyword_text) for kw in keywords],
            return_exceptions=True,
        )

        volume_list = []
        for kw, result in zip(keywords, results):
            if isinstance(result, Exception):
                logger.warning("키워드 '%s' 검색량 조회 실패: %s", kw.keyword_text, result)
                volume_list.append({
                    "keyword_id": kw.id,
                    "keyword_text": kw.keyword_text,
                    "total_count": 0,
                    "min_count": 0,
                    "max_count": 0,
                })
            else:
                volume_list.append({
                    "keyword_id": kw.id,
                    "keyword_text": kw.keyword_text,
                    "total_count": result.get("total_count", 0),
                    "min_count": result.get("min_count", 0),
                    "max_count": result.get("max_count", 0),
                })

        return sorted(volume_list, key=lambda x: x["total_count"], reverse=True)