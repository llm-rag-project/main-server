import json
import streamlit as st

from api.articles import get_articles
from api.client import api_get, api_post

def render_summary_result(summary_result):
    """
    summary_result가 dict이든 JSON 문자열이든 보기 좋게 렌더링
    기대 형태 예:
    {
        "article_id": 38,
        "title": "...",
        "summary": "..."
    }
    """
    if not summary_result:
        st.info("요약 결과가 없습니다.")
        return

    parsed = summary_result

    # 문자열이면 JSON 파싱 시도
    if isinstance(summary_result, str):
        try:
            parsed = json.loads(summary_result)
        except Exception:
            parsed = {"summary": summary_result}

    title = ""
    summary_text = ""

    if isinstance(parsed, dict):
        title = parsed.get("title", "")
        summary_text = (
            parsed.get("summary")
            or parsed.get("summary_text")
            or parsed.get("result")
            or parsed.get("text")
            or ""
        )

    with st.container(border=True):
        st.markdown("### 요약 결과")

        if title:
            st.caption(title)

        if summary_text:
            st.write(summary_text)
        else:
            st.warning("표시할 요약 텍스트가 없습니다.")


def render_importance_result(importance_result):
    """
    importance_result 예:
    {
        "success": True,
        "data": {
            "workflow_run_id": "...",
            "task_id": "...",
            "items": [
                {
                    "article_id": 38,
                    "score": 0.82,
                    "reason": "...",
                    "status": "COMPLETED"
                }
            ]
        }
    }

    또는 data만 unwrap된 상태:
    {
        "workflow_run_id": "...",
        "task_id": "...",
        "items": [...]
    }
    """
    if not importance_result:
        st.info("중요도 실행 결과가 없습니다.")
        return

    parsed = importance_result

    if isinstance(importance_result, str):
        try:
            parsed = json.loads(importance_result)
        except Exception:
            st.warning("중요도 응답을 해석할 수 없습니다.")
            st.write(importance_result)
            return

    if not isinstance(parsed, dict):
        st.warning("중요도 응답 형식이 올바르지 않습니다.")
        st.write(parsed)
        return

    data = parsed.get("data") if isinstance(parsed.get("data"), dict) else parsed
    items = data.get("items", []) if isinstance(data, dict) else []

    with st.container(border=True):
        st.markdown("### 중요도 실행 결과")

        workflow_run_id = data.get("workflow_run_id") if isinstance(data, dict) else None
        task_id = data.get("task_id") if isinstance(data, dict) else None

        meta_cols = st.columns(2)
        meta_cols[0].caption(f"workflow_run_id: {workflow_run_id or '-'}")
        meta_cols[1].caption(f"task_id: {task_id or '-'}")

        if not items:
            st.warning("반환된 중요도 항목이 없습니다.")
            return

        for item in items:
            article_id = item.get("article_id", "-")
            score = item.get("score")
            status = item.get("status", "COMPLETED")
            reason = item.get("reason", "")

            score_text = "-"
            progress_value = 0.0

            if score is not None:
                try:
                    progress_value = float(score)
                    progress_value = max(0.0, min(progress_value, 1.0))
                    score_text = f"{progress_value:.2f}"
                except Exception:
                    score_text = str(score)

            st.markdown(f"**기사 ID:** {article_id}")

            row_cols = st.columns([1, 1, 3])
            row_cols[0].metric("점수", score_text)
            row_cols[1].metric("상태", status)

            if score is not None:
                st.progress(progress_value)

            if reason:
                st.markdown("**사유**")
                st.write(reason)

            st.divider()


def render_summary_cards():
    selected_keyword = st.session_state.get("selected_keyword_name")
    keyword_id = st.session_state.get("selected_keyword_id")

    article_count = 0
    importance_count = 0

    try:
        articles, _ = get_articles(keyword_id=keyword_id, page=1, size=100)
        article_count = len(articles)
    except Exception:
        articles = []

    try:
        params = {"page": 1, "size": 100}
        if keyword_id:
            params["keyword_id"] = keyword_id

        result = api_get("/importance", params=params)
        importance_items = result.get("items", []) if isinstance(result, dict) else []
        st.session_state["importance_items"] = importance_items
        importance_count = len(importance_items)
    except Exception:
        st.session_state["importance_items"] = []

    col1, col2, col3 = st.columns(3)
    col1.metric("선택 키워드", selected_keyword if selected_keyword else "-")
    col2.metric("기사 수", article_count)
    col3.metric("중요도 결과 수", importance_count)

    st.markdown("### 중요도 상위 항목")
    items = st.session_state.get("importance_items", [])
    if items:
        for item in items[:5]:
            st.write(
                f"- {item.get('title', '제목 없음')} | "
                f"score={item.get('score', '-')} | "
                f"status={item.get('status', '-')}"
            )
    else:
        st.caption("중요도 데이터가 없습니다.")