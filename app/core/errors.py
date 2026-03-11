#To make standard error code /custom
from dataclasses import dataclass
from typing import Any


@dataclass #이 어노테이션이 자동으로 생성자 생성해줌
class AppError(Exception):
    code: str
    message: str
    status_code: int
    details: Any | None = None


class ErrorCode:
    VALIDATION_ERROR = ("VALIDATION_ERROR", 400)
    INVALID_CREDENTIALS = ("INVALID_CREDENTIALS", 401)
    AUTH_REQUIRED = ("AUTH_REQUIRED", 401)
    
    REFRESH_TOKEN_INVALID = ("REFRESH_TOKEN_INVALID", 401)
    TOKEN_REVOKED = ("TOKEN_REVOKED", 401)
    TOKEN_MISMATCH = ("TOKEN_MISMATCH", 403)
    
    FORBIDDEN = ("FORBIDDEN", 403)
    NOT_FOUND = ("NOT_FOUND", 404)
    CONFLICT_DUPLICATE = ("CONFLICT_DUPLICATE", 409)
    CREDITS_INSUFFICIENT = ("CREDITS_INSUFFICIENT", 422)
    RATE_LIMITED = ("RATE_LIMITED", 429)
    UPSTREAM_ERROR = ("UPSTREAM_ERROR", 502)
    INTERNAL_ERROR = ("INTERNAL_ERROR", 500)


#AppError 객체를 쉽게 만들기 위한 헬퍼 함수
#AppError는 API용 에러 구조를 강제하기 위한 객체
def build_error(error_tuple: tuple[str, int], message: str, details: Any | None = None) -> AppError:
    code, status_code = error_tuple
    return AppError(code=code, message=message, status_code=status_code, details=details)