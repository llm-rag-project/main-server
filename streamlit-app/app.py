import os

import streamlit as st
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env", override=False)

from components.article_actions import render_article_action_buttons
from components.article_list import render_article_list
from components.chat_box import render_chat_box
from components.chat_list import render_chat_list
from components.sidebar import LOGIN_DISABLED, render_sidebar
from components.summary_cards import render_summary_cards
from components.stats_chart import render_stats_charts
from utils.session import init_state

APP_TITLE = os.getenv("APP_TITLE", "AI Agent 기반 기사 모니터링")

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📰",
    layout="wide",
)

init_state()


def render_header():
    st.title(APP_TITLE)
    st.caption("메인서버 + AI서버 연동 Streamlit 화면")


def main():
    render_sidebar()
    render_header()

    if not LOGIN_DISABLED and not st.session_state.get("is_logged_in"):
        st.warning("왼쪽 사이드바에서 로그인하세요.")
        st.stop()

    selected_keyword_id = st.session_state.get("selected_keyword_id")
    if not selected_keyword_id:
        st.warning("왼쪽 사이드바에서 키워드를 선택하세요.")
        st.stop()

    render_summary_cards()
    st.markdown("---")

    tab_articles, tab_stats = st.tabs(["📰 기사 목록", "📊 통계 그래프"])

    with tab_articles:
        left, right = st.columns([3, 2])

        with left:
            render_article_action_buttons()
            st.markdown("---")
            render_article_list()

        with right:
            st.markdown("## AI 채팅")
            render_chat_list()
            st.markdown("---")
            render_chat_box()

    with tab_stats:
        render_stats_charts()


if __name__ == "__main__":
    main()