from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class DifyKnowledgeDocument(Base, TimestampMixin):
    __tablename__ = "dify_knowledge_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    article_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    keyword_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("keywords.id", ondelete="SET NULL"), nullable=True)
    keyword_text: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(255), nullable=False)
    document_id: Mapped[str] = mapped_column(String(255), nullable=False)
    batch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="UPLOADED", server_default="UPLOADED")
    delete_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User")
    article = relationship("Article")
    keyword = relationship("Keyword")

    __table_args__ = (
        UniqueConstraint("dataset_id", "document_id", name="uq_dify_knowledge_documents_dataset_document"),
        UniqueConstraint("article_id", "keyword_id", name="uq_dify_knowledge_documents_article_keyword"),
        Index("ix_dify_knowledge_documents_keyword", "keyword_id"),
        Index("ix_dify_knowledge_documents_article", "article_id"),
        Index("ix_dify_knowledge_documents_status", "status"),
    )
