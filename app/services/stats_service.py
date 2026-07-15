import logging
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import asyncio

from app.core.transnews_client import TransNewsClient
from app.repositories.stats_repository import StatsRepository

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


class StatsService:
    def __init__(self, repo: StatsRepository, transnews_client: TransNewsClient | None = None):
        self.repo = repo
        self.transnews_client = transnews_client

    async def get_article_stats(self, user_id: int, days: int = 7) -> dict:
        by_keyword = await self.repo.get_article_count_by_keyword(user_id=user_id, days=days)
        by_date = await self.repo.get_article_count_by_date(user_id=user_id, days=days)
        by_keyword_date = await self.repo.get_article_count_by_date_per_keyword(user_id=user_id, days=days)
        by_collected_date = await self.repo.get_article_count_by_collected_date(user_id=user_id, days=days)
        by_keyword_collected_date = await self.repo.get_article_count_by_collected_date_per_keyword(
            user_id=user_id,
            days=days,
        )

        return {
            "days": days,
            "by_keyword": by_keyword,
            "by_date": by_date,
            "by_keyword_date": by_keyword_date,
            "by_collected_date": by_collected_date,
            "by_keyword_collected_date": by_keyword_collected_date,
            "keyword_insights": self._build_keyword_insights(by_keyword_date),
        }

    async def get_article_hourly_stats(
        self,
        *,
        user_id: int,
        target_date: date,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        keyword_id: int | None = None,
    ) -> list[dict]:
        return await self.repo.get_article_count_by_published_hour(
            user_id=user_id,
            target_date=target_date,
            from_at=from_at,
            to_at=to_at,
            keyword_id=keyword_id,
        )

    async def get_daily_social_stats(
        self,
        *,
        user_id: int,
        target_date: date,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        keyword_id: int | None = None,
    ) -> list[dict]:
        rows = await self.repo.get_social_metrics_by_sampled_date(
            user_id=user_id,
            target_date=target_date,
            from_at=from_at,
            to_at=to_at,
            keyword_id=keyword_id,
        )
        if rows or not self.transnews_client:
            return rows

        keywords = await self.repo.get_active_keywords(user_id=user_id)
        if keyword_id:
            keywords = [kw for kw in keywords if kw.id == keyword_id]
        if not keywords:
            return []

        start_at = (from_at.astimezone(KST) if from_at else datetime.combine(target_date, time.min, tzinfo=KST))
        end_at = (to_at.astimezone(KST) if to_at else datetime.combine(target_date, time.max, tzinfo=KST))
        for kw in keywords:
            try:
                result = await self.transnews_client.get_social_stats(
                    kw.keyword_text,
                    limit=kw.crawl_limit,
                    window_start=start_at.astimezone(timezone.utc).isoformat(),
                    window_end=end_at.astimezone(timezone.utc).isoformat(),
                )
            except Exception as exc:
                logger.warning("Daily social metric lookup failed keyword_id=%s date=%s: %s", kw.id, target_date, exc)
                continue

            for item in result.get("sources") or []:
                await self.repo.add_social_metric(
                    user_id=user_id,
                    keyword_id=kw.id,
                    keyword_text=kw.keyword_text,
                    source=item.get("source") or "unknown",
                    mention_count=int(item.get("mention_count") or 0),
                    positive_hint_count=int(item.get("positive_hint_count") or 0),
                    negative_hint_count=int(item.get("negative_hint_count") or 0),
                    sampled_at=end_at,
                )

        return await self.repo.get_social_metrics_by_sampled_date(
            user_id=user_id,
            target_date=target_date,
            from_at=from_at,
            to_at=to_at,
            keyword_id=keyword_id,
        )

    def _build_keyword_insights(self, rows: list[dict]) -> list[dict]:
        by_keyword: dict[int, dict] = {}
        for row in rows:
            keyword_id = row["keyword_id"]
            bucket = by_keyword.setdefault(
                keyword_id,
                {
                    "keyword_id": keyword_id,
                    "keyword_text": row["keyword_text"],
                    "daily_counts": [],
                },
            )
            bucket["daily_counts"].append(
                {
                    "date": row["date"],
                    "article_count": int(row["article_count"] or 0),
                }
            )

        insights: list[dict] = []
        for bucket in by_keyword.values():
            daily_counts = sorted(bucket["daily_counts"], key=lambda item: item["date"])
            today_count = daily_counts[-1]["article_count"] if daily_counts else 0
            yesterday_count = daily_counts[-2]["article_count"] if len(daily_counts) > 1 else 0
            previous_counts = [item["article_count"] for item in daily_counts[:-1]]
            avg_previous = round(sum(previous_counts) / len(previous_counts), 1) if previous_counts else 0
            delta = today_count - yesterday_count
            delta_rate = round((delta / yesterday_count) * 100) if yesterday_count else (100 if today_count else 0)
            spike = today_count >= max(3, avg_previous * 2) and today_count > yesterday_count
            risk_level = "watch" if spike else "monitor" if today_count >= 10 else "normal"

            insights.append(
                {
                    "keyword_id": bucket["keyword_id"],
                    "keyword_text": bucket["keyword_text"],
                    "today_count": today_count,
                    "yesterday_count": yesterday_count,
                    "delta": delta,
                    "delta_rate": delta_rate,
                    "avg_previous": avg_previous,
                    "spike": spike,
                    "risk_level": risk_level,
                    "summary": self._insight_sentence(bucket["keyword_text"], today_count, delta, spike, avg_previous),
                }
            )

        return sorted(insights, key=lambda item: (item["spike"], item["today_count"]), reverse=True)

    def _insight_sentence(self, keyword: str, today_count: int, delta: int, spike: bool, avg_previous: float) -> str:
        if spike:
            return f"{keyword} 관련 보도가 최근 평균 {avg_previous}건 대비 빠르게 증가했습니다."
        if delta > 0:
            return f"{keyword} 관련 보도가 전일 대비 {delta}건 증가했습니다."
        if delta < 0:
            return f"{keyword} 관련 보도는 전일 대비 {abs(delta)}건 감소했습니다."
        if today_count:
            return f"{keyword} 관련 보도량은 전일과 비슷한 수준입니다."
        return f"{keyword} 관련 신규 보도 신호가 약합니다."

    async def get_analysis_stats(self, user_id: int, days: int = 7) -> dict:
        sentiment_by_kw = await self.repo.get_sentiment_by_keyword(user_id=user_id, days=days)
        promotion_by_kw = await self.repo.get_promotion_by_keyword(user_id=user_id, days=days)
        sentiment_by_date = await self.repo.get_sentiment_by_date(user_id=user_id, days=days)
        return {
            "days": days,
            "sentiment_by_keyword": sentiment_by_kw,
            "promotion_by_keyword": promotion_by_kw,
            "sentiment_by_date": sentiment_by_date,
        }

    async def get_keyword_search_volume(self, user_id: int) -> list[dict]:
        keywords = await self.repo.get_active_keywords(user_id=user_id)
        if not keywords:
            return []

        latest_news_rows = await self.repo.get_latest_news_search_metrics(user_id=user_id)
        news_by_keyword = {row["keyword_id"]: row for row in latest_news_rows}

        if self.transnews_client:
            missing_news_keywords = [kw for kw in keywords if kw.id not in news_by_keyword]
            news_results = await asyncio.gather(
                *[self._count_search_results_for_keyword(kw, hours=1) for kw in missing_news_keywords],
                return_exceptions=True,
            )
            now = datetime.now(timezone.utc)
            for kw, result in zip(missing_news_keywords, news_results):
                if isinstance(result, Exception):
                    logger.warning("Keyword '%s' news search metric lookup failed: %s", kw.keyword_text, result)
                    continue
                metric = await self.repo.add_news_search_metric(
                    user_id=user_id,
                    keyword_id=kw.id,
                    keyword_text=kw.keyword_text,
                    total_count=int(result["count"]),
                    min_count=0,
                    max_count=int(result["limit"]),
                    sampled_at=now,
                )
                news_by_keyword[kw.id] = {
                    "keyword_id": kw.id,
                    "keyword_text": kw.keyword_text,
                    "total_count": metric.total_count,
                    "min_count": metric.min_count,
                    "max_count": metric.max_count,
                    "sampled_at": metric.sampled_at.isoformat() if metric.sampled_at else None,
                }

        social_rows = await self.repo.get_latest_social_metrics(user_id=user_id)
        social_by_keyword: dict[int, list[dict]] = {}
        for row in social_rows:
            social_by_keyword.setdefault(row["keyword_id"], []).append(row)

        if self.transnews_client:
            missing_social_keywords = [kw for kw in keywords if kw.id not in social_by_keyword]
            social_results = await asyncio.gather(
                *[
                    self.transnews_client.get_social_stats(kw.keyword_text, limit=kw.crawl_limit, hours=168)
                    for kw in missing_social_keywords
                ],
                return_exceptions=True,
            )
            for kw, result in zip(missing_social_keywords, social_results):
                if isinstance(result, Exception):
                    logger.warning("Keyword '%s' social metric lookup failed: %s", kw.keyword_text, result)
                    continue
                social_by_keyword[kw.id] = [
                    {
                        "keyword_id": kw.id,
                        "keyword_text": kw.keyword_text,
                        "source": item.get("source"),
                        "mention_count": int(item.get("mention_count") or 0),
                        "positive_hint_count": int(item.get("positive_hint_count") or 0),
                        "negative_hint_count": int(item.get("negative_hint_count") or 0),
                        "sampled_at": result.get("sampled_at"),
                    }
                    for item in (result.get("sources") or [])
                ]

        volume_list = []
        for kw in keywords:
            social_sources = social_by_keyword.get(kw.id, [])
            social_total = sum(item.get("mention_count", 0) for item in social_sources)
            social_negative = sum(item.get("negative_hint_count", 0) for item in social_sources)
            social_positive = sum(item.get("positive_hint_count", 0) for item in social_sources)
            news_metric = news_by_keyword.get(kw.id, {})
            volume_list.append(
                {
                    "keyword_id": kw.id,
                    "keyword_text": kw.keyword_text,
                    "total_count": news_metric.get("total_count", 0),
                    "min_count": news_metric.get("min_count", 0),
                    "max_count": news_metric.get("max_count", 0),
                    "sampled_at": news_metric.get("sampled_at"),
                    "social_total_count": social_total,
                    "social_positive_hint_count": social_positive,
                    "social_negative_hint_count": social_negative,
                    "social_sources": social_sources,
                }
            )

        return sorted(volume_list, key=lambda x: x["total_count"] + x["social_total_count"], reverse=True)

    async def get_keyword_search_volume_trend(self, user_id: int, hours: int = 48) -> list[dict]:
        return await self.repo.get_news_search_metric_trend(user_id=user_id, hours=hours)

    async def capture_news_search_metrics(self, user_id: int) -> dict:
        if not self.transnews_client:
            return {"captured_count": 0, "failed_count": 0}

        keywords = await self.repo.get_active_keywords(user_id=user_id)
        results = await asyncio.gather(
            *[self._count_search_results_for_keyword(kw, hours=1) for kw in keywords],
            return_exceptions=True,
        )
        now = datetime.now(timezone.utc)
        captured_count = 0
        failed_count = 0
        for kw, result in zip(keywords, results):
            if isinstance(result, Exception):
                failed_count += 1
                logger.warning("Keyword '%s' hourly news search metric capture failed: %s", kw.keyword_text, result)
                continue
            await self.repo.add_news_search_metric(
                user_id=user_id,
                keyword_id=kw.id,
                keyword_text=kw.keyword_text,
                total_count=int(result["count"]),
                min_count=0,
                max_count=int(result["limit"]),
                sampled_at=now,
            )
            captured_count += 1

        return {"captured_count": captured_count, "failed_count": failed_count}

    async def _count_search_results_for_keyword(self, keyword, *, hours: int = 1) -> dict:
        if not self.transnews_client:
            return {"count": 0, "limit": 0}

        end_at = datetime.now(timezone.utc)
        start_at = end_at - timedelta(hours=hours)
        # Search volume should be an independent market signal, not capped by
        # the number of articles the user wants to save in one crawl run.
        limit = 1000
        result = await self.transnews_client.search_news(
            keyword.keyword_text,
            published_after=start_at.isoformat(),
            published_before=end_at.isoformat(),
            limit=limit,
        )
        items = result.get("data") or []
        return {
            "count": len(items),
            "limit": limit,
        }
