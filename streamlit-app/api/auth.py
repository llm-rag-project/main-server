import streamlit as st

from api.client import api_get, api_post
from utils.session import clear_auth_state, set_auth_state


def login(email: str, password: str):
    payload = {
        "email": email,
        "password": password,
    }

    # 로그인은 토큰 없이 요청
    result = api_post("/auth/login", payload, with_auth=False)

    # 실제 응답 구조에 맞게 토큰 추출
    access_token = result.get("access_token") or result.get("accessToken")
    refresh_token = result.get("refresh_token") or result.get("refreshToken")

    if not access_token:
        raise ValueError("로그인 응답에 access_token이 없습니다.")

    user = None
    set_auth_state(access_token=access_token, refresh_token=refresh_token, user=user)

    # 로그인 후 사용자 정보 조회
    try:
        me = get_me()
        st.session_state["user"] = me
    except Exception:
        pass

    return result


def get_me():
    return api_get("/users/me", with_auth=True)


def logout():
    refresh_token = st.session_state.get("refresh_token")

    try:
        if refresh_token:
            api_post("/auth/logout", {"refresh_token": refresh_token}, with_auth=True)
    except Exception:
        pass

    clear_auth_state()