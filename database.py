from __future__ import annotations

from datetime import date
from pathlib import Path

from config import is_postgres
from db_budget import add_transaction, compute_left_to_budget, delete_category, delete_transaction, get_budget_summary, get_budget_summary_for_coach, get_categories, get_category_actuals_for_coach, get_transactions, left_to_budget_status, upsert_category
from db_business import add_business_entry, delete_business_entry, get_business_summary, get_business_summary_for_coach, get_ledger_entries
from db_constants import BUSINESS_CATEGORIES, DEFAULT_CATEGORIES
from db_people import authenticate_user, create_user
from db_schema import init_tables, seed_categories
from db_security import hash_password, verify_password
from db_state import engine


def current_month() -> str:
    return date.today().strftime("%Y-%m")


def init_db(db_path: str | Path | None = None) -> None:
    init_tables(db_path)
    seed_month(current_month())


def seed_month(month: str, conn=None) -> None:
    seed_categories(month)


def required_tables_exist(db_path: str | Path | None = None) -> bool:
    with engine(db_path).begin() as conn:
        if is_postgres():
            rows = conn.exec_driver_sql("SELECT table_name AS name FROM information_schema.tables WHERE table_schema = 'public'").fetchall()
        else:
            rows = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {row._mapping["name"].lower() for row in rows}
    return {"users_app", "transactions_app", "budget_categories", "business_ledger"}.issubset(names)
