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

    if "chat_list_refresh_token" not in st.session_state:
        st.session_state["chat_list_refresh_token"] = 0

    # 생성 폼
    with st.expander("새 채팅방 만들기", expanded=True):
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
                    result = create_chat(
                        title=title,
                        context_type=context_type,
                    )

                    if not isinstance(result, dict):
                        st.error(f"생성 응답 형식이 이상합니다: {type(result)}")
                        return

                    # result가 바로 데이터일 경우 처리
                    if "id" in result:
                        data = result
                    else:
                        success = result.get("success", False)
                        if not success:
                            error = result.get("error")
                            if isinstance(error, dict):
                                st.error(error.get("message", "채팅방 생성 실패"))
                            else:
                                st.error(f"채팅방 생성 실패: {error}")
                            return
                        data = result.get("data", {})

                    created_chat_id = data.get("id")
                    external_conversation_id = data.get("external_conversation_id") or ""

                    if not created_chat_id:
                        st.error(f"생성은 됐지만 chat id가 없습니다: {data}")
                        return

                    st.session_state["selected_chat_id"] = created_chat_id
                    st.session_state["chat_conversation_id"] = external_conversation_id
                    st.session_state["chat_messages"] = []
                    st.session_state["chat_list_refresh_token"] += 1

                    st.success("채팅방이 생성되었습니다.")
                    st.rerun()

            except Exception as e:
                st.error(f"채팅방 생성 실패: {e}")

    st.markdown("---")

    # 목록 조회
    try:
        result = get_chat_list(page=1, size=50)

        if not isinstance(result, dict):
            st.error(f"목록 응답 형식이 이상합니다: {type(result)}")
            return

        success = result.get("success", False)
        data = result.get("data")
        error = result.get("error")

        if not success:
            if isinstance(error, dict):
                st.error(error.get("message", "채팅방 목록을 불러오지 못했습니다."))
            else:
                st.error(f"채팅방 목록을 불러오지 못했습니다: {error}")
            return

        if not isinstance(data, dict):
            st.error(f"목록 data 형식이 이상합니다: {data}")
            return

        items = data.get("items", [])

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

                    if not isinstance(detail_result, dict):
                        st.error(f"상세 응답 형식이 이상합니다: {type(detail_result)}")
                        return

                    detail_success = detail_result.get("success", False)
                    detail_data = detail_result.get("data")
                    detail_error = detail_result.get("error")

                    if not detail_success:
                        if isinstance(detail_error, dict):
                            st.error(detail_error.get("message", "채팅방 상세를 불러오지 못했습니다."))
                        else:
                            st.error(f"채팅방 상세를 불러오지 못했습니다: {detail_error}")
                        return

                    if not isinstance(detail_data, dict):
                        st.error(f"상세 data 형식이 이상합니다: {detail_data}")
                        return

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
        st.error(f"채팅방 목록 조회 실패: {e}")