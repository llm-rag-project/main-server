def extract_summary_text(result: dict) -> str:
    if not isinstance(result, dict):
        return "요약 결과가 없습니다."

    summary_text = (
        result.get("summary_text")
        or result.get("summary")
        or result.get("result")
        or result.get("text")
    )
    return summary_text or "요약 결과가 없습니다."


def extract_scoring_result(result: dict) -> list[dict]:
    if not isinstance(result, dict):
        return []

    items = result.get("results") or result.get("items") or []
    return items if isinstance(items, list) else []


def extract_error_message(result: dict, default_message: str = "알 수 없는 오류") -> str:
    if not isinstance(result, dict):
        return default_message

    error = result.get("error") or {}
    return error.get("message", default_message)
