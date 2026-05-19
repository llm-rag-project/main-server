"""
인메모리 Job 진행상황 저장소.
백엔드가 Dify 같은 외부 AI 서버와 통신하는 동안,
프론트엔드가 GET /jobs/{job_id} 를 폴링해서 진행률을 확인한다.
"""
import uuid
from datetime import datetime, timezone

# { job_id: { status, progress, message, result, error, created_at } }
_jobs: dict[str, dict] = {}


def create_job(job_type: str, job_id: str | None = None) -> str:
    """새 job 생성. job_id를 지정하면 그대로 사용 (프론트에서 UUID 전달 시)."""
    jid = job_id or str(uuid.uuid4())
    _jobs[jid] = {
        "job_id": jid,
        "type": job_type,
        "status": "running",   # running | done | error
        "progress": 0,         # 0 ~ 100
        "message": "시작 중...",
        "result": None,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return jid


def update_job(job_id: str, *, progress: int, message: str) -> None:
    """진행률·메시지 업데이트."""
    if job_id in _jobs:
        _jobs[job_id]["progress"] = progress
        _jobs[job_id]["message"] = message


def complete_job(job_id: str, result: dict | None = None) -> None:
    """작업 완료 처리."""
    if job_id in _jobs:
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["message"] = "완료"
        _jobs[job_id]["result"] = result


def fail_job(job_id: str, error: str) -> None:
    """작업 실패 처리."""
    if job_id in _jobs:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["message"] = f"오류: {error}"
        _jobs[job_id]["error"] = error


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)
