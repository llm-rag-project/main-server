import streamlit as st

from api.articles import get_articles
from api.client import api_get


def render_summary_cards():
    selected_keyword = st.session_state.get("selected_keyword_name")
    keyword_id = st.session_state.get("selected_keyword_id")

    article_count = 0
    importance_count = 0

    try:
        _, page_info = get_articles(keyword_id=keyword_id, page=1, size=1)
        article_count = page_info.get("total", 0) if page_info else 0
    except Exception:
        pass

    try:
        params = {"page": 1, "size": 5}
        if keyword_id:
            params["keyword_id"] = keyword_id

        result = api_get("/importance", params=params)
        # api_get이 data를 unwrap → result = {"items": [...], "page_info": {...}}
        importance_items = result.get("items", []) if isinstance(result, dict) else []
        page_info_imp = result.get("page_info") if isinstance(result, dict) else None
        importance_count = page_info_imp.get("total", len(importance_items)) if page_info_imp else len(importance_items)

        st.session_state["importance_items"] = importance_items
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
