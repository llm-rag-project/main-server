from fastapi import APIRouter
from app.api.v1.ai import router as ai_router
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.keywords import router as keywords_router
from app.api.v1.articles import router as articles_router
from app.api.v1.importance import router as importance_router
from app.api.v1.crawl_runs import router as crawl_runs_router
from app.api.v1.chats import router as chats_router
from app.api.v1.credits import router as credits_router
from app.api.v1.stats import router as stats_router
from app.api.v1.reports import router as reports_router

api_router = APIRouter()

api_router.include_router(ai_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(keywords_router)
api_router.include_router(articles_router)
api_router.include_router(importance_router)
api_router.include_router(crawl_runs_router)
api_router.include_router(chats_router)
api_router.include_router(credits_router)
api_router.include_router(stats_router)
api_router.include_router(reports_router)