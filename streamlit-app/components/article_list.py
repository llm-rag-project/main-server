import threading
import time
import uuid

import streamlit as st

from api.ai_actions import request_article_summary
from api.articles import (
    get_article_detail,
    get_article_importance,
    get_articles,
)
from api.client import get_job_status
from api.importance import submit_scoring_feedback
from utils.ai_response_parser import extract_summary_text


RANK_MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]


def _build_rank_map() -> dict[int, str]:
    """중요도 상위 항목(session_state)에서 article_id → 순위 이모지 매핑 반환."""
    items = st.session_state.get("importance_items", [])
    return {
        item["article_id"]: RANK_MEDALS[i]
        for i, item in enumerate(items[:5])
        if item.get("article_id") is not None
    }


SORT_OPTIONS = {
    "최신순": "published_at_desc",
    "오래된순": "published_at_asc",
    "중요도 높은순": "importance_desc",
    "중요도 낮은순": "importance_asc",
}


def render_article_list():
    # ── 헤더 + 새로고침 버튼 ──────────────────────────────────
    col_title, col_refresh = st.columns([5, 1])
    col_title.subheader("기사 목록")
    if col_refresh.button("🔄 새로고침", key="article_list_refresh", width="stretch"):
        st.rerun()

    keyword_id = st.session_state.get("selected_keyword_id")

    # ── 검색 + 정렬 ──────────────────────────────────────────
    col_search, col_sort = st.columns([3, 1])
    with col_search:
        q = st.text_input(
            "🔍 기사 검색",
            placeholder="제목·내용 키워드 입력 후 Enter",
            key="article_search_q",
            label_visibility="collapsed",
        )
    with col_sort:
        sort_label = st.selectbox(
            "정렬",
            list(SORT_OPTIONS.keys()),
            index=0,
            key="article_sort",
            label_visibility="collapsed",
        )
    sort = SORT_OPTIONS[sort_label]

    # 검색어가 바뀌면 페이지를 1로 리셋
    prev_q = st.session_state.get("_prev_search_q", "")
    if q != prev_q:
        st.session_state["_prev_search_q"] = q
        st.session_state["article_list_page"] = 1

    col_size, col_page = st.columns([2, 1])
    with col_size:
        size = st.selectbox("페이지당 기사 수", [10, 20, 50], index=1, key="article_list_size")
    with col_page:
        page = st.number_input("페이지", min_value=1, value=1, step=1, key="article_list_page")

    try:
        articles, page_info = get_articles(
            keyword_id=keyword_id,
            page=page,
            size=size,
            q=q.strip() if q else None,
            sort=sort,
        )
        st.session_state["articles"] = articles
        st.session_state["article_page_info"] = page_info
    except Exception as e:
        st.error(f"기사 목록 조회 실패: {e}")
        return

    if page_info and isinstance(page_info, dict):
        total = page_info.get("total", 0)
        if q and q.strip():
            st.caption(f"🔍 '{q.strip()}' 검색 결과 {total}건 중 {len(articles)}건 표시")
        else:
            st.caption(f"전체 {total}건 중 {len(articles)}건 표시")

    if not articles:
        if q and q.strip():
            st.info(f"🔍 **'{q.strip()}'** 에 해당하는 기사가 없습니다.")
        else:
            st.info("표시할 기사가 없습니다.")
        return

    rank_map = _build_rank_map()  # { article_id: "🥇" | "🥈" | ... }

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

        # ── 요약 백그라운드 완료 여부 확인 ──────────────────────
        is_summarizing = st.session_state.get(f"is_summarizing_{article_id}", False)
        if is_summarizing:
            holder = st.session_state.get(f"_summary_holder_{article_id}", {})
            if holder.get("done"):
                st.session_state[f"is_summarizing_{article_id}"] = False
                st.session_state[f"summary_job_id_{article_id}"] = None
                if holder.get("error"):
                    st.session_state[f"summary_error_{article_id}"] = holder["error"]
                elif holder.get("result"):
                    st.session_state[f"article_summary_{article_id}"] = extract_summary_text(holder["result"])
                    st.session_state.pop(f"summary_error_{article_id}", None)
                st.rerun()

        medal = rank_map.get(article_id, "")
        sentiment = article.get("sentiment")
        is_promotion = article.get("is_promotion")

        with st.container(border=True):
            if medal:
                st.markdown(
                    f"<div style='font-size:1.25rem; font-weight:700; line-height:1.4'>"
                    f"<span style='font-size:1.6rem'>{medal}</span>&nbsp;{title}"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"**{title}**")

            # ── 배지 행 ───────────────────────────────────────────
            badges = []
            if sentiment and sentiment != "분석실패":
                color_map = {"긍정": "#27ae60", "부정": "#e74c3c", "중립": "#7f8c8d"}
                color = color_map.get(sentiment, "#7f8c8d")
                badges.append(
                    f"<span style='background:{color};color:#fff;"
                    f"padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600'>"
                    f"{sentiment}</span>"
                )
            if is_promotion is True:
                badges.append(
                    "<span style='background:#e67e22;color:#fff;"
                    "padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600'>"
                    "📢 홍보성</span>"
                )
            if badges:
                st.markdown("&nbsp;".join(badges), unsafe_allow_html=True)

            st.caption(f"{source} | {published_at}")

            if importance is not None:
                imp_label = f"{importance:.0f}점" if isinstance(importance, (int, float)) else str(importance)
                st.markdown(
                    f"<span style='font-size:0.8rem; color:#555;'>AI 중요도&nbsp;</span>"
                    f"<span style='font-size:0.95rem; font-weight:600; color:#1a1a1a;'>{imp_label}</span>",
                    unsafe_allow_html=True,
                )

            if summary:
                st.write(summary)

            col1, col2, col3 = st.columns(3)

            if col1.button("상세", key=f"detail_{article_id}"):
                try:
                    st.session_state[f"article_detail_{article_id}"] = get_article_detail(article_id)
                except Exception as e:
                    st.error(f"상세 조회 실패: {e}")

            # ── AI 요약 버튼 ──────────────────────────────────────
            if col2.button(
                "⏳ 요약 중..." if is_summarizing else "AI 요약",
                key=f"summary_{article_id}",
                disabled=is_summarizing,
            ):
                job_id = str(uuid.uuid4())
                holder = {"done": False, "result": None, "error": None}
                st.session_state[f"_summary_holder_{article_id}"] = holder
                st.session_state[f"summary_job_id_{article_id}"] = job_id
                st.session_state[f"is_summarizing_{article_id}"] = True
                st.session_state.pop(f"summary_error_{article_id}", None)

                def _summarize(aid=article_id, jid=job_id, h=holder):
                    try:
                        result = request_article_summary(aid, job_id=jid)
                        h["result"] = result
                    except Exception as e:
                        h["error"] = str(e)
                    finally:
                        h["done"] = True

                threading.Thread(target=_summarize, daemon=True).start()
                st.rerun()

            if col3.button("AI 중요도 조회", key=f"importance_{article_id}"):
                try:
                    st.session_state[f"article_importance_{article_id}"] = get_article_importance(article_id)
                except Exception as e:
                    st.error(f"중요도 조회 실패: {e}")

            if url:
                st.link_button("원문 링크", url)

            # ── 요약 진행 중 실시간 표시 ──────────────────────────
            if is_summarizing:
                job_id = st.session_state.get(f"summary_job_id_{article_id}")
                progress_ratio = 0.0
                message = "🤖 AI 요약 요청 중..."

                if job_id:
                    try:
                        job = get_job_status(job_id)
                        raw_progress = job.get("progress", 0)
                        progress_ratio = min(raw_progress / 100, 0.99)
                        message = job.get("message", message)
                    except Exception:
                        pass  # 폴링 실패 시 기본 메시지 유지

                st.progress(progress_ratio)
                st.caption(message)
                time.sleep(1)
                st.rerun()

            # ── 결과 표시 ─────────────────────────────────────────────
            detail_data = st.session_state.get(f"article_detail_{article_id}")
            if detail_data:
                st.markdown("##### 기사 상세")
                st.json(detail_data)

            summary_error = st.session_state.get(f"summary_error_{article_id}")
            if summary_error:
                st.error(f"요약 실패: {summary_error}")

            summary_data = st.session_state.get(f"article_summary_{article_id}")
            if summary_data:
                st.markdown("##### 요약 결과")
                st.write(summary_data)

            importance_data = st.session_state.get(f"article_importance_{article_id}")
            if importance_data:
                st.markdown("##### AI 중요도 상세")
                st.json(importance_data)

            # ── 사용자 피드백 ───────────────────────────────
            with st.expander("✏️ AI 점수 피드백 남기기"):
                original_score = int(importance) if isinstance(importance, (int, float)) else 50

                user_score = st.slider(
                    "내 점수 (1~100)",
                    min_value=1,
                    max_value=100,
                    value=original_score,
                    key=f"my_score_input_{article_id}",
                )
                user_reason = st.text_input(
                    "사유 (필수)",
                    key=f"my_reason_input_{article_id}",
                    placeholder="예: 업계에 직접 영향을 미치는 정책 기사",
                )

                if st.button("저장", key=f"save_my_score_{article_id}"):
                    if not user_reason.strip():
                        st.warning("사유를 입력해 주세요.")
                    else:
                        try:
                            submit_scoring_feedback(
                                article_id=article_id,
                                original_score=original_score,
                                user_score=user_score,
                                reason=user_reason.strip(),
                            )
                            st.success(f"피드백이 저장되었습니다. (내 점수: {user_score}점)")
                        except Exception as e:
                            st.error(f"저장 실패: {e}")
