import logging
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.articles import NewsStatsResponse, TransNewsSearchResponse

logger = logging.getLogger(__name__)


class TransNewsClientError(Exception):
    pass


class TransNewsClient:
    def __init__(self) -> None:
        self.base_url = settings.transnews_base_url.rstrip("/")
        self.timeout = settings.transnews_request_timeout

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise TransNewsClientError(f"GET {url} failed: {detail}") from e

        return response.json()

    async def _post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, params=params)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise TransNewsClientError(f"POST {url} failed: {detail}") from e

        return response.json()

    async def search_news(
        self,
        keyword: str,
        *,
        published_after: str | None = None,
        published_before: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"keyword": keyword}
        if published_after:
            params["published_after"] = published_after
        if published_before:
            params["published_before"] = published_before
        if limit:
            params["limit"] = limit

        result = await self._get("/news", params=params)
        logger.debug("TRANSNEWS RAW RESPONSE = %s", result)

        try:
            parsed = TransNewsSearchResponse.model_validate(result)
        except ValidationError as e:
            raise TransNewsClientError(
                f"Invalid search_news response schema: {e}"
            ) from e

        return parsed.model_dump()

    async def get_news_stats(self, keyword: str) -> dict[str, Any]:
        result = await self._get("/news/stats", params={"keyword": keyword})
        try:
            parsed = NewsStatsResponse.model_validate(result.get("data", result))
        except ValidationError as e:
            raise TransNewsClientError(
                f"Invalid get_news_stats response schema: {e}"
            ) from e
        return parsed.model_dump()

    async def get_social_stats(
        self,
        keyword: str,
        limit: int = 30,
        hours: int = 24,
        window_start: str | None = None,
        window_end: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"keyword": keyword, "limit": limit, "hours": hours}
        if window_start:
            params["window_start"] = window_start
        if window_end:
            params["window_end"] = window_end
        result = await self._get("/social/stats", params=params)
        return result.get("data", result)

    async def crawl_article(self, url: str) -> dict[str, Any]:
        return await self._get("/crawl", params={"url": url})

    async def summarize_news(self, url: str) -> dict[str, Any]:
        return await self._post("/pipeline/news-summary", params={"url": url})
