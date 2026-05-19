from fastapi import APIRouter, Request

from app.core.errors import ErrorCode, build_error
from app.core.job_store import get_job
from app.core.response import success_response

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
async def get_job_status(request: Request, job_id: str):
    """프론트엔드가 1초마다 폴링해서 진행률을 확인하는 엔드포인트."""
    job = get_job(job_id)
    if job is None:
        raise build_error(ErrorCode.NOT_FOUND, f"Job '{job_id}' 을 찾을 수 없습니다.")
    return success_response(request, data=job)
