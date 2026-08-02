import logging
import re
import time
from typing import Any
from html import unescape

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.metrics import observe_external_request
from app.schemas.articles import NewsStatsResponse, TransNewsSearchResponse

logger = logging.getLogger(__name__)


class TransNewsClientError(Exception):
    pass


class TransNewsClient:
    _shared_client: httpx.AsyncClient | None = None

    def __init__(self) -> None:
        self.base_url = settings.transnews_base_url.rstrip("/")
        self.timeout = settings.transnews_request_timeout

    @classmethod
    def _http_client(cls) -> httpx.AsyncClient:
        if cls._shared_client is None or cls._shared_client.is_closed:
            cls._shared_client = httpx.AsyncClient(
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return cls._shared_client

    @classmethod
    async def close_shared_client(cls) -> None:
        client = cls._shared_client
        cls._shared_client = None
        if client is not None and not client.is_closed:
            await client.aclose()

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        operation = path.strip("/").replace("/", "_") or "root"
        started_at = time.perf_counter()
        metric_status = "error"
        try:
            response = await self._http_client().get(
                url,
                params=params,
                timeout=timeout or self.timeout,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                metric_status = "http_error"
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text
                raise TransNewsClientError(f"GET {url} failed: {detail}") from exc

            try:
                payload = response.json()
            except Exception:
                metric_status = "parse_error"
                raise
            metric_status = "success"
            return payload
        except httpx.TimeoutException:
            metric_status = "timeout"
            raise
        except httpx.TransportError:
            metric_status = "connection_error"
            raise
        finally:
            observe_external_request(
                service="transnews",
                operation=operation,
                status=metric_status,
                started_at=started_at,
            )

    def _strip_html(self, value: Any) -> str | None:
        if value is None:
            return None
        text = unescape(str(value))
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    def _first_value(self, item: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return value
        return None

    def _extract_response_items(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        payload = result.get("data", result)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("items", "articles", "news", "results", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def _normalize_news_item(self, item: dict[str, Any]) -> dict[str, Any]:
        title = self._strip_html(self._first_value(item, "title", "headline", "name")) or "제목 없음"
        description = self._strip_html(
            self._first_value(item, "content", "description", "summary", "snippet", "body", "text")
        )
        original_url = self._first_value(
            item,
            "original_url",
            "originallink",
            "originalLink",
            "source_url",
            "article_link",
            "article_url",
            "resolved_url",
            "url",
        )
        link = self._first_value(item, "link", "naver_link", "naverLink")
        source_name = self._strip_html(
            self._first_value(item, "source_name", "publisher", "source", "media", "media_name", "press")
        )
        normalized = {
            **item,
            "title": title,
            "link": str(link).strip() if link else None,
            "article_link": str(self._first_value(item, "article_link", "article_url") or original_url or link or "").strip() or None,
            "original_url": str(original_url or link or "").strip() or None,
            "source_name": source_name,
            "source_url": self._first_value(item, "source_url", "publisher_url", "media_url"),
            "collection_source": self._first_value(item, "collection_source", "collectionSource"),
            "language": item.get("language") or "ko",
            "published": self._first_value(item, "published", "published_at", "pubDate", "pubdate", "date"),
            "published_at": self._first_value(item, "published_at", "published", "pubDate", "pubdate", "date"),
            "content": description or "",
        }
        return normalized

    def _normalize_search_response(self, result: dict[str, Any]) -> dict[str, Any]:
        items = [self._normalize_news_item(item) for item in self._extract_response_items(result)]
        payload = result.get("data")
        source_debug = {}
        if isinstance(payload, dict) and isinstance(payload.get("source_debug"), dict):
            source_debug = payload["source_debug"]
        elif isinstance(result.get("source_debug"), dict):
            source_debug = result["source_debug"]
        status = str(result.get("status") or result.get("code") or "SUCCESS").upper()
        if status in {"OK", "200", "TRUE"}:
            status = "SUCCESS"
        return {
            "status": status,
            "message": result.get("message") or result.get("msg") or "뉴스 검색 성공",
            "data": items,
            "source_debug": source_debug,
        }

    async def _post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        operation = path.strip("/").replace("/", "_") or "root"
        started_at = time.perf_counter()
        metric_status = "error"
        try:
            response = await self._http_client().post(
                url,
                params=params,
                timeout=self.timeout,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                metric_status = "http_error"
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text
                raise TransNewsClientError(f"POST {url} failed: {detail}") from exc

            try:
                payload = response.json()
            except Exception:
                metric_status = "parse_error"
                raise
            metric_status = "success"
            return payload
        except httpx.TimeoutException:
            metric_status = "timeout"
            raise
        except httpx.TransportError:
            metric_status = "connection_error"
            raise
        finally:
            observe_external_request(
                service="transnews",
                operation=operation,
                status=metric_status,
                started_at=started_at,
            )

    async def search_news(
        self,
        keyword: str,
        *,
        published_after: str | None = None,
        published_before: str | None = None,
        limit: int | None = None,
        mail_date: str | None = None,
        include_dongguk_official: bool = False,
        include_section_pools: bool = False,
        include_empty_content: bool = False,
        section_pool_target_count: int | None = None,
        timeout_seconds: float | None = None,
        discovery_only: bool = False,
        search_sort: str | None = None,
        include_source_debug: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"keyword": keyword}
        if mail_date:
            params["mail_date"] = mail_date
        if published_after:
            params["published_after"] = published_after
        if published_before:
            params["published_before"] = published_before
        if limit:
            params["limit"] = limit
        if include_dongguk_official:
            params["include_dongguk_official"] = True
        if include_section_pools:
            params["include_section_pools"] = True
        if include_empty_content:
            params["include_empty_content"] = True
        if section_pool_target_count:
            params["section_pool_target_count"] = section_pool_target_count
        if timeout_seconds:
            params["timeout_seconds"] = timeout_seconds
        if discovery_only:
            params["discovery_only"] = True
        if search_sort:
            params["search_sort"] = search_sort
        if include_source_debug:
            params["include_source_debug"] = True

        # Expanded collection runs source discovery and relation expansion
        # sequentially, so the gateway needs room for both stages.
        request_timeout = max(self.timeout, (timeout_seconds or 0) + 60) if timeout_seconds else None
        result = await self._get("/news", params=params, timeout=request_timeout)
        logger.debug("TRANSNEWS RAW RESPONSE = %s", result)
        normalized = self._normalize_search_response(result)

        try:
            parsed = TransNewsSearchResponse.model_validate(normalized)
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
