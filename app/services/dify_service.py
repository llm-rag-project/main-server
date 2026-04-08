from typing import Any

import httpx

from app.core.config import settings
from app.core.dify_knowledge_client import DifyKnowledgeClient, DifyKnowledgeClientError
from app.models.article import Article


class DifyUploadError(Exception):
    pass


class DifyService:
    def __init__(
        self,
        base_url: str,
        chatflow_api_key: str,
        summary_workflow_api_key: str,
        scoring_workflow_api_key: str,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.chatflow_api_key = chatflow_api_key
        self.summary_workflow_api_key = summary_workflow_api_key
        self.scoring_workflow_api_key = scoring_workflow_api_key
        self.timeout = timeout

    async def _post(self, path: str, api_key: str, payload: dict) -> dict:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 500:
            raise RuntimeError("UPSTREAM_ERROR")

        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise RuntimeError(f"DIFY_ERROR: {detail}")

        return response.json()

    async def send_chat_message(
        self,
        *,
        user_id: int,
        message: str,
        conversation_id: str = "",
        article_id: int | None = None,
    ):
        inputs = {
            "user_id": user_id,
        }

        if article_id is not None:
            inputs["article_id"] = article_id

        payload = {
            "inputs": inputs,
            "query": message,
            "conversation_id": conversation_id or "",
            "response_mode": "blocking",
            "user": str(user_id),
        }

        data = await self._post("/chat-messages", self.chatflow_api_key, payload)

        return {
            "conversation_id": data.get("conversation_id"),
            "answer": data.get("answer"),
        }
        
    async def run_summary_workflow(
        self,
        *,
        user_id: int,
        message: str,
        articles: str,
    ) -> dict:
        payload = {
            "inputs": {
                "user_id": user_id,
                "message": message,
                "articles": articles,
            },
            "response_mode": "blocking",
            "user": str(user_id),
        }

        data = await self._post("/workflows/run", self.summary_workflow_api_key, payload)
        print("\n=== 🔥 DIFY SUMMARY RAW RESPONSE ===")
        print(data)
        print("===================================\n")

        result_data = data.get("data") or {}
        outputs = result_data.get("outputs") or {}

        return {
            "success": data.get("success", True),
            "data": {
                "workflow_run_id": result_data.get("workflow_run_id"),
                "task_id": result_data.get("task_id"),
                "summary_text": (
                    outputs.get("summary")
                    or outputs.get("summary_text")
                    or outputs.get("result")
                    or outputs.get("text")
                ),
            },
            "error": data.get("error"),
            "meta": data.get("meta"),
            "raw": data,
        }

    async def run_importance_workflow(
        self,
        *,
        user_id: int,
        articles: str,
    ) -> dict:
        payload = {
            "inputs": {
                "user_id": user_id,
                "articles": articles,
            },
            "response_mode": "blocking",
            "user": str(user_id),
        }

        data = await self._post("/workflows/run", self.scoring_workflow_api_key, payload)

        print("\n=== 🔥 DIFY IMPORTANCE RAW RESPONSE ===")
        print(data)
        print("======================================\n")

        result_data = data.get("data") or {}
        outputs = result_data.get("outputs") or {}

        return {
            "success": data.get("success", True),
            "data": {
                "workflow_run_id": result_data.get("workflow_run_id"),
                "task_id": result_data.get("task_id"),
                "items": outputs.get("items", []),
            },
            "error": data.get("error"),
            "meta": data.get("meta"),
            "raw": data,
        }

    @classmethod
    def from_settings(cls) -> "DifyService":
        return cls(
            base_url=settings.dify_base_url,
            chatflow_api_key=settings.chatflow_api_key,
            summary_workflow_api_key=settings.summary_workflow_api_key,
            scoring_workflow_api_key=settings.scoring_workflow_api_key,
            timeout=settings.dify_request_timeout,
        )


class DifyArticleUploadService:
    def __init__(self, knowledge_client: DifyKnowledgeClient | None = None) -> None:
        self.knowledge_client = knowledge_client or DifyKnowledgeClient()

    async def upload_article_to_knowledge(self, article: Article) -> dict[str, Any]:
        if not article.content or not article.content.strip():
            raise DifyUploadError(f"article_id={article.id} 본문이 비어 있어 업로드할 수 없습니다.")

        try:
            created = await self.knowledge_client.create_document_by_text(
                title=article.title or f"article-{article.id}",
                text=article.content,
            )

            document_id = created["document_id"]
            batch = created.get("batch")

            await self.knowledge_client.attach_article_id_metadata(
                document_id=document_id,
                article_id=article.id,
            )

            return {
                "article_id": article.id,
                "document_id": document_id,
                "batch": batch,
                "status": "UPLOADED",
            }

        except DifyKnowledgeClientError as e:
            raise DifyUploadError(f"article_id={article.id} Dify 업로드 실패: {e}") from e

    async def upload_articles_to_knowledge(self, articles: list[Article]) -> dict[str, Any]:
        uploaded = []
        failed = []

        for article in articles:
            try:
                result = await self.upload_article_to_knowledge(article)
                uploaded.append(result)
            except Exception as e:
                failed.append(
                    {
                        "article_id": article.id,
                        "status": "FAILED",
                        "reason": str(e),
                    }
                )

        return {
            "uploaded_count": len(uploaded),
            "failed_count": len(failed),
            "uploaded": uploaded,
            "failed": failed,
        }