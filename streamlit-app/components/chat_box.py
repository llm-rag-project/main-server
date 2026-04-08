import streamlit as st
from api.chat import send_chat_message


def render_chat_box():
    st.subheader("AI 채팅")

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    if "chat_conversation_id" not in st.session_state:
        st.session_state["chat_conversation_id"] = ""

    if not st.session_state["chat_messages"]:
        st.info("질문을 입력하면 AI 응답이 표시됩니다.")

    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    prompt = st.chat_input("예: 하이닉스 관련 기사 흐름 요약해줘")

    if prompt:
        selected_article_id = st.session_state.get("selected_article_id")
        conversation_id = st.session_state.get("chat_conversation_id", "")
        chat_id = st.session_state.get("selected_chat_id")

        st.session_state["chat_messages"].append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("assistant"):
            with st.spinner("응답 생성 중..."):
                try:
                    if not chat_id:
                        raise ValueError("선택된 채팅방이 없습니다. 먼저 채팅방을 선택하거나 생성하세요.")

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
                    answer = f"채팅 요청 실패: {e}"

                st.write(answer)

        st.session_state["chat_messages"].append({
            "role": "assistant",
            "content": answer
        })


def extract_chat_result(result):
    if not isinstance(result, dict):
        return "채팅 결과를 해석하지 못했습니다.", ""

    success = result.get("success", False)
    if not success:
        error = result.get("error", {})
        if isinstance(error, dict):
            return error.get("message", "채팅 요청에 실패했습니다."), ""
        return "채팅 요청에 실패했습니다.", ""

    data = result.get("data")
    if not isinstance(data, dict):
        return "채팅 응답 데이터가 없습니다.", ""

    answer = data.get("answer", "")
    conversation_id = data.get("conversation_id", "")

    if not isinstance(answer, str) or not answer.strip():
        answer = "응답 내용이 비어 있습니다."

    if not isinstance(conversation_id, str):
        conversation_id = ""

    return answer, conversation_id