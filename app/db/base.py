from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func

#이 클래스는 모든 ORM 모델의 부모 클래스
class Base(DeclarativeBase):
    pass

#Mixin이란, 여러 클래스에서 재사용할 필드나 기능을 제공하는 클래스
#created_at,updated_at 컬럼을 재사용하기 위해
class TimestampMixin:
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(), #UPDATE 될 때마다 자동으로 NOW()로 갱신
    )

# Alembic autogenerate용
import app.models  # noqa