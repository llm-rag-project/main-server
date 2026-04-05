import streamlit as st

from api.auth import login, logout, signup


def render_login_box():
    st.sidebar.subheader("로그인 / 회원가입")

    is_logged_in = st.session_state.get("is_logged_in", False)
    user = st.session_state.get("user")

    if is_logged_in:
        st.sidebar.success("로그인됨")

        if user:
            email = user.get("email", "")
            nickname = user.get("nickname") or user.get("name") or ""
            if nickname:
                st.sidebar.caption(f"{nickname} ({email})")
            else:
                st.sidebar.caption(email)

        if st.sidebar.button("로그아웃", use_container_width=True):
            logout()
            st.rerun()

        st.sidebar.divider()
        return

    tab1, tab2 = st.sidebar.tabs(["로그인", "회원가입"])

    with tab1:
        login_email = st.text_input("이메일", key="login_email")
        login_password = st.text_input("비밀번호", type="password", key="login_password")

        if st.button("로그인", key="login_btn", use_container_width=True):
            if not login_email or not login_password:
                st.warning("이메일과 비밀번호를 입력하세요.")
            else:
                try:
                    login(login_email, login_password)
                    st.success("로그인 성공")
                    st.rerun()
                except Exception as e:
                    st.error(f"로그인 실패: {e}")

    with tab2:
        signup_name = st.text_input("이름", key="signup_name")
        signup_email = st.text_input("이메일", key="signup_email")
        signup_password = st.text_input("비밀번호", type="password", key="signup_password")
        signup_password_check = st.text_input("비밀번호 확인", type="password", key="signup_password_check")

        if st.button("회원가입", key="signup_btn", use_container_width=True):
            if not signup_email or not signup_password:
                st.warning("이메일과 비밀번호를 입력하세요.")
            elif signup_password != signup_password_check:
                st.warning("비밀번호가 일치하지 않습니다.")
            else:
                try:
                    result = signup(signup_email, signup_password, signup_name)
                    st.success("회원가입 성공")
                    st.write(result)
                except Exception as e:
                    st.error(f"회원가입 실패: {e}")

    st.sidebar.divider()