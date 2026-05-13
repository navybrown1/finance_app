from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine, text

from config import DATABASE_URL, DB_PATH, ensure_data_dir, is_postgres

_ENGINE = None


def db_url(db_path: str | Path | None = None) -> str:
    if is_postgres():
        return str(DATABASE_URL)
    ensure_data_dir()
    path = Path(db_path or DB_PATH).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def engine(db_path: str | Path | None = None):
    global _ENGINE
    if db_path is not None:
        return create_engine(db_url(db_path), future=True)
    if _ENGINE is None:
        options = {"future": True, "pool_pre_ping": True}
        if is_postgres():
            options["connect_args"] = {"sslmode": "require"}
        _ENGINE = create_engine(db_url(), **options)
    return _ENGINE


def as_dicts(result_rows):
    return [dict(row._mapping) for row in result_rows]


def run(sql: str, params: dict | None = None):
    with engine().begin() as conn:
        return conn.execute(text(sql), params or {})
