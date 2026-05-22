import threading
import time
import uuid
from datetime import datetime

import pandas as pd
import streamlit as st

from api.client import get_job_status
from api.crawl_runs import get_pending_analysis_count, run_analysis
from api.reports import download_daily_report, send_report_email
from api.stats import get_analysis_stats, get_article_stats, get_search_volume


@st.cache_data(ttl=60)
def fetch_pending_count() -> int:
    try:
        return get_pending_analysis_count()
    except Exception:
        return 0


@st.cache_data(ttl=300)  # 5분 캐시
def fetch_article_stats(days: int) -> dict:
    return get_article_stats(days=days)


@st.cache_data(ttl=300)
def fetch_analysis_stats(days: int) -> dict:
    return get_analysis_stats(days=days)


@st.cache_data(ttl=60)  # 1분 캐시 (실시간성 중요)
def fetch_search_volume() -> list:
    return get_search_volume()


def render_stats_charts():
    st.subheader("📊 키워드 통계")

    # ── AI 분석 백그라운드 완료 확인 ────────────────────────────
    is_analyzing = st.session_state.get("is_analyzing", False)
    if is_analyzing:
        holder = st.session_state.get("_analysis_holder", {})
        if holder.get("done"):
            st.session_state["is_analyzing"] = False
            is_analyzing = False
            if holder.get("error"):
                st.session_state["analysis_msg"] = ("error", f"분석 실패: {holder['error']}")
            else:
                r = holder.get("result") or {}
                analyzed = r.get("analyzed_count", 0)
                total = r.get("total", 0)
                if total == 0:
                    st.session_state["analysis_msg"] = ("success", "✅ 모든 기사가 이미 분석되어 있습니다.")
                else:
                    st.session_state["analysis_msg"] = ("success", f"✅ {analyzed}건 분석 완료!")
            st.cache_data.clear()
            st.rerun()

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        days = st.slider("조회 기간 (일)", min_value=1, max_value=90, value=7, step=1)
    with col2:
        if st.button("🔄 새로고침", width="stretch", disabled=is_analyzing):
            st.cache_data.clear()
            st.rerun()
    with col3:
        pending = fetch_pending_count()
        btn_label = (
            "⏳ 분석 중..." if is_analyzing
            else f"🤖 AI 분석 ({pending}건)" if pending > 0
            else "🤖 AI 분석 (없음)"
        )
        if st.button(btn_label, width="stretch", disabled=is_analyzing or pending == 0,
                     help="미분석 기사에 대해 감성·홍보성 분석을 즉시 실행합니다"):
            job_id = str(uuid.uuid4())
            holder = {"done": False, "result": None, "error": None}
            st.session_state["_analysis_holder"] = holder
            st.session_state["analysis_job_id"] = job_id
            st.session_state["is_analyzing"] = True
            st.session_state["analysis_msg"] = None

            def _analyze(jid=job_id, h=holder):
                try:
                    result = run_analysis(job_id=jid)
                    h["result"] = result
                except Exception as e:
                    h["error"] = str(e)
                finally:
                    h["done"] = True

            threading.Thread(target=_analyze, daemon=True).start()
            st.rerun()

    # ── 분석 진행 중 실시간 표시 ─────────────────────────────────
    if is_analyzing:
        job_id = st.session_state.get("analysis_job_id")
        progress_ratio = 0.0
        message = "🤖 AI 분석 요청 중..."
        if job_id:
            try:
                job = get_job_status(job_id)
                raw_progress = job.get("progress", 0)
                progress_ratio = min(raw_progress / 100, 0.99)
                message = job.get("message", message)
            except Exception:
                pass
        st.progress(progress_ratio)
        st.caption(message)

    # ── 분석 결과 메시지 ─────────────────────────────────────────
    analysis_msg = st.session_state.get("analysis_msg")
    if analysis_msg:
        kind, text = analysis_msg
        if kind == "success":
            st.success(text)
        else:
            st.error(text)

    if is_analyzing:
        time.sleep(1)
        st.rerun()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "키워드별 기사 수",
        "날짜별 기사 수",
        "감성 분포",
        "광고성 기사 비율",
        "날짜별 감성 추이",
        "실시간 검색량 비교",
    ])

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

                all_keywords = sorted(df["keyword_text"].unique().tolist())
                selected_keywords = st.multiselect(
                    "표시할 키워드 선택",
                    options=all_keywords,
                    default=all_keywords,
                    key="date_chart_keywords",
                )

                if not selected_keywords:
                    st.info("표시할 키워드를 하나 이상 선택해 주세요.")
                else:
                    filtered_df = df[df["keyword_text"].isin(selected_keywords)]
                    pivot = filtered_df.pivot_table(
                        index="date",
                        columns="keyword_text",
                        values="article_count",
                        fill_value=0,
                    )
                    st.line_chart(pivot, width="stretch")
        except Exception as e:
            st.error(f"날짜별 기사 수 조회 실패: {e}")

    # ── 탭 3: 감성 분포 (키워드별 개별 차트) ─────────────────────
    with tab3:
        try:
            result = fetch_analysis_stats(days=days)
            sentiment_data = result.get("sentiment_by_keyword", [])

            if not sentiment_data:
                st.info("분석된 기사가 없습니다. AI 분석이 완료된 후 확인해 주세요.")
            else:
                df = pd.DataFrame(sentiment_data)
                keywords = sorted(df["keyword_text"].unique())
                SENTIMENT_ORDER = ["긍정", "중립", "부정", "분석실패", "미분석"]
                SENTIMENT_COLORS = {"긍정": "#27ae60", "중립": "#7f8c8d", "부정": "#e74c3c",
                                    "분석실패": "#bdc3c7", "미분석": "#dfe6e9"}

                cols = st.columns(min(len(keywords), 2))
                for i, kw in enumerate(keywords):
                    with cols[i % len(cols)]:
                        kw_df = df[df["keyword_text"] == kw].copy()
                        kw_df = kw_df.set_index("sentiment")["count"]
                        ordered = [c for c in SENTIMENT_ORDER if c in kw_df.index]
                        kw_df = kw_df.reindex(ordered).fillna(0)
                        total = int(kw_df.sum())

                        st.markdown(f"**{kw}** <span style='color:#888;font-size:0.85rem'>({total}건)</span>",
                                    unsafe_allow_html=True)
                        colors = [SENTIMENT_COLORS[c] for c in ordered]
                        st.bar_chart(kw_df, height=220, color=colors)

                        # 비율 표시
                        pct_rows = [
                            {"감성": c, "건수": int(kw_df[c]), "비율": f"{kw_df[c]/total*100:.1f}%"}
                            for c in ordered if total > 0
                        ]
                        if pct_rows:
                            st.dataframe(pd.DataFrame(pct_rows), hide_index=True, use_container_width=True)
        except Exception as e:
            st.error(f"감성 분포 조회 실패: {e}")

    # ── 탭 4: 광고성 기사 비율 (키워드별 개별 차트) ──────────────
    with tab4:
        try:
            result = fetch_analysis_stats(days=days)
            promotion_data = result.get("promotion_by_keyword", [])

            if not promotion_data:
                st.info("분석된 기사가 없습니다. AI 분석이 완료된 후 확인해 주세요.")
            else:
                df = pd.DataFrame(promotion_data)
                keywords = sorted(df["keyword_text"].unique())
                PROMO_ORDER = ["✅ 일반", "📢 광고성", "❓ 미분석"]
                PROMO_COLORS = {"✅ 일반": "#27ae60", "📢 광고성": "#e67e22", "❓ 미분석": "#bdc3c7"}

                cols = st.columns(min(len(keywords), 2))
                for i, kw in enumerate(keywords):
                    with cols[i % len(cols)]:
                        kw_df = df[df["keyword_text"] == kw].copy()
                        kw_df = kw_df.set_index("promotion")["count"]
                        ordered = [c for c in PROMO_ORDER if c in kw_df.index]
                        kw_df = kw_df.reindex(ordered).fillna(0)
                        total = int(kw_df.sum())

                        promo_cnt = int(kw_df.get("📢 광고성", 0))
                        promo_pct = f"{promo_cnt/total*100:.1f}%" if total > 0 else "0%"
                        st.markdown(
                            f"**{kw}** <span style='color:#888;font-size:0.85rem'>({total}건 · 광고성 {promo_pct})</span>",
                            unsafe_allow_html=True,
                        )
                        colors = [PROMO_COLORS[c] for c in ordered]
                        st.bar_chart(kw_df, height=220, color=colors)

                        pct_rows = [
                            {"구분": c, "건수": int(kw_df[c]), "비율": f"{kw_df[c]/total*100:.1f}%"}
                            for c in ordered if total > 0
                        ]
                        if pct_rows:
                            st.dataframe(pd.DataFrame(pct_rows), hide_index=True, use_container_width=True)

                # 광고성 TOP 키워드 경고
                promo_totals = (
                    df[df["promotion"] == "📢 광고성"]
                    .groupby("keyword_text")["count"].sum()
                )
                if not promo_totals.empty and promo_totals.max() > 0:
                    top_kw = promo_totals.idxmax()
                    st.warning(f"📢 광고성 기사가 가장 많은 키워드: **{top_kw}** ({int(promo_totals[top_kw])}건)")
        except Exception as e:
            st.error(f"광고성 비율 조회 실패: {e}")

    # ── 탭 5: 날짜별 감성 추이 (키워드별 개별 차트) ──────────────
    with tab5:
        try:
            result = fetch_analysis_stats(days=days)
            sentiment_date_data = result.get("sentiment_by_date", [])

            if not sentiment_date_data:
                st.info("분석된 기사가 없습니다. AI 분석이 완료된 후 확인해 주세요.")
            else:
                df = pd.DataFrame(sentiment_date_data)
                df["date"] = pd.to_datetime(df["date"])
                keywords = sorted(df["keyword_text"].unique()) if "keyword_text" in df.columns else ["전체"]

                # 날짜별 감성 추이는 날짜 축이 넓어야 해서 전체 너비로 키워드별 표시
                SENTIMENT_COLORS_LIST = ["#27ae60", "#7f8c8d", "#e74c3c"]
                for kw in keywords:
                    st.markdown(f"**{kw}**")
                    kw_df = df[df["keyword_text"] == kw] if "keyword_text" in df.columns else df
                    pivot = kw_df.pivot_table(
                        index="date",
                        columns="sentiment",
                        values="count",
                        aggfunc="sum",
                        fill_value=0,
                    )
                    ordered_cols = [c for c in ["긍정", "중립", "부정"] if c in pivot.columns]
                    if ordered_cols:
                        pivot = pivot[ordered_cols]
                        st.line_chart(
                            pivot,
                            width="stretch",
                            height=220,
                            color=SENTIMENT_COLORS_LIST[:len(ordered_cols)],
                        )
                    else:
                        st.info(f"'{kw}' 감성 분석 데이터가 없습니다.")
        except Exception as e:
            st.error(f"날짜별 감성 추이 조회 실패: {e}")

    # ── 탭 6: 실시간 검색량 비교 ──────────────────────────────────
    with tab6:
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

    is_sending = st.session_state.get("is_sending_email", False)

    # 백그라운드 작업 완료 여부 확인
    if is_sending:
        holder = st.session_state.get("_email_holder", {})
        if holder.get("done"):
            st.session_state["is_sending_email"] = False
            is_sending = False
            error = holder.get("error")
            result = holder.get("result")
            if error:
                err_str = error
                if "SMTP" in err_str or "smtp" in err_str:
                    st.session_state["email_msg"] = ("error", "SMTP 설정이 올바르지 않습니다. 서버의 .env 파일을 확인해 주세요.")
                else:
                    st.session_state["email_msg"] = ("error", f"이메일 발송 실패: {err_str}")
            elif result:
                sent_to = result.get("sent_to", [])
                article_count = result.get("article_count", 0)
                st.session_state["email_msg"] = (
                    "success",
                    f"✅ {len(sent_to)}명에게 데일리 리포트({article_count}건)를 발송했습니다.",
                )
            st.rerun()

    email_input = st.text_area(
        "수신자 이메일 (여러 명이면 줄바꿈 또는 쉼표로 구분)",
        placeholder="example@gmail.com\nanother@example.com",
        height=100,
        key="email_recipients_input",
        disabled=is_sending,
    )

    if st.button("이메일 발송", width="stretch", disabled=is_sending):
        raw = email_input.strip()
        if not raw:
            st.session_state["email_msg"] = ("error", "수신자 이메일을 입력해 주세요.")
            st.rerun()
        else:
            to_emails = [e.strip() for e in raw.replace(",", "\n").splitlines() if e.strip()]
            if not to_emails:
                st.session_state["email_msg"] = ("error", "유효한 이메일 주소를 입력해 주세요.")
                st.rerun()
            else:
                holder = {"done": False, "result": None, "error": None}
                st.session_state["_email_holder"] = holder
                st.session_state["is_sending_email"] = True
                st.session_state["email_start_time"] = time.time()
                st.session_state["email_msg"] = None

                def _send():
                    try:
                        r = send_report_email(
                            to_emails=to_emails,
                            keyword_id=selected_keyword_id,
                            keyword_name=selected_keyword_name,
                        )
                        holder["result"] = r
                    except Exception as e:
                        holder["error"] = str(e)
                    finally:
                        holder["done"] = True

                threading.Thread(target=_send, daemon=True).start()
                st.rerun()

    # 발송 중 진행 상황 표시
    if is_sending:
        elapsed = int(time.time() - st.session_state.get("email_start_time", time.time()))
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins}분 {secs}초" if mins > 0 else f"{secs}초"
        st.info(f"📨 이메일 발송 중... **{time_str}** 경과")
        if elapsed < 10:
            st.caption("📋 리포트 데이터 조회 중...")
        elif elapsed < 25:
            st.caption("📊 Excel 파일 생성 중...")
        else:
            st.caption("📤 이메일 전송 중...")
        time.sleep(1)
        st.rerun()

    # 결과 메시지
    email_msg = st.session_state.get("email_msg")
    if email_msg:
        kind, text = email_msg
        if kind == "success":
            st.success(text)
        else:
            st.error(text)