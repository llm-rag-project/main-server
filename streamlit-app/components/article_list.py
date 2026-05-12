import streamlit as st

from api.ai_actions import request_article_summary
from api.articles import (
    get_article_detail,
    get_article_importance,
    get_articles,
)
from api.importance import set_user_score
from utils.ai_response_parser import extract_summary_text


def render_article_list():
    st.subheader("기사 목록")

    keyword_id = st.session_state.get("selected_keyword_id")

    col_size, col_page = st.columns([2, 1])
    with col_size:
        size = st.selectbox("페이지당 기사 수", [10, 20, 50], index=1, key="article_list_size")
    with col_page:
        page = st.number_input("페이지", min_value=1, value=1, step=1, key="article_list_page")

    try:
        articles, page_info = get_articles(keyword_id=keyword_id, page=page, size=size)
        st.session_state["articles"] = articles
        st.session_state["article_page_info"] = page_info
    except Exception as e:
        st.error(f"기사 목록 조회 실패: {e}")
        return

    if page_info and isinstance(page_info, dict):
        total = page_info.get("total", 0)
        st.caption(f"전체 {total}건 중 {len(articles)}건 표시")

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
                col_imp, _ = st.columns([1, 3])
                col_imp.metric("AI 중요도", f"{importance:.0f}점" if isinstance(importance, (int, float)) else importance)

            if summary:
                st.write(summary)

            col1, col2, col3 = st.columns(3)

            if col1.button("상세", key=f"detail_{article_id}"):
                try:
                    st.session_state[f"article_detail_{article_id}"] = get_article_detail(article_id)
                except Exception as e:
                    st.error(f"상세 조회 실패: {e}")

            if col2.button("AI 요약", key=f"summary_{article_id}"):
                try:
                    result = request_article_summary(article_id)
                    st.session_state[f"article_summary_{article_id}"] = extract_summary_text(result)
                except Exception as e:
                    st.error(f"요약 요청 실패: {e}")

            if col3.button("AI 중요도 조회", key=f"importance_{article_id}"):
                try:
                    st.session_state[f"article_importance_{article_id}"] = get_article_importance(article_id)
                except Exception as e:
                    st.error(f"중요도 조회 실패: {e}")

            if url:
                st.link_button("원문 링크", url)

            # ── 결과 표시 ─────────────────────────────────────────────
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
                st.markdown("##### AI 중요도 상세")
                st.json(importance_data)

            # ── 사용자 개인 중요도 설정 ───────────────────────────────
            with st.expander("✏️ 내 중요도 직접 설정"):
                score_key = f"my_score_input_{article_id}"
                reason_key = f"my_reason_input_{article_id}"

                user_score = st.slider(
                    "중요도 점수 (1~100)",
                    min_value=1,
                    max_value=100,
                    value=50,
                    key=score_key,
                )
                user_reason = st.text_input(
                    "사유 (선택)",
                    key=reason_key,
                    placeholder="예: 업계에 직접 영향을 미치는 정책 기사",
                )

                if st.button("저장", key=f"save_my_score_{article_id}"):
                    try:
                        set_user_score(
                            article_id=article_id,
                            score=float(user_score),
                            reason=user_reason.strip() or None,
                        )
                        st.success(f"중요도 {user_score}점으로 저장되었습니다.")
                    except Exception as e:
                        st.error(f"저장 실패: {e}")
