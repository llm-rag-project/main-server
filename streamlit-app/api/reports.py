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
