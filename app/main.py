from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.middleware import RequestIDMiddleware
from app.core.response import error_response
from app.db.base import Base
from app.db.session import engine
from app.services.crawl_scheduler_service import shutdown_scheduler, start_scheduler

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH, override=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE articles ADD COLUMN IF NOT EXISTS thumbnail_url TEXT"))
        await conn.execute(text("ALTER TABLE articles ADD COLUMN IF NOT EXISTS canonical_url TEXT"))
        await conn.execute(text("ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_fingerprint VARCHAR(64)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_articles_canonical_url ON articles(canonical_url)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_articles_content_fingerprint ON articles(content_fingerprint)"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS crawl_interval_minutes INTEGER NOT NULL DEFAULT 1440"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS crawl_limit INTEGER NOT NULL DEFAULT 10"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS email_auto_send BOOLEAN NOT NULL DEFAULT false"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS email_recipients TEXT"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS email_send_time VARCHAR(5) NOT NULL DEFAULT '08:30'"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS email_condition_type VARCHAR(40) NOT NULL DEFAULT 'daily_summary'"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS alert_negative_rate_threshold INTEGER NOT NULL DEFAULT 25"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS alert_importance_threshold INTEGER NOT NULL DEFAULT 80"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS alert_article_count_threshold INTEGER NOT NULL DEFAULT 10"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS importance_criteria TEXT"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS dashboard_mode VARCHAR(20) NOT NULL DEFAULT 'general'"))
        await conn.execute(text("UPDATE keywords SET dashboard_mode = 'dongguk' WHERE keyword_text ILIKE '%동국%'"))
        await conn.execute(text("UPDATE keywords SET dashboard_mode = 'general' WHERE dashboard_mode IS NULL OR dashboard_mode = ''"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_keywords_user_dashboard_mode ON keywords(user_id, dashboard_mode)"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS client_name VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS group_name VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS monitoring_type VARCHAR(40) NOT NULL DEFAULT 'brand'"))
        await conn.execute(text("ALTER TABLE keywords ADD COLUMN IF NOT EXISTS priority_level VARCHAR(20) NOT NULL DEFAULT 'normal'"))
        await conn.execute(text("ALTER TABLE chats ADD COLUMN IF NOT EXISTS keyword_id BIGINT REFERENCES keywords(id) ON DELETE CASCADE"))
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_chats_user_keyword_not_null ON chats(user_id, keyword_id) WHERE keyword_id IS NOT NULL"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chats_user_keyword ON chats(user_id, keyword_id)"))
        await conn.execute(text("ALTER TABLE dongguk_mail_drafts ADD COLUMN IF NOT EXISTS removed_article_keys TEXT NOT NULL DEFAULT '[]'"))
        await conn.execute(text("ALTER TABLE dongguk_mail_drafts ADD COLUMN IF NOT EXISTS removed_articles TEXT NOT NULL DEFAULT '[]'"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dongguk_article_trash (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                keyword_id BIGINT,
                mail_date VARCHAR(10) NOT NULL,
                article_id BIGINT NOT NULL,
                article_body TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
                CONSTRAINT uq_dongguk_trash_user_keyword_date_article UNIQUE (user_id, keyword_id, mail_date, article_id)
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dongguk_trash_user_date ON dongguk_article_trash(user_id, mail_date)"))
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return error_response(
        request,
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []))
        details.append(
            {
                "field": loc,
                "reason": err.get("msg", "invalid"),
            }
        )

    return error_response(
        request,
        code=ErrorCode.VALIDATION_ERROR[0],
        message="Validation error",
        status_code=ErrorCode.VALIDATION_ERROR[1],
        details=details,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return error_response(
        request,
        code=ErrorCode.INTERNAL_ERROR[0],
        message="Internal server error",
        status_code=ErrorCode.INTERNAL_ERROR[1],
    )


@app.get("/")
async def health():
    return {"status": "ok"}
