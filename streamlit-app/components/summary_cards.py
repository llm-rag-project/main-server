import streamlit as st

from api.articles import get_articles
from api.client import api_get

RANK_MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]


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
        params = {"page": 1, "size": 5, "sort": "score_desc"}
        if keyword_id:
            params["keyword_id"] = keyword_id

        result = api_get("/importance", params=params)
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

    if not items:
        st.caption("중요도 데이터가 없습니다.")
        return

    for rank, item in enumerate(items[:5]):
        medal = RANK_MEDALS[rank]
        title = item.get("title") or "제목 없음"
        score = item.get("score")
        url = item.get("url", "")

        score_val = float(score) if score is not None else 0.0
        score_display = f"{score_val:.1f}"

        # 점수 색상 (100점 기준)
        if score_val >= 80:
            score_color = "#e74c3c"   # 빨강
        elif score_val >= 50:
            score_color = "#e67e22"   # 주황
        else:
            score_color = "#7f8c8d"   # 회색

        with st.container(border=True):
            col_rank, col_content, col_score = st.columns([1, 10, 2])

            col_rank.markdown(f"## {medal}")

            with col_content:
                if url:
                    st.markdown(f"**[{title}]({url})**")
                else:
                    st.markdown(f"**{title}**")

            col_score.markdown(
                f"<div style='text-align:center; font-size:1.4rem; font-weight:bold; color:{score_color}'>"
                f"{score_display}</div>",
                unsafe_allow_html=True,
            )
