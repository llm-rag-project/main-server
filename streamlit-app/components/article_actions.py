from datetime import datetime

import streamlit as st

from api.ai_actions import request_articles_scoring
from api.articles import get_articles
from api.reports import download_daily_report, send_report_email
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
        width="stretch",
        disabled=scoring_disabled,
    ):
        st.session_state["article_scoring_result"] = None
        st.session_state["scoring_msg"] = None

        try:
            with st.spinner("중요도 계산 중..."):
                result = request_articles_scoring(
                    keyword_id=selected_keyword_id,
                    article_ids=article_ids,
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

    st.markdown("---")

    # ── 데일리 리포트 Excel 다운로드 ──────────────────────────
    st.subheader("📥 데일리 리포트")
    st.caption("현재 선택된 키워드의 기사·중요도·요약을 Excel로 다운로드합니다.")

    try:
        excel_bytes = download_daily_report(keyword_id=selected_keyword_id)
        today_str = datetime.now().strftime("%Y-%m-%d")
        st.download_button(
            label="Excel 다운로드",
            data=excel_bytes,
            file_name=f"daily_report_{today_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    except Exception as e:
        st.error(f"리포트 생성 실패: {e}")

    st.markdown("---")

    # ── 이메일 발송 ────────────────────────────────────────────
    st.subheader("📧 이메일 발송")
    st.caption("데일리 리포트를 Excel 첨부 파일로 이메일 전송합니다.")

    email_input = st.text_area(
        "수신자 이메일 (여러 명이면 줄바꿈 또는 쉼표로 구분)",
        placeholder="example@gmail.com\nanother@example.com",
        height=100,
        key="email_recipients_input",
    )

    if st.button("이메일 발송", width="stretch"):
        raw = email_input.strip()
        if not raw:
            st.error("수신자 이메일을 입력해 주세요.")
        else:
            # 줄바꿈 또는 쉼표로 분리, 공백 제거, 빈 항목 제거
            to_emails = [e.strip() for e in raw.replace(",", "\n").splitlines() if e.strip()]
            if not to_emails:
                st.error("유효한 이메일 주소를 입력해 주세요.")
            else:
                selected_keyword = st.session_state.get("selected_keyword_name")
                try:
                    with st.spinner("이메일 발송 중..."):
                        result = send_report_email(
                            to_emails=to_emails,
                            keyword_id=selected_keyword_id,
                            keyword_name=selected_keyword,
                        )
                    sent_to = result.get("data", {}).get("sent_to", to_emails)
                    article_count = result.get("data", {}).get("article_count", 0)
                    st.success(
                        f"✅ {len(sent_to)}명에게 데일리 리포트({article_count}건)를 발송했습니다."
                    )
                except Exception as e:
                    err_str = str(e)
                    if "SMTP" in err_str or "smtp" in err_str:
                        st.error("SMTP 설정이 올바르지 않습니다. 서버의 .env 파일을 확인해 주세요.")
                    else:
                        st.error(f"이메일 발송 실패: {e}")

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