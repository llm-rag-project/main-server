from typing import Any

import httpx

from app.core.config import settings


class TransNewsClientError(Exception):
    pass


class TransNewsClient:
    def __init__(self) -> None:
        self.base_url = settings.transnews_base_url.rstrip("/")
        self.timeout = settings.transnews_request_timeout

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
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

    async def _post(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
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

    async def search_news(self, keyword: str) -> dict[str, Any]:
        result =  await self._get("/news", params={"keyword": keyword})
        print("[DEBUG] TRANSNEWS RAW RESPONSE = ", result)
        return result

    async def crawl_article(self, url: str) -> dict[str, Any]:
        return await self._get("/crawl", params={"url": url})

    async def summarize_news(self, url: str) -> dict[str, Any]:
        return await self._post("/pipeline/news-summary", params={"url": url})