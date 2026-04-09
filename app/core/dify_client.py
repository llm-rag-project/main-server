import json
from typing import Any

import httpx

from app.core.config import settings


class DifyClientError(Exception):
    pass


class DifyClient:
    def __init__(self) -> None:
        self.base_url = settings.dify_base_url.rstrip("/")
        self.timeout = settings.dify_request_timeout

    async def _post(self, path: str, *, api_key: str, json_body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        print("DIFY URL =", url)
        print("DIFY PAYLOAD =", payload)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=json_body)
        
        print("DIFY STATUS =", response.status_code)
        print("DIFY BODY =", response.text)
        
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise DifyClientError(f"Dify 호출 실패: {detail}") from e

        return response.json()

    async def run_chatflow(
        self,
        *,
        user_id: int,
        query: str,
        article_id: int | None = None,
        conversation_id: str = "",
    ) -> dict[str, Any]:
        inputs = {"user_id": user_id}
        if article_id is not None:
            inputs["article_id"] = article_id

        payload = {
            "inputs": inputs,
            "query": query,
            "conversation_id": conversation_id,
            "response_mode": "blocking",
            "user": f"user-{user_id}",
        }

        return await self._post(
            "/chat-messages",
            api_key=settings.chatflow_api_key,
            json_body=payload,
        )

    async def run_summary_workflow(
        self,
        *,
        user_id: int,
        message: str,
        articles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "inputs": {
                "user_id": user_id,
                "message": message,
                "articles": json.dumps(articles, ensure_ascii=False),
            },
            "response_mode": "blocking",
            "user": f"user-{user_id}",
        }

        return await self._post(
            "/workflows/run",
            api_key=settings.summary_workflow_api_key,
            json_body=payload,
        )

    async def run_importance_workflow(
        self,
        *,
        user_id: int,
        articles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "inputs": {
                "user_id": user_id,
                "articles": json.dumps(articles, ensure_ascii=False),
            },
            "response_mode": "blocking",
            "user": f"user-{user_id}",
        }

        return await self._post(
            "/workflows/run",
            api_key=settings.scoring_workflow_api_key,
            json_body=payload,
        )