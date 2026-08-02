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
        self.keyword_id_metadata_field_id = os.getenv("DIFY_KEYWORD_ID_METADATA_FIELD_ID")
        self.keyword_text_metadata_field_id = os.getenv("DIFY_KEYWORD_TEXT_METADATA_FIELD_ID")

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

    def _extract_document_payload(self, result: dict[str, Any]) -> tuple[str | None, dict[str, Any], str | None]:
        containers = [
            result,
            result.get("data") if isinstance(result.get("data"), dict) else {},
        ]
        candidates: list[dict[str, Any]] = []
        for container in containers:
            if not isinstance(container, dict):
                continue
            candidates.append(container)
            document = container.get("document")
            if isinstance(document, dict):
                candidates.append(document)

        document_id = None
        document_data: dict[str, Any] = {}
        for candidate in candidates:
            document_id = candidate.get("document_id") or candidate.get("id") or candidate.get("documentId")
            if document_id:
                document_data = candidate
                break

        batch = None
        for container in containers:
            if isinstance(container, dict):
                batch = container.get("batch") or container.get("batch_id") or batch

        return document_id, document_data, batch

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

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.get(url, headers=self._headers(), params=params)
            except httpx.HTTPError as e:
                raise DifyKnowledgeClientError(f"Dify 요청 실패: {e}") from e

        try:
            result = response.json()
        except Exception as e:
            raise DifyKnowledgeClientError(f"Dify 응답 파싱 실패: {response.text}") from e

        if response.status_code >= 400 or result.get("success") is False:
            message = (
                result.get("error", {}).get("message")
                or response.text
                or "Failed to fetch documents from knowledge base"
            )
            raise DifyKnowledgeClientError(message)

        return result

    async def _delete(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.delete(url, headers=self._headers())
            except httpx.HTTPError as e:
                raise DifyKnowledgeClientError(f"Dify 삭제 요청 실패: {e}") from e

        if response.status_code in (200, 202, 204):
            if not response.content:
                return {"success": True}
            try:
                return response.json()
            except Exception:
                return {"success": True}

        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise DifyKnowledgeClientError(f"Dify 삭제 실패 status={response.status_code}, detail={detail}")

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

        document_id, document_data, batch = self._extract_document_payload(result)
        if not document_id:
            raise DifyKnowledgeClientError(f"Dify document_id가 응답에 없습니다. response={result}")

        return {
            "document_id": document_id,
            "name": document_data.get("name"),
            "indexing_status": document_data.get("indexing_status"),
            "batch": batch or document_data.get("batch"),
        }

    async def search_documents(self, *, keyword: str, page: int = 1, limit: int = 10) -> list[dict[str, Any]]:
        result = await self._get(
            f"/datasets/{self.dataset_id}/documents",
            params={"keyword": keyword, "page": page, "limit": limit},
        )
        data = result.get("data")
        return data if isinstance(data, list) else []

    def _normalize_document_name(self, value: str | None) -> str:
        return " ".join(str(value or "").split()).casefold()

    async def find_document_by_title(self, *, title: str) -> dict[str, Any] | None:
        title_key = self._normalize_document_name(title)
        if not title_key:
            return None

        documents = await self.search_documents(keyword=title, limit=10)
        for document in documents:
            name_key = self._normalize_document_name(document.get("name"))
            if name_key == title_key:
                return document

        for document in documents:
            name_key = self._normalize_document_name(document.get("name"))
            if title_key in name_key or name_key in title_key:
                return document
        return None

    async def attach_article_id_metadata(self, *, document_id: str, article_id: int) -> None:
        await self.attach_article_keyword_metadata(document_id=document_id, article_id=article_id)

    async def attach_article_keyword_metadata(
        self,
        *,
        document_id: str,
        article_id: int,
        keyword_id: int | None = None,
        keyword_text: str | None = None,
    ) -> None:
        metadata_list = [
            {
                "id": self.article_id_metadata_field_id,
                "name": "article_id",
                "value": article_id,
            }
        ]
        if self.keyword_id_metadata_field_id and keyword_id is not None:
            metadata_list.append(
                {
                    "id": self.keyword_id_metadata_field_id,
                    "name": "keyword_id",
                    "value": keyword_id,
                }
            )
        if self.keyword_text_metadata_field_id and keyword_text:
            metadata_list.append(
                {
                    "id": self.keyword_text_metadata_field_id,
                    "name": "keyword_text",
                    "value": keyword_text,
                }
            )

        payload = {
            "operation_data": [
                {
                    "document_id": document_id,
                    "metadata_list": metadata_list,
                }
            ]
        }

        await self._post(
            f"/datasets/{self.dataset_id}/documents/metadata",
            payload,
        )

    async def delete_document(self, *, document_id: str) -> dict[str, Any]:
        return await self._delete(f"/datasets/{self.dataset_id}/documents/{document_id}")
