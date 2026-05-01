import os
from typing import Any

import httpx

from app.core.errors import ErrorCode, build_error


class DifyKnowledgeClientError(Exception):
    pass


class DifyKnowledgeClient:
    def __init__(self):
        self.base_url = os.getenv("DIFY_BASE_URL", "http://localhost/v1").rstrip("/")
        self.dataset_id = os.getenv("DIFY_DATASET_ID")
        self.api_key = os.getenv("KNOWLEDGE_API_KEY")
        self.article_id_metadata_field_id = os.getenv("DIFY_ARTICLE_ID_METADATA_FIELD_ID")

        if not self.dataset_id:
            raise ValueError("DIFY_DATASET_ID is not configured")
        if not self.api_key:
            raise ValueError("KNOWLEDGE_API_KEY is not configured")
        if not self.article_id_metadata_field_id:
            raise ValueError("DIFY_ARTICLE_ID_METADATA_FIELD_ID is not configured")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(url, headers=self._headers(), json=payload)
            except httpx.HTTPError as e:
                raise DifyKnowledgeClientError(f"Dify 요청 실패: {e}") from e

        try:
            result = response.json()
        except Exception as e:
            raise DifyKnowledgeClientError(
                f"Dify 응답 파싱 실패: {response.text}"
            ) from e

        if response.status_code >= 400 or result.get("success") is False:
            message = (
                result.get("error", {}).get("message")
                or response.text
                or "Failed to upload document to knowledge base"
            )
            raise DifyKnowledgeClientError(message)

        return result

    async def create_document_by_text(self, *, title: str, text: str) -> dict[str, Any]:
        payload = {
            "name": title,
            "text": text,
            "indexing_technique": "high_quality",
            "process_rule": {
                "mode": "automatic"
            },
        }

        result = await self._post(
            f"/datasets/{self.dataset_id}/document/create-by-text",
            payload,
        )

        data = result.get("data", {})
        document_id = data.get("document_id")
        if not document_id:
            raise DifyKnowledgeClientError("Dify document_id가 응답에 없습니다.")

        return {
            "document_id": document_id,
            "name": data.get("name"),
            "indexing_status": data.get("indexing_status"),
            "batch": data.get("batch"),
        }

    async def attach_article_id_metadata(self, *, document_id: str, article_id: int) -> None:
        payload = {
            "operation_data": [
                {
                    "document_id": document_id,
                    "metadata_list": [
                        {
                            "id": self.article_id_metadata_field_id,
                            "name": "article_id",
                            "value": article_id,
                        }
                    ],
                }
            ]
        }

        await self._post(
            f"/datasets/{self.dataset_id}/documents/metadata",
            payload,
        )