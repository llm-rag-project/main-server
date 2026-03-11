import uuid #python dml uuid생성모델 -> 랜덤 기반 UUID 생성

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next): #매 HTTP 요청마다 자동으로 실행
        request_id = f"req_{uuid.uuid4().hex}" #고유 요청 ID 생성
        request.state.request_id = request_id #FastApi에서 요청 처리 중 임시 데이터를 거장하는 공간인 request.state에 request_id 저장

        response = await call_next(request) # 다음 단계(실제 요청 처리) 진행
        response.headers["X-Request-ID"] = request_id #응답헤더에 request_id 추가
        return response