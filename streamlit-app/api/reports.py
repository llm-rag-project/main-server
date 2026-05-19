from typing import Optional

import streamlit as st

from api.client import BASE_URL, get_headers
import requests


def download_daily_report(keyword_id: Optional[int] = None) -> bytes:
    """데일리 리포트 Excel 파일을 bytes로 반환"""
    params = {}
    if keyword_id:
        params["keyword_id"] = keyword_id

    response = requests.get(
        f"{BASE_URL}/reports/daily",
        headers=get_headers(),
        params=params,
        timeout=60,
    )
    response.raise_for_status()
    return response.content


def send_report_email(
    to_emails: list[str],
    keyword_id: Optional[int] = None,
    keyword_name: Optional[str] = None,
) -> dict:
    """데일리 리포트를 이메일로 발송"""
    payload = {"to_emails": to_emails}
    if keyword_id is not None:
        payload["keyword_id"] = keyword_id
    if keyword_name is not None:
        payload["keyword_name"] = keyword_name

    response = requests.post(
        f"{BASE_URL}/reports/email",
        headers=get_headers(),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    body = response.json()
    # 다른 API 함수들과 동일하게 {"success": true, "data": {...}} 에서 data를 꺼냄
    return body.get("data", body) if isinstance(body, dict) else body
