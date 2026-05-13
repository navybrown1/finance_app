from __future__ import annotations

import streamlit as st
from sqlalchemy import text

from database import authenticate_user, create_user
from db_state import engine


def init_session() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)


def _has_any_account() -> bool:
    with engine().begin() as conn:
        row = conn.execute(text("SELECT COUNT(*) AS total FROM users_app")).fetchone()
    return int(row._mapping["total"]) > 0


def _first_run_form() -> bool:
    st.title("FinVault setup")
    st.caption("Create the first local admin account for this deployment.")
    with st.form("first_run_form"):
        name_value = st.text_input("User name", value="admin")
        key_value = st.text_input("Access key", type="password")
        submitted = st.form_submit_button("Create admin", use_container_width=True)
    if submitted:
        if not name_value.strip() or not key_value:
            st.error("Enter a user name and access key.")
            return False
        if create_user(name_value, key_value, "admin"):
            st.success("Admin created. Sign in now.")
            st.rerun()
        else:
            st.error("That user name already exists.")
    return False


def login_form() -> bool:
    init_session()
    if st.session_state["authenticated"]:
        return True
    if not _has_any_account():
        return _first_run_form()

    st.title("FinVault")
    st.caption("Private budgeting workspace")
    with st.form("access_form"):
        name_value = st.text_input("User name")
        key_value = st.text_input("Access key", type="password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
        user = authenticate_user(name_value, key_value)
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
