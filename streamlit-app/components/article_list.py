import streamlit as st

from api.ai_actions import request_article_summary
from api.articles import (
    get_article_detail,
    get_article_importance,
    get_articles,
)


def extract_summary_text(result):
    if not isinstance(result, dict):
        return "요약 결과를 해석하지 못했습니다."

    # 1. 메인서버 공통 응답 형식
    data = result.get("data")
    if isinstance(data, dict):
        summary = data.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary

        # 혹시 Dify 결과를 data 안에 summary_text로 넣은 경우
        summary_text = data.get("summary_text")
        if isinstance(summary_text, str) and summary_text.strip():
            return summary_text

    # 2. 예전 방식: 최상위 summary
    summary = result.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary

    # 3. 예전 방식: 최상위 summary_text
    summary_text = result.get("summary_text")
    if isinstance(summary_text, str) and summary_text.strip():
        return summary_text

    return "요약 결과가 비어 있습니다."


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
        url = (
            article.get("original_url")
            or article.get("url")
            or article.get("link")
            or ""
        )
        importance = article.get("importance")

        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(f"{source} | {published_at}")

            if importance is not None:
                st.write(f"중요도: {importance}")

            if summary:
                st.write(summary)

            col1, col2, col3 = st.columns(3)

            if col1.button("상세", key=f"detail_{article_id}"):
                try:
                    st.session_state[f"article_detail_{article_id}"] = get_article_detail(article_id)
                except Exception as e:
                    st.error(f"상세 조회 실패: {e}")

            if col2.button("요약", key=f"summary_{article_id}"):
                try:
                    result = request_article_summary(article_id)
                    st.session_state[f"article_summary_{article_id}"] = extract_summary_text(result)
                except Exception as e:
                    st.error(f"요약 요청 실패: {e}")

            if col3.button("중요도", key=f"importance_{article_id}"):
                try:
                    st.session_state[f"article_importance_{article_id}"] = get_article_importance(article_id)
                except Exception as e:
                    st.error(f"중요도 조회 실패: {e}")

            if url:
                st.link_button("원문 링크", url)

            detail_data = st.session_state.get(f"article_detail_{article_id}")
            if detail_data:
                st.markdown("##### 기사 상세")
                st.json(detail_data)

            summary_data = st.session_state.get(f"article_summary_{article_id}")
            if summary_data:
                st.markdown("##### 요약 결과")
                st.write(summary_data)

            importance_data = st.session_state.get(f"article_importance_{article_id}")
            if importance_data:
                st.markdown("##### 중요도 상세")
                st.json(importance_data)