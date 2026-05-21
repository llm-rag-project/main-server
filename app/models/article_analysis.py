from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ArticleAnalysis(Base, TimestampMixin):
    """크롤링 후 AI 분석 결과 (감성 / 홍보성) 저장 테이블."""

    __tablename__ = "article_analysis"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("articles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    # 감성: 긍정 / 부정 / 중립 / 분석실패
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 홍보성: True=홍보성, False=일반, None=분석실패
    is_promotion: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    article = relationship("Article", back_populates="analysis")
