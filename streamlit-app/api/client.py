import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import streamlit as st
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = Path(__file__).resolve().parents[2] / "main-server" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

BASE_URL = os.getenv("BASE_URL", "http://localhost:8001/api/v1")
TIMEOUT = 240


class APIError(Exception):
    pass


def get_headers(with_auth: bool = True) -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
    }

    if with_auth:
        token = st.session_state.get("access_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"

    return headers


def unwrap_response(response_json: Dict[str, Any]) -> Any:
    if isinstance(response_json, dict) and "data" in response_json:
        return response_json["data"]
    return response_json


def handle_response(response: requests.Response) -> Any:
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise APIError(f"HTTP {response.status_code}: {detail}") from e

    if not response.text.strip():
        return None

    try:
        result = response.json()
    except Exception as e:
        raise APIError(f"JSON 파싱 실패: {response.text}") from e

    return unwrap_response(result)


def _request(
    method: str,
    base_url: str,
    path: str,
    *,
    data=None,
    params=None,
    with_auth=True,
    headers: Optional[Dict[str, str]] = None,
):
    url = f"{base_url}{path}"

    final_headers = get_headers(with_auth=with_auth)
    if headers:
        final_headers.update(headers)

    response = requests.request(
        method=method,
        url=url,
        headers=final_headers,
        json=data,
        params=params,
        timeout=TIMEOUT,
    )
    return handle_response(response)


def api_get(path: str, params: Optional[Dict[str, Any]] = None, with_auth: bool = False) -> Any:
    return _request("GET", BASE_URL, path, params=params, with_auth=with_auth)


def api_post(path: str, data: Optional[Dict[str, Any]] = None, with_auth: bool = False) -> Any:
    return _request("POST", BASE_URL, path, data=data, with_auth=with_auth)


def api_patch(path: str, data: Optional[Dict[str, Any]] = None, with_auth: bool = False) -> Any:
    return _request("PATCH", BASE_URL, path, data=data, with_auth=with_auth)


def api_delete(path: str, with_auth: bool = False) -> Any:
    return _request("DELETE", BASE_URL, path, with_auth=with_auth)