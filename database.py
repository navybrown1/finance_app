from __future__ import annotations

from datetime import date


def current_month() -> str:
    return date.today().strftime("%Y-%m")
