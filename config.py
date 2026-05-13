from __future__ import annotations

import os
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


APP_NAME = os.getenv("FINANCE_APP_NAME", "FinVault")
DATA_DIR = Path(os.getenv("FINANCE_APP_DATA_DIR", ".")).expanduser().resolve()
DB_PATH = Path(os.getenv("FINANCE_APP_DB_PATH", str(DATA_DIR / "finance_data.db"))).expanduser().resolve()
DEMO_MODE = _env_bool("FINANCE_APP_DEMO_MODE", True)
ALLOW_SIGNUP = _env_bool("FINANCE_APP_ALLOW_SIGNUP", False)


def ensure_data_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
