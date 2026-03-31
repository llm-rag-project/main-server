import json
import httpx

from app.core.config import settings


class DifyService:
    def __init__(self):
        self.base_url = settings.dify_base_url.rstrip("/")
        self.api_key = settings.dify_api_key
        self.timeout = settings.dify_request_timeout

    async def send_chat_message(
        self,
        query: str,
        user: str,
        conversation_id: str | None = None,
        inputs: dict | None = None,
    ) -> dict:
        url = f"{self.base_url}/chat-messages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": query,
            "user": user,
            "inputs": inputs or {},
            "response_mode": "blocking",
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 500:
            raise RuntimeError("UPSTREAM_ERROR")
        if response.status_code >= 400:
            raise RuntimeError(f"DIFY_ERROR:{response.status_code}:{response.text}")

        data = response.json()
        return {
            "conversation_id": data.get("conversation_id"),
            "message_id": data.get("message_id"),
            "answer": data.get("answer"),
            "created_at": data.get("created_at"),
            "raw": data,
        }

    async def run_importance_workflow(
        self,
        user_id: int,
        articles: list[dict],
    ) -> dict:
        url = f"{self.base_url}/workflows/run"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "inputs": {
                "user_id": user_id,
                # 네 명세 기준: JSON 직렬화 string
                "articles": json.dumps(articles, ensure_ascii=False),
            },
            "response_mode": "blocking",
            "user": str(user_id),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 500:
            raise RuntimeError("UPSTREAM_ERROR")
        if response.status_code >= 400:
            raise RuntimeError(f"DIFY_ERROR:{response.status_code}:{response.text}")

        data = response.json()

        # workflow raw 응답 구조가 프로젝트별로 다를 수 있으니 방어적으로 파싱
        result_data = data.get("data") or {}
        items = result_data.get("items") or []

        return {
            "workflow_run_id": result_data.get("workflow_run_id"),
            "task_id": result_data.get("task_id"),
            "items": items,
            "raw": data,
        }