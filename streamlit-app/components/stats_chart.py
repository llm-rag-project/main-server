from datetime import datetime

import streamlit as st
import pandas as pd
from api.stats import get_article_stats, get_search_volume
from api.reports import download_daily_report, send_report_email


@st.cache_data(ttl=300)  # 5분 캐시
def fetch_article_stats(days: int) -> dict:
    return get_article_stats(days=days)


@st.cache_data(ttl=60)  # 1분 캐시 (실시간성 중요)
def fetch_search_volume() -> list:
    return get_search_volume()


def render_stats_charts():
    st.subheader("📊 키워드 통계")

    col1, col2 = st.columns([3, 1])
    with col1:
        days = st.slider("조회 기간 (일)", min_value=1, max_value=90, value=7, step=1)
    with col2:
        if st.button("🔄 새로고침", width="stretch"):
            st.cache_data.clear()
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["키워드별 기사 수", "날짜별 기사 수", "실시간 검색량 비교"])

    # ── 탭 1: 키워드별 기사 수 (바 차트) ──────────────────────────
    with tab1:
        try:
            result = fetch_article_stats(days=days)
            by_keyword = result.get("by_keyword", [])

            if not by_keyword:
                st.info("기간 내 수집된 기사가 없습니다.")
            else:
                df = pd.DataFrame(by_keyword)
                st.bar_chart(
                    df.set_index("keyword_text")["article_count"],
                    width="stretch",
                )
                st.dataframe(
                    df.rename(columns={
                        "keyword_text": "키워드",
                        "article_count": "기사 수",
                    })[["키워드", "기사 수"]],
                    width="stretch",
                    hide_index=True,
                )
        except Exception as e:
            st.error(f"키워드별 기사 수 조회 실패: {e}")

    # ── 탭 2: 날짜별 기사 수 (라인 차트) ─────────────────────────
    with tab2:
        try:
            result = fetch_article_stats(days=days)  # 캐시 hit — 추가 API 호출 없음
            by_keyword_date = result.get("by_keyword_date", [])

            if not by_keyword_date:
                st.info("기간 내 수집된 기사가 없습니다.")
            else:
                df = pd.DataFrame(by_keyword_date)
                df["date"] = pd.to_datetime(df["date"])

                pivot = df.pivot_table(
                    index="date",
                    columns="keyword_text",
                    values="article_count",
                    fill_value=0,
                )
                st.line_chart(pivot, width="stretch")
        except Exception as e:
            st.error(f"날짜별 기사 수 조회 실패: {e}")

    # ── 탭 3: 실시간 검색량 비교 ──────────────────────────────────
    with tab3:
        st.caption("크롤링 서버에서 실시간으로 조회한 Google News 검색량입니다.")

        try:
            volume_data = fetch_search_volume()

            if not volume_data:
                st.info("활성 키워드가 없거나 검색량 데이터를 가져오지 못했습니다.")
            else:
                df = pd.DataFrame(volume_data)

                st.bar_chart(
                    df.set_index("keyword_text")["total_count"],
                    width="stretch",
                )
                st.dataframe(
                    df.rename(columns={
                        "keyword_text": "키워드",
                        "total_count": "총 검색량",
                        "min_count": "최소",
                        "max_count": "최대",
                    })[["키워드", "총 검색량", "최소", "최대"]],
                    width="stretch",
                    hide_index=True,
                )

                top = df.loc[df["total_count"].idxmax()]
                st.success(
                    f"🏆 현재 가장 많이 검색되는 키워드: "
                    f"**{top['keyword_text']}** ({top['total_count']}건)"
                )
        except Exception as e:
            st.error(f"실시간 검색량 조회 실패: {e}")

    st.markdown("---")

    # ── 데일리 리포트 Excel 다운로드 ──────────────────────────
    selected_keyword_id = st.session_state.get("selected_keyword_id")
    selected_keyword_name = st.session_state.get("selected_keyword_name")

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
            to_emails = [e.strip() for e in raw.replace(",", "\n").splitlines() if e.strip()]
            if not to_emails:
                st.error("유효한 이메일 주소를 입력해 주세요.")
            else:
                try:
                    with st.spinner("이메일 발송 중..."):
                        result = send_report_email(
                            to_emails=to_emails,
                            keyword_id=selected_keyword_id,
                            keyword_name=selected_keyword_name,
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