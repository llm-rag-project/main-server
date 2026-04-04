import streamlit as st

from api.articles import get_articles
from api.client import api_get, api_post


def render_summary_cards():
    selected_keyword = st.session_state.get("selected_keyword_name")
    keyword_id = st.session_state.get("selected_keyword_id")

    article_count = 0
    importance_count = 0

    try:
        articles, _ = get_articles(keyword_id=keyword_id, page=1, size=100)
        article_count = len(articles)
    except Exception:
        articles = []

    try:
        params = {"page": 1, "size": 100}
        if keyword_id:
            params["keyword_id"] = keyword_id

        result = api_get("/importance", params=params)
        importance_items = result.get("items", []) if isinstance(result, dict) else []
        st.session_state["importance_items"] = importance_items
        importance_count = len(importance_items)
    except Exception:
        st.session_state["importance_items"] = []

    col1, col2, col3 = st.columns(3)
    col1.metric("선택 키워드", selected_keyword if selected_keyword else "-")
    col2.metric("기사 수", article_count)
    col3.metric("중요도 결과 수", importance_count)

    st.markdown("### 중요도 상위 항목")
    items = st.session_state.get("importance_items", [])
    if items:
        for item in items[:5]:
            st.write(
                f"- {item.get('title', '제목 없음')} | "
                f"score={item.get('score', '-')} | "
                f"status={item.get('status', '-')}"
            )
    else:
        st.caption("중요도 데이터가 없습니다.")

    st.markdown("### 중요도 실행")
    if st.button("선택 키워드 기사 중요도 계산"):
        if not keyword_id:
            st.warning("먼저 키워드를 선택하세요.")
            return

        try:
            article_ids = [a["id"] for a in articles if a.get("id")]

            if not article_ids:
                st.warning("해당 키워드에 연결된 기사가 없습니다.")
                return

            result = api_post("/importance/run", {"article_ids": article_ids})
            st.success("중요도 계산 요청 완료")
            st.json(result)
        except Exception as e:
            st.error(f"중요도 실행 실패: {e}")