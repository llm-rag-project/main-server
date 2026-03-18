from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def success_response(
    request: Request,
    data: Any,
    status_code: int = 200,
) -> JSONResponse:
    payload = {
        "success": True,
        "data": jsonable_encoder(data),
        "error": None,
        "meta": {
            "request_id": request.state.request_id,
        },
    }
    return JSONResponse(status_code=status_code, content=payload)


def error_response(
    request: Request,
    *,
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
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))