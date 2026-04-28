import streamlit as st

from api.ai_actions import request_articles_scoring
from api.articles import get_articles
from utils.ai_response_parser import (
    extract_scoring_result,
    extract_error_message,
)


def render_article_action_buttons():
    st.subheader("AI 작업")

    selected_keyword_id = st.session_state.get("selected_keyword_id")

    article_ids = []

    try:
        articles, _ = get_articles(
            keyword_id=selected_keyword_id,
            page=1,
            size=100,
        )
        article_ids = [
            article["id"]
            for article in articles
            if isinstance(article, dict) and article.get("id") is not None
        ]
    except Exception as e:
        st.error(f"중요도 계산 대상 기사 조회 실패: {e}")
        articles = []

    st.caption(f"중요도 계산 대상 기사 수: {len(article_ids)}건")

    scoring_disabled = (selected_keyword_id is None) or (len(article_ids) == 0)

    if st.button(
        "선택 키워드 기사 중요도 계산",
        use_container_width=True,
        disabled=scoring_disabled,
    ):
        try:
            st.session_state["article_scoring_result"] = None

            with st.spinner("중요도 계산 중..."):
                result = request_articles_scoring(
                    keyword_id=selected_keyword_id,
                    article_ids=article_ids,
                )

            if result.get("success") is False:
                st.error(
                    f"중요도 계산 실패: {extract_error_message(result, '중요도 계산 실패')}"
                )
                return

            scoring_items = extract_scoring_result(result)
            st.session_state["article_scoring_result"] = scoring_items

            if not scoring_items:
                # st.warning("반환된 중요도 항목이 없습니다.")
                return

            st.success("중요도 계산이 완료되었습니다.")

        except Exception as e:
            st.error(f"중요도 계산 실패: {e}")

    render_scoring_result()


def render_scoring_result():
    scoring_result = st.session_state.get("article_scoring_result")

    if not scoring_result:
        return

    st.markdown("### 중요도 결과")

    if isinstance(scoring_result, list):
        sorted_items = sorted(
            scoring_result,
            key=lambda x: x.get("score", 0),
            reverse=True,
        )

        for item in sorted_items:
            article_id = item.get("article_id")
            score = item.get("score")
            reason = item.get("reason", "사유 없음")

            st.write(f"- 기사 ID: {article_id}, 점수: {score}")
            st.caption(f"사유: {reason}")
    else:
        st.write(scoring_result)