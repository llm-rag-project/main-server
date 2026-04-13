from app.core.dify_knowledge_client import DifyKnowledgeClient


class DifyKnowledgeService:
    def __init__(self, client: DifyKnowledgeClient | None = None):
        self.client = client or DifyKnowledgeClient()

    async def upload_article(self, article) -> dict:
        title = (article.title or "").strip()
        content = (article.content or "").strip()

        if not title:
            title = f"article-{article.id}"

        if not content:
            raise ValueError(f"기사 본문이 비어 있어 Dify 업로드 불가: article_id={article.id}")

        document_id = await self.client.create_document_by_text(
            name=title,
            text=content,
        )

        await self.client.attach_article_id_metadata(
            document_id=document_id,
            article_id=article.id,
        )

        return {
            "article_id": article.id,
            "document_id": document_id,
        }