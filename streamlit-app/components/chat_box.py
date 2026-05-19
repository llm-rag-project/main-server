import streamlit as st
from api.chat import send_chat_message


def render_chat_box():
    st.subheader("AI 채팅")

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    if "chat_conversation_id" not in st.session_state:
        st.session_state["chat_conversation_id"] = ""

    chat_id = st.session_state.get("selected_chat_id")

    # 세션 미선택 시 안내
    if not chat_id:
        st.warning(
            "💬 **채팅을 시작하려면 먼저 왼쪽 사이드바에서 채팅 세션을 선택하거나 새로 만들어 주세요.**",
        )
        st.chat_input("채팅 세션을 먼저 선택해 주세요", disabled=True)
        return

    if not st.session_state["chat_messages"]:
        st.info("💬 질문을 입력하면 AI 응답이 표시됩니다.\n\n📌 채팅 세션별로 대화 내역이 구분되니, 왼쪽 사이드바에서 원하는 세션을 선택해 주세요.")

    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    prompt = st.chat_input("예: 하이닉스 관련 기사 흐름 요약해줘")

    if prompt:
        selected_article_id = st.session_state.get("selected_article_id")
        conversation_id = st.session_state.get("chat_conversation_id", "")

        st.session_state["chat_messages"].append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("assistant"):
            with st.spinner("응답 생성 중..."):
                try:
                    result = send_chat_message(
                        chat_id=chat_id,
                        message=prompt,
                        article_id=selected_article_id,
                        conversation_id=conversation_id,
                    )

                    answer, new_conversation_id = extract_chat_result(result)

                    if new_conversation_id:
                        st.session_state["chat_conversation_id"] = new_conversation_id

                except Exception as e:
                    err_str = str(e)
                    if any(k in err_str for k in ("503", "UNAVAILABLE", "high demand", "DIFY_ERROR", "DIFY_TIMEOUT")):
                        answer = "AI 모델 서버가 일시적으로 혼잡합니다. 잠시 후 다시 시도해 주세요."
                    else:
                        answer = f"채팅 요청 실패: {e}"

                st.write(answer)

        st.session_state["chat_messages"].append({
            "role": "assistant",
            "content": answer
        })


def extract_chat_result(result):
    if not isinstance(result, dict):
        return "채팅 결과를 해석하지 못했습니다.", ""

    answer = result.get("answer", "")
    conversation_id = result.get("conversation_id", "")

    if not isinstance(answer, str) or not answer.strip():
        answer = "응답 내용이 비어 있습니다."

    if not isinstance(conversation_id, str):
        conversation_id = ""

    return answer, conversation_id