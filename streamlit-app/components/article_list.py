import streamlit as st

from api.ai_actions import request_article_summary
from api.articles import (
    get_article_detail,
    get_article_importance,
    get_articles,
)


def render_article_list():
    st.subheader("기사 목록")

    keyword_id = st.session_state.get("selected_keyword_id")

    try:
        articles, page_info = get_articles(keyword_id=keyword_id, page=1, size=10)
        st.session_state["articles"] = articles
        st.session_state["article_page_info"] = page_info
    except Exception as e:
        st.error(f"기사 목록 조회 실패: {e}")
        return

    if not articles:
        st.info("표시할 기사가 없습니다.")
        return

    for article in articles:
        article_id = article.get("id")
        title = article.get("title", "제목 없음")
        source = article.get("source", "출처 없음")
        published_at = article.get("published_at", "")
        summary = article.get("summary", "")
        url = article.get("url", "")
        importance = article.get("importance")

        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(f"{source} | {published_at}")

            if importance is not None:
                st.write(f"중요도: {importance}")

            summary_data = st.session_state.get(f"article_summary_{article_id}")
            if summary_data:
                st.markdown("##### 요약 결과")

                if isinstance(summary_data, dict):
                    summary_text = summary_data.get("summary_text") or summary_data.get("text")
                    if summary_text:
                        st.write(summary_text)
                    else:
                        st.json(summary_data)
                else:
                    st.write(summary_data)

            col1, col2= st.columns(3)

            if col1.button("상세", key=f"detail_{article_id}"):
                try:
                    st.session_state[f"article_detail_{article_id}"] = get_article_detail(article_id)
                except Exception as e:
                    st.error(f"상세 조회 실패: {e}")

            if col2.button("요약", key=f"summary_{article_id}"):
                try:
                    st.session_state[f"article_summary_{article_id}"] = request_article_summary(article_id)
                except Exception as e:
                    st.error(f"요약 요청 실패: {e}")

           
            if url:
                st.link_button("원문 링크", url)

            detail_data = st.session_state.get(f"article_detail_{article_id}")
            if detail_data:
                st.markdown("##### 기사 상세")
                st.json(detail_data)

            summary_data = st.session_state.get(f"article_summary_{article_id}")
            if summary_data:
                st.markdown("##### 요약 결과")
                st.json(summary_data)

            importance_data = st.session_state.get(f"article_importance_{article_id}")
            if importance_data:
                st.markdown("##### 중요도 상세")
                st.json(importance_data)