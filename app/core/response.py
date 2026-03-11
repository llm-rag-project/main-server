#공통 응답 빌더 
from typing import Any #어떤 타입이든 들어올 수 있도록 하는 타입 힌트

from fastapi import Request #HTTP 요청 객체
from fastapi.responses import JSONResponse #JSON HTTP 응답을 만들어주는 객체


def success_response( #성공응답 표준 형식으로 만들어 반환
    request: Request,
    data: Any,
    status_code: int = 200,
) -> JSONResponse:
    payload = {
        "success": True,
        "data": data,
        "error": None,
        "meta": {
            "request_id": request.state.request_id,
        },
    }
    return JSONResponse(status_code=status_code, content=payload)


def error_response( #실패 응답 표준 형식으로 만들어 반환
    request: Request,
    *,#이 기호는 뒤의 인자들을 키워드 전용 인자로 만들기 위한 문법 <- "NOT_FOUND" 대신  code="NOT_FOUND"로!!
    code: str,
    message: str,
    status_code: int,
    details: Any | None = None,
) -> JSONResponse:
    error = {
        "code": code,
        "message": message,
    }
    if details is not None:
        error["details"] = details

    payload = {
        "success": False,
        "data": None,
        "error": error,
        "meta": {
            "request_id": getattr(request.state, "request_id", None),
        },
    }
    return JSONResponse(status_code=status_code, content=payload)