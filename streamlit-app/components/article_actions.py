import streamlit as st

from api.ai_actions import request_article_summary, request_articles_scoring
from utils.ai_response_parser import (
    extract_summary_text,
    extract_scoring_result,
    extract_error_message,
)

def render_article_action_buttons():
    st.subheader("AI 작업")

    selected_keyword_id = st.session_state.get("selected_keyword_id")
    selected_article_id = st.session_state.get("selected_article_id")
    selected_article_title = st.session_state.get("selected_article_title")
    article_list = st.session_state.get("articles", [])

    article_ids = [
        article["id"]
        for article in article_list
        if isinstance(article, dict) and article.get("id") is not None
    ]

    col1, col2 = st.columns(2)

    with col1:
        if selected_article_title:
            st.caption(f"선택 기사: {selected_article_title}")
        else:
            st.caption("선택된 기사가 없습니다.")

        if st.button(
            "선택 기사 요약",
            use_container_width=True,
            disabled=(selected_article_id is None),
        ):
            try:
                st.session_state["article_summary_result"] = None

                with st.spinner("기사 요약 생성 중..."):
                    result = request_article_summary(selected_article_id)

                if result.get("success") is False:
                    st.error(
                        f"요약 요청 실패: {extract_error_message(result, '요약 요청 실패')}"
                    )
                    return

                st.session_state["article_summary_result"] = extract_summary_text(result)
                st.success("기사 요약이 완료되었습니다.")
            except Exception as e:
                st.error(f"요약 요청 실패: {e}")

    with col2:
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
                    st.warning("반환된 중요도 항목이 없습니다.")
                    return

                st.success("중요도 계산이 완료되었습니다.")

            except Exception as e:
                st.error(f"중요도 계산 실패: {e}")

    summary_result = st.session_state.get("article_summary_result")
    if summary_result:
        st.markdown("### 요약 결과")
        st.write(summary_result)

    scoring_result = st.session_state.get("article_scoring_result")
    if scoring_result:
        st.markdown("### 중요도 결과")
        for item in sorted(
            scoring_result,
            key=lambda x: x.get("score", 0),
            reverse=True
        ):
            st.write(
                f"- 기사 ID: {item.get('article_id')}, 점수: {item.get('score')}"
            )
            st.caption(f"사유: {item.get('reason', '사유 없음')}")

            

def render_summary_section(selected_article_id: int | None, selected_article_title: str | None):
    if selected_article_title:
        st.caption(f"선택 기사: {selected_article_title}")
    else:
        st.caption("선택된 기사가 없습니다.")

    summary_disabled = selected_article_id is None

    if st.button("선택 기사 요약", use_container_width=True, disabled=summary_disabled):
        try:
            st.session_state["article_summary_result"] = None

            with st.spinner("기사 요약 생성 중..."):
                result = request_article_summary(selected_article_id)

            if result.get("success") is False:
                error_message = extract_error_message(result, "요약 요청에 실패했습니다.")
                st.error(f"요약 요청 실패: {error_message}")
                return

            summary_text = extract_summary_text(result)
            st.session_state["article_summary_result"] = summary_text
            st.success("기사 요약이 완료되었습니다.")

        except Exception as e:
            st.error(f"요약 요청 실패: {e}")


def render_scoring_section(article_ids: list[int]):
    st.caption(f"중요도 계산 대상 기사 수: {len(article_ids)}건")

    scoring_disabled = len(article_ids) == 0

    if st.button("전체 기사 중요도 계산", use_container_width=True, disabled=scoring_disabled):
        try:
            st.session_state["article_scoring_result"] = None

            with st.spinner("전체 기사 중요도 계산 중..."):
                result = request_articles_scoring(article_ids)

            if result.get("success") is False:
                error_message = extract_error_message(result, "중요도 계산에 실패했습니다.")
                st.error(f"중요도 계산 실패: {error_message}")
                return

            scoring_items = extract_scoring_result(result)
            st.session_state["article_scoring_result"] = scoring_items

            if not scoring_items:
                st.warning("반환된 중요도 항목이 없습니다.")
                return

            st.success("전체 기사 중요도 계산이 완료되었습니다.")

        except Exception as e:
            st.error(f"중요도 계산 실패: {e}")


def render_summary_result():
    summary_result = st.session_state.get("article_summary_result")

    if summary_result:
        st.markdown("### 요약 결과")
        st.write(summary_result)


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