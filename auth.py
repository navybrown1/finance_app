from __future__ import annotations

import streamlit as st


def init_session() -> None:
    st.session_state.setdefault("authenticated", True)
    st.session_state.setdefault("user", {"username": "local", "role": "admin"})


def login_form() -> bool:
    init_session()
    return True


def current_user() -> dict | None:
    init_session()
    return st.session_state.get("user")


def require_role(*roles: str) -> bool:
    user = current_user()
    return bool(user and user.get("role") in roles)


def logout_button() -> None:
    return None
