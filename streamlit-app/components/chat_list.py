import streamlit as st
from api.chat_rooms import create_chat, get_chat_detail, get_chat_list


def render_chat_list():
    st.subheader("채팅방")

    if "selected_chat_id" not in st.session_state:
        st.session_state["selected_chat_id"] = None

    if "chat_conversation_id" not in st.session_state:
        st.session_state["chat_conversation_id"] = ""

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    with st.expander("새 채팅방 만들기", expanded=False):
        new_title = st.text_input("채팅방 제목", key="new_chat_title")
        context_type = st.selectbox(
            "컨텍스트 타입",
            options=["GENERAL", "ARTICLE"],
            index=0,
            key="new_chat_context_type",
        )

        if st.button("채팅방 생성", use_container_width=True):
            try:
                if not new_title.strip():
                    st.warning("채팅방 제목을 입력하세요.")
                else:
                    result = create_chat(
                        title=new_title.strip(),
                        context_type=context_type,
                    )

                    success = result.get("success", False)
                    data = result.get("data", {}) if isinstance(result, dict) else {}

                    if success and isinstance(data, dict):
                        created_chat_id = data.get("id")
                        external_conversation_id = data.get("external_conversation_id") or ""

                        st.session_state["selected_chat_id"] = created_chat_id
                        st.session_state["chat_conversation_id"] = external_conversation_id
                        st.session_state["chat_messages"] = []

                        st.success("채팅방이 생성되었습니다.")
                        st.rerun()
                    else:
                        error = result.get("error", {}) if isinstance(result, dict) else {}
                        if isinstance(error, dict):
                            st.error(error.get("message", "채팅방 생성에 실패했습니다."))
                        else:
                            st.error("채팅방 생성에 실패했습니다.")
            except Exception as e:
                st.error(f"채팅방 생성 실패: {e}")

    st.markdown("---")

    try:
        result = get_chat_list(page=1, size=50)

        success = result.get("success", False)
        if not success:
            error = result.get("error", {}) if isinstance(result, dict) else {}
            if isinstance(error, dict):
                st.error(error.get("message", "채팅방 목록을 불러오지 못했습니다."))
            else:
                st.error("채팅방 목록을 불러오지 못했습니다.")
            return

        data = result.get("data", {})
        if not isinstance(data, dict):
            st.info("채팅방 데이터가 없습니다.")
            return

        items = data.get("items", [])
        if not items:
            st.info("생성된 채팅방이 없습니다.")
            return

        for chat in items:
            if not isinstance(chat, dict):
                continue

            chat_id = chat.get("id")
            title = chat.get("title", f"채팅방 {chat_id}")
            last_message = chat.get("last_message") or ""
            is_selected = st.session_state.get("selected_chat_id") == chat_id

            button_label = f"✅ {title}" if is_selected else title

            if st.button(button_label, key=f"chat_room_{chat_id}", use_container_width=True):
                try:
                    detail_result = get_chat_detail(chat_id)

                    detail_success = detail_result.get("success", False)
                    detail_data = detail_result.get("data", {}) if isinstance(detail_result, dict) else {}

                    if detail_success and isinstance(detail_data, dict):
                        st.session_state["selected_chat_id"] = detail_data.get("id")
                        st.session_state["chat_conversation_id"] = detail_data.get("external_conversation_id") or ""
                        st.session_state["chat_messages"] = []

                        if last_message:
                            st.session_state["chat_messages"].append({
                                "role": "assistant",
                                "content": last_message
                            })

                        st.rerun()
                    else:
                        error = detail_result.get("error", {}) if isinstance(detail_result, dict) else {}
                        if isinstance(error, dict):
                            st.error(error.get("message", "채팅방 상세를 불러오지 못했습니다."))
                        else:
                            st.error("채팅방 상세를 불러오지 못했습니다.")

                except Exception as e:
                    st.error(f"채팅방 선택 실패: {e}")

    except Exception as e:
        st.error(f"채팅방 목록 조회 실패: {e}")