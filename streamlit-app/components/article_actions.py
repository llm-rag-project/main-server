import streamlit as st

from api.ai_actions import request_articles_scoring
from api.articles import get_articles
from api.client import api_get
from api.crawl_runs import create_crawl_run
from utils.ai_response_parser import (
    extract_scoring_result,
    extract_error_message,
)


def render_article_action_buttons():
    # ── 수동 크롤링 ────────────────────────────────────────────
    st.subheader("🔍 크롤링")
    st.caption("활성화된 모든 키워드의 최신 기사를 즉시 수집합니다. (자동: 매일 오전 8시)")

    if st.button("수동 크롤링 실행", width="stretch"):
        try:
            with st.spinner("크롤링 중..."):
                result = create_crawl_run(force=True)
            st.success("✅ 크롤링이 시작되었습니다. 잠시 후 기사 목록을 새로고침하세요.")
        except Exception as e:
            st.error(f"크롤링 실패: {e}")

    st.markdown("---")

    st.subheader("AI 작업")

    selected_keyword_id = st.session_state.get("selected_keyword_id")

    # 미채점 기사 수 표시
    if selected_keyword_id:
        try:
            _, page_info = get_articles(keyword_id=selected_keyword_id, page=1, size=1)
            total_articles = page_info.get("total", 0) if page_info else 0

            imp_result = api_get("/importance", params={"keyword_id": selected_keyword_id, "page": 1, "size": 1})
            total_scored = imp_result.get("page_info", {}).get("total", 0) if isinstance(imp_result, dict) else 0

            unscored = max(total_articles - total_scored, 0)
            st.caption(f"전체 기사 {total_articles}건 중 미채점 **{unscored}건**")
        except Exception:
            pass

    scoring_disabled = selected_keyword_id is None

    if st.button(
        "선택 키워드 기사 중요도 계산",
        width="stretch",
        disabled=scoring_disabled,
    ):
        st.session_state["article_scoring_result"] = None
        st.session_state["scoring_msg"] = None

        try:
            with st.spinner("중요도 계산 중..."):
                result = request_articles_scoring(
                    keyword_id=selected_keyword_id,
                )

            scoring_items = extract_scoring_result(result)
            st.session_state["article_scoring_result"] = scoring_items

            remaining = result.get("remaining_count", 0) if isinstance(result, dict) else 0
            already = result.get("already_scored_count", 0) if isinstance(result, dict) else 0

            if scoring_items:
                msg = f"중요도 계산이 완료되었습니다. ({len(scoring_items)}건 계산)"
                if already:
                    msg += f" | 기계산 {already}건 건너뜀"
                if remaining:
                    msg += f" | 미계산 {remaining}건 남음 (버튼을 다시 눌러 계속 계산)"
                st.session_state["scoring_msg"] = ("success", msg)
            elif already and not scoring_items:
                st.session_state["scoring_msg"] = ("success", f"모든 기사({already}건)가 이미 계산되어 있습니다.")
            else:
                st.session_state["scoring_msg"] = ("error", "중요도 계산 결과가 없습니다. Dify 워크플로우 로그를 확인하세요.")

        except Exception as e:
            err_str = str(e)
            if any(k in err_str for k in ("503", "UNAVAILABLE", "high demand", "DIFY_TIMEOUT")):
                st.session_state["scoring_msg"] = (
                    "warning",
                    "AI 모델 서버가 일시적으로 혼잡합니다. 잠시 후 다시 시도해 주세요.",
                )
            else:
                st.session_state["scoring_msg"] = ("error", f"중요도 계산 실패: {e}")

    msg = st.session_state.get("scoring_msg")
    if msg:
        kind, text = msg
        if kind == "success":
            st.success(text)
        elif kind == "warning":
            st.warning(text)
        else:
            st.error(text)

    render_scoring_result()


def render_scoring_result():
    scoring_result = st.session_state.get("article_scoring_result")

    if not scoring_result:
        return

    st.markdown("### 중요도 결과")

    if not isinstance(scoring_result, list):
        st.write(scoring_result)
        return

    sorted_items = sorted(scoring_result, key=lambda x: x.get("score", 0), reverse=True)

    for item in sorted_items:
        article_id = item.get("article_id", "-")
        score = item.get("score")
        reason = item.get("reason", "사유 없음")

        score_display = f"{float(score):.2f}" if score is not None else "-"
        progress_value = 0.0
        if score is not None:
            try:
                v = float(score)
                progress_value = max(0.0, min(v if v <= 1 else v / 100.0, 1.0))
            except Exception:
                pass

        with st.container(border=True):
            col_id, col_score = st.columns([3, 1])
            col_id.markdown(f"**기사 ID:** {article_id}")
            col_score.metric("점수", score_display)
            if score is not None:
                st.progress(progress_value)
            st.caption(f"사유: {reason}")
