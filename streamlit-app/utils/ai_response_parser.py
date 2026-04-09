def extract_summary_text(result: dict) -> str:
    if not result:
        return "요약 결과가 없습니다."

    if result.get("success") is False:
        error = result.get("error") or {}
        return f"요약 생성 실패: {error.get('message', '알 수 없는 오류')}"

    data = result.get("data") or {}
    summary_text = data.get("summary_text")

    if summary_text:
        return summary_text

    return "요약 결과가 없습니다."


def extract_scoring_result(result: dict) -> list[dict]:
    if not result:
        return []

    if result.get("success") is False:
        return []

    data = result.get("data") or {}
    items = data.get("items")

    if isinstance(items, list):
        return items

    return []


def extract_error_message(result: dict, default_message: str = "알 수 없는 오류") -> str:
    if not result:
        return default_message

    error = result.get("error") or {}
    return error.get("message", default_message)