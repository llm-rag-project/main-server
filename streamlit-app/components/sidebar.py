import streamlit as st
import os
from dotenv import load_dotenv
from pathlib import Path

import api.keywords
from components.login_box import render_login_box
from utils.session import reset_chat, set_selected_keyword
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)
LOGIN_DISABLED = os.getenv("LOGIN_DISABLED", "false").lower() == "true"

def render_sidebar():
    st.sidebar.title("키워드 관리")

    # render_login_box()

    # if not st.session_state.get("is_logged_in"):
    #     st.sidebar.info("로그인 후 키워드를 조회할 수 있습니다.")
    #     return
    
    if not LOGIN_DISABLED:
        render_login_box()

        if not st.session_state.get("is_logged_in"):
            st.sidebar.info("로그인 후 키워드를 조회할 수 있습니다.")
            return
    else:
        st.sidebar.caption("개발 모드: 로그인 비활성화")
        
        
    try:
        keywords, page_info = api.keywords.get_keywords(page=1, size=100)
        st.session_state["keyword_page_info"] = page_info
    except Exception as e:
        st.sidebar.error(f"키워드 목록 조회 실패: {e}")
        keywords = []
    keyword_ids = {kw.get("id") for kw in keywords if kw.get("id") is not None}
    selected_keyword_id = st.session_state.get("selected_keyword_id")

    if selected_keyword_id and selected_keyword_id not in keyword_ids:
        st.session_state["selected_keyword_id"] = None
        st.session_state["selected_keyword_name"] = None
        st.sidebar.subheader("키워드 리스트")

    if not keywords:
        st.sidebar.info("등록된 키워드가 없습니다.")

    for kw in keywords:
        keyword_id = kw.get("id")
        keyword_name = kw.get("keyword", "이름 없음")
        is_active = kw.get("is_active", True)

        row1, row2 = st.sidebar.columns([4, 1])

        label = keyword_name
        if not is_active:
            label += " (비활성)"

        if row1.button(label, key=f"kw_{keyword_id}", use_container_width=True):
            set_selected_keyword(keyword_id, keyword_name)
            reset_chat()
            st.rerun()

        if row2.button("X", key=f"del_{keyword_id}", use_container_width=True):
            try:
                api.keywords.delete_keyword(keyword_id)
                if st.session_state.get("selected_keyword_id") == keyword_id:
                    st.session_state["selected_keyword_id"] = None
                    st.session_state["selected_keyword_name"] = None
                    reset_chat()
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"삭제 실패: {e}")

        toggle_key = f"toggle_{keyword_id}"
        new_active = st.sidebar.checkbox(
            f"{keyword_name} 활성",
            value=is_active,
            key=toggle_key,
        )

        if new_active != is_active:
            try:
                api.keywords.update_keyword_active(keyword_id, new_active)
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"상태 변경 실패: {e}")

    st.sidebar.divider()

    new_keyword = st.sidebar.text_input("새 키워드", placeholder="예: 하이닉스")

    if st.sidebar.button("키워드 추가", use_container_width=True):
        if not new_keyword.strip():
            st.sidebar.warning("키워드를 입력해주세요.")
        else:
            try:
                result = api.keywords.create_keyword_and_crawl(new_keyword.strip())

                created_keyword = result.get("keyword", {})
                created_keyword_id = created_keyword.get("id")
                created_keyword_name = created_keyword.get("keyword", new_keyword.strip())

                if created_keyword_id:
                    set_selected_keyword(created_keyword_id, created_keyword_name)
                    reset_chat()

                st.sidebar.success("키워드 등록 및 크롤링 요청 완료")
                st.rerun()

            except Exception as e:
                st.sidebar.error(f"추가 실패: {e}")

    st.sidebar.divider()

    selected_name = st.session_state.get("selected_keyword_name")
    if selected_name:
        st.sidebar.caption(f"현재 선택: {selected_name}")
    else:
        st.sidebar.caption("선택된 키워드 없음")