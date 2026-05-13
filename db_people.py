from __future__ import annotations

from typing import Any

from sqlalchemy import text

from db_security import hash_password, verify_password
from db_state import engine


def create_user(username: str, key_value: str, role: str) -> bool:
    if role not in {"admin", "coach"}:
        raise ValueError("Role must be admin or coach.")
    try:
        with engine().begin() as conn:
            conn.execute(
                text("INSERT INTO users_app(username, key_digest, role) VALUES (:u, :h, :r)"),
                {"u": username.strip(), "h": hash_password(key_value), "r": role},
            )
        return True
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            return False
        raise


def authenticate_user(username: str, key_value: str) -> dict[str, Any] | None:
    with engine().begin() as conn:
        row = conn.execute(text("SELECT * FROM users_app WHERE username = :u"), {"u": username.strip()}).fetchone()
    if row and verify_password(key_value, row._mapping["key_digest"]):
        user = dict(row._mapping)
        user.pop("key_digest", None)
        return user
    return None
