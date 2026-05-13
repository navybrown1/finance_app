from __future__ import annotations

import streamlit as st

from database import authenticate_user


def init_session() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)


def login_form() -> bool:
    init_session()
    if st.session_state["authenticated"]:
        return True

    st.title("FinVault")
    st.caption("Private budgeting workspace")
    with st.form("access_form"):
        name_value = st.text_input("User name")
        secret_value = st.text_input("Access key", type="password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
        user = authenticate_user(name_value, secret_value)
        if user:
            st.session_state["authenticated"] = True
            st.session_state["user"] = user
            st.rerun()
        st.error("Access check failed.")
    return False


def current_user() -> dict | None:
    init_session()
    return st.session_state.get("user")


def require_role(*roles: str) -> bool:
    user = current_user()
    return bool(user and user.get("role") in roles)


def logout_button() -> None:
    if st.sidebar.button("Sign out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["user"] = None
        st.rerun()
