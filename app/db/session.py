#FastAPI에서 PostgresSQL을 비동기로 사용하기 위한 SQLAlchemy 설정 코드
#핵심목적=DB연결 만들고, DB 작업 할 수 있는 Session을 준비하는 것
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

#DB연결 객체(engine)을 만드는 코드
engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    future=True
)
#Session생성기(Factory)를 만드는 코드
AsyncSessionLocal = async_sessionmaker(
    bind=engine, # 이 세션은 이 engine(DB)에 연결됨
    class_=AsyncSession, #비동기세션 사용
    expire_on_commit=False, #commit후에도 객체 데이터 유지
)
