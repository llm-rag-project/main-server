import streamlit as st
import os
from dotenv import load_dotenv
from pathlib import Path

import api.keywords
from api.chat_rooms import create_chat, delete_chat, get_chat_detail, get_chat_list
from components.login_box import render_login_box
from utils.session import reset_chat, set_selected_keyword

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_PATH)
LOGIN_DISABLED = os.getenv("LOGIN_DISABLED", "false").lower() == "true"


def _unwrap(result):
    if not isinstance(result, dict):
        raise ValueError(f"응답 형식 오류: {type(result)}")
    if "success" in result:
        if not result.get("success", False):
            error = result.get("error")
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise ValueError(message or "요청 실패")
        return result.get("data", {})
    return result


def render_chat_session_sidebar():
    st.sidebar.divider()
    st.sidebar.subheader("💬 채팅 세션")

    # 새 세션 만들기
    with st.sidebar.expander("새 세션 만들기", expanded=False):
        with st.sidebar.form("create_chat_form_sidebar", clear_on_submit=True):
            new_title = st.text_input("세션 제목", key="sidebar_chat_title_input")
            submitted = st.form_submit_button("생성", width="stretch")

        if submitted:
            try:
                title = (new_title or "").strip()
                if not title:
                    st.sidebar.warning("제목을 입력하세요.")
                else:
                    result = create_chat(title=title)
                    data = _unwrap(result)
                    created_id = data.get("id")
                    if not created_id:
                        raise ValueError(f"id 없음: {data}")
                    st.session_state["selected_chat_id"] = created_id
                    st.session_state["chat_conversation_id"] = data.get("external_conversation_id") or ""
                    st.session_state["chat_messages"] = []
                    st.sidebar.success("세션 생성 완료!")
                    st.rerun()
            except Exception as e:
                st.sidebar.error(f"생성 실패: {e}")

    # 세션 목록
    try:
        result = get_chat_list(page=1, size=50)
        data = _unwrap(result)
        items = data.get("items", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

        if not items:
            st.sidebar.caption("채팅 세션이 없습니다.")
        else:
            for chat in items:
                if not isinstance(chat, dict):
                    continue
                chat_id = chat.get("id")
                title = chat.get("title", f"세션 {chat_id}")
                is_selected = st.session_state.get("selected_chat_id") == chat_id
                label = f"✅ {title}" if is_selected else title

                if st.sidebar.button(label, key=f"sb_chat_{chat_id}", width="stretch"):
                    try:
                        detail = _unwrap(get_chat_detail(chat_id))
                        st.session_state["selected_chat_id"] = detail.get("id")
                        st.session_state["chat_conversation_id"] = detail.get("external_conversation_id") or ""
                        st.session_state["chat_messages"] = []
                        last_msg = chat.get("last_message")
                        if last_msg:
                            st.session_state["chat_messages"].append({"role": "assistant", "content": last_msg})
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"선택 실패: {e}")

                if st.sidebar.button("🗑️", key=f"sb_del_{chat_id}", width="stretch"):
                    try:
                        _unwrap(delete_chat(chat_id))
                        if st.session_state.get("selected_chat_id") == chat_id:
                            st.session_state["selected_chat_id"] = None
                            st.session_state["chat_conversation_id"] = ""
                            st.session_state["chat_messages"] = []
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"삭제 실패: {e}")

    except Exception as e:
        st.sidebar.error(f"세션 목록 오류: {e}")


def render_sidebar():
    st.sidebar.title("키워드 관리")

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

    if not keywords:
        st.sidebar.info("등록된 키워드가 없습니다.")

    for kw in keywords:
        keyword_id = kw.get("id")
        keyword_name = kw.get("keyword", "이름 없음")
        is_active = kw.get("is_active", True)

        row1, row2 = st.sidebar.columns([4, 1])
        label = keyword_name if is_active else f"{keyword_name} (비활성)"

        if row1.button(label, key=f"kw_{keyword_id}", width="stretch"):
            set_selected_keyword(keyword_id, keyword_name)
            reset_chat()
            st.rerun()

        if row2.button("X", key=f"del_{keyword_id}", width="stretch"):
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

    if st.sidebar.button("키워드 추가", width="stretch"):
        if not new_keyword.strip():
            st.sidebar.warning("키워드를 입력해주세요.")
        else:
            try:
                with st.sidebar:
                    with st.spinner("키워드 등록, 기사 크롤링 요청 중..."):
                        result = api.keywords.create_keyword_and_crawl(new_keyword.strip())

                created_keyword = result.get("keyword", {})
                created_keyword_id = created_keyword.get("id")
                created_keyword_name = created_keyword.get("keyword", new_keyword.strip())

                if created_keyword_id:
                    set_selected_keyword(created_keyword_id, created_keyword_name)
                    reset_chat()

                st.sidebar.success("키워드 등록 및 크롤링 요청 완료!")
                st.rerun()

            except Exception as e:
                st.sidebar.error(f"추가 실패: {e}")

    selected_name = st.session_state.get("selected_keyword_name")
    if selected_name:
        st.sidebar.caption(f"현재 선택: {selected_name}")

    # ✅ 채팅 세션을 사이드바 하단에 배치
    render_chat_session_sidebar()