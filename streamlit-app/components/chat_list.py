import streamlit as st
from api.chat_rooms import create_chat, get_chat_detail, get_chat_list


def _unwrap_response(result):
    """
    응답 형태를 둘 다 지원:
    1) 래핑 응답: {"success": true, "data": {...}, "error": null}
    2) 직접 응답: {...}
    """
    if not isinstance(result, dict):
        raise ValueError(f"응답 형식이 dict가 아닙니다: {type(result)}")

    if "success" in result:
        success = result.get("success", False)
        if not success:
            error = result.get("error")
            if isinstance(error, dict):
                message = error.get("message") or error.get("detail") or "요청에 실패했습니다."
            else:
                message = str(error) if error is not None else "요청에 실패했습니다."
            raise ValueError(message)

        return result.get("data", {})

    return result


def render_chat_list():
    st.subheader("채팅방")

    if "selected_chat_id" not in st.session_state:
        st.session_state["selected_chat_id"] = None

    if "chat_conversation_id" not in st.session_state:
        st.session_state["chat_conversation_id"] = ""

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    with st.expander("새 채팅방 만들기", expanded=False):
        with st.form("create_chat_form", clear_on_submit=True):
            new_title = st.text_input("채팅방 제목", key="new_chat_title_input")
            context_type = st.selectbox(
                "컨텍스트 타입",
                options=["GENERAL", "ARTICLE"],
                index=0,
                key="new_chat_context_type_input",
            )
            submitted = st.form_submit_button("채팅방 생성", use_container_width=True)

        if submitted:
            try:
                title = (new_title or "").strip()
                if not title:
                    st.warning("채팅방 제목을 입력하세요.")
                else:
                    result = create_chat(title=title, context_type=context_type)
                    data = _unwrap_response(result)

                    created_chat_id = data.get("id")
                    external_conversation_id = data.get("external_conversation_id") or ""

                    if not created_chat_id:
                        raise ValueError(f"생성 응답에 id가 없습니다: {data}")

                    st.session_state["selected_chat_id"] = created_chat_id
                    st.session_state["chat_conversation_id"] = external_conversation_id
                    st.session_state["chat_messages"] = []

                    st.success("채팅방이 생성되었습니다.")
                    st.rerun()

            except Exception as e:
                st.error(f"채팅방 생성 실패: {e}")

    st.markdown("---")

    try:
        result = get_chat_list(page=1, size=50)
        data = _unwrap_response(result)

        # 직접 응답/래핑 응답 둘 다 처리
        if isinstance(data, dict) and "items" in data:
            items = data.get("items", [])
        elif isinstance(data, list):
            items = data
        else:
            items = []

        if not items:
            st.info("채팅방이 없습니다.")
            return

        for chat in items:
            if not isinstance(chat, dict):
                continue

            chat_id = chat.get("id")
            title = chat.get("title", f"채팅방 {chat_id}")
            last_message = chat.get("last_message") or ""
            is_selected = st.session_state.get("selected_chat_id") == chat_id

            label = f"✅ {title}" if is_selected else title

            if st.button(label, key=f"chat_room_{chat_id}", use_container_width=True):
                try:
                    detail_result = get_chat_detail(chat_id)
                    detail_data = _unwrap_response(detail_result)

                    st.session_state["selected_chat_id"] = detail_data.get("id")
                    st.session_state["chat_conversation_id"] = detail_data.get("external_conversation_id") or ""
                    st.session_state["chat_messages"] = []

                    if last_message:
                        st.session_state["chat_messages"].append({
                            "role": "assistant",
                            "content": last_message
                        })

                    st.rerun()

                except Exception as e:
                    st.error(f"채팅방 선택 실패: {e}")

    except Exception as e:
        st.error(f"채팅방 목록을 불러오지 못했습니다: {e}")