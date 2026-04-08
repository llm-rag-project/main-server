# import streamlit as st

# from api.client import api_get, api_post
# from utils.session import clear_auth_state, set_auth_state


# def login(email: str, password: str):
#     payload = {
#         "email": email,
#         "password": password,
#     }

#     result = api_post("/auth/login", payload, with_auth=False)

#     access_token = result.get("access_token") or result.get("accessToken")
#     refresh_token = result.get("refresh_token") or result.get("refreshToken")

#     if not access_token:
#         raise ValueError(f"로그인 응답에 access_token이 없습니다: {result}")

#     # 1) 먼저 임시로 토큰 저장
#     st.session_state["access_token"] = access_token
#     st.session_state["refresh_token"] = refresh_token

#     # 2) 토큰으로 실제 인증 검증
#     try:
#         me = get_me()
#     except Exception as e:
#         clear_auth_state()
#         raise ValueError(f"로그인은 됐지만 토큰 검증에 실패했습니다: {e}")

#     # 3) 검증 성공한 경우만 로그인 상태 확정
#     set_auth_state(
#         access_token=access_token,
#         refresh_token=refresh_token,
#         user=me,
#     )

#     return result


# def signup(email: str, password: str, name: str | None = None):
#     payload = {
#         "email": email,
#         "password": password,
#     }

#     if name:
#         payload["name"] = name

#     return api_post("/auth/signup", payload, with_auth=False)


# def get_me():
#     return api_get("/users/me", with_auth=True)


# def logout():
#     refresh_token = st.session_state.get("refresh_token")

#     try:
#         if refresh_token:
#             api_post("/auth/logout", {"refresh_token": refresh_token}, with_auth=True)
#     except Exception:
#         pass

#     clear_auth_state()