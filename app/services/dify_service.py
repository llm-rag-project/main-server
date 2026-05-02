import json
from typing import Any
import re

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
            "user": f"user-{user_id}",
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
        article_id: int,
        title: str,
        content: str,
    ) -> dict:
        articles = [
            {
                "article_id": article_id,
                "title": title,
                "content": content,
            }
        ]

        payload = {
            "inputs": {
                "user_id": user_id,
                "message": (
                    "이 기사를 한국어로 핵심만 간결하게 요약해줘. "
                    "반드시 JSON 형식으로 반환해줘."
                ),
                "articles": json.dumps(articles, ensure_ascii=False),
            },
            "response_mode": "blocking",
            "user": f"user-{user_id}",
        }
        print("====== RUN SUMMARY WORKFLOW START ======", flush=True)
        dify_result = await self._post(
            "/workflows/run",
            self.summary_workflow_api_key,
            payload,
        )
                
        print("====== DIFY RESULT ======", flush=True)
        print(dify_result, flush=True)
        result_data = dify_result.get("data") or {}
        outputs = result_data.get("outputs") or {}

        summary_text = outputs.get("summary_text")

        if not summary_text:
            raise ValueError(f"요약 결과를 찾을 수 없습니다. outputs={outputs}")

        # 1. Dify가 JSON 객체로 준 경우
        if isinstance(summary_text, dict):
            return {
                "article_id": summary_text.get("article_id", article_id),
                "summary": summary_text.get("summary") or summary_text.get("요약문") or str(summary_text),
            }

        # 2. Dify가 문자열로 준 경우
        if isinstance(summary_text, str):
            text = summary_text.strip()

            # 2-1. 문자열 내용이 JSON이면 파싱
            try:
                parsed = json.loads(text)

                if isinstance(parsed, dict):
                    if "articles" in parsed and parsed["articles"]:
                        first = parsed["articles"][0]
                        return {
                            "article_id": first.get("article_id", article_id),
                            "summary": first.get("summary", ""),
                        }

                    if "기사 목록" in parsed and parsed["기사 목록"]:
                        first = parsed["기사 목록"][0]
                        return {
                            "article_id": first.get("article_id") or first.get("기사 id") or article_id,
                            "summary": (
                                first.get("summary")
                                or first.get("summary_text")
                                or first.get("요약본")
                                or first.get("요약문")
                                or first.get("요약")
                                or ""
                            ),
                        }

                    if "summary" in parsed:
                        return {
                            "article_id": parsed.get("article_id", article_id),
                            "summary": parsed.get("summary", ""),
                        }

            except json.JSONDecodeError:
                pass

            # 2-2. 현재 사진처럼 일반 텍스트로 온 경우 처리
            article_id_match = re.search(r"기사\s*id\s*:\s*(\d+)", text)
            summary_match = re.search(r"요약본\s*:\s*(.+)", text, re.DOTALL)

            return {
                "article_id": int(article_id_match.group(1)) if article_id_match else article_id,
                "summary": summary_match.group(1).strip() if summary_match else text,
            }

        # 3. 그 외 타입
        return {
            "article_id": article_id,
            "summary": str(summary_text),
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
            "user": f"user-{user_id}",
        }

        data = await self._post("/workflows/run", self.scoring_workflow_api_key, payload)

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
        # 본문이 없으면 Dify에 업로드할 수 없으므로 예외 발생
        if not article.content or not article.content.strip():
            raise DifyUploadError(f"article_id={article.id} 본문이 비어 있어 업로드할 수 없습니다.")

        try:
            # 기사 본문을 기반으로 Dify 문서 생성
            created = await self.knowledge_client.create_document_by_text(
                title=article.title or f"article-{article.id}",
                text=article.content,
            )

            document_id = created["document_id"]
            batch = created.get("batch")

            # 나중에 article_id로 추적할 수 있게 메타데이터 연결
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
        # 여러 기사를 순차적으로 업로드하고 성공/실패를 집계하는 메서드
        uploaded: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        for article in articles:
            try:
                result = await self.upload_article_to_knowledge(article)
                uploaded.append(result)
            except Exception as e:
                failed.append(
                    {
                        "article_id": getattr(article, "id", None),
                        "title": getattr(article, "title", None),
                        "error": str(e),
                    }
                )

        return {
            "uploaded_count": len(uploaded),
            "failed_count": len(failed),
            "uploaded": uploaded,
            "failed": failed,
        }