from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.middleware import RequestIDMiddleware
from app.core.response import error_response
from app.db.base import Base
from app.db.session import engine
from app.models.user import User
from app.models.credit import CreditWallet, CreditTransaction
from app.models.auth_refresh_token import AuthRefreshToken
from app.services.crawl_scheduler_service import start_scheduler, shutdown_scheduler
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH, override=True)

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.add_middleware(RequestIDMiddleware)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    start_scheduler()


@app.on_event("shutdown")
async def on_shutdown():
    shutdown_scheduler()


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