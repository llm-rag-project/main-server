from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Translation(Base, TimestampMixin):
    __tablename__ = "translations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_lang: Mapped[str] = mapped_column(String(10), nullable=False)
    target_lang: Mapped[str] = mapped_column(String(10), nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    engine_name: Mapped[str] = mapped_column(String(200), nullable=False)

    article = relationship("Article", back_populates="translations")

    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "source_lang",
            "target_lang",
            "engine_name",
            name="uq_translations_article_lang_engine",
        ),
    )