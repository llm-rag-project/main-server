from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.keywords import router as keywords_router
from app.api.v1.articles import router as articles_router
from app.api.v1.feedbacks import router as feedbacks_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(keywords_router)
api_router.include_router(articles_router)
api_router.include_router(feedbacks_router)