from __future__ import annotations

from typing import Any

from sqlalchemy import text

from db_schema import seed_categories
from db_state import as_dicts, engine


def get_categories(month: str) -> list[dict[str, Any]]:
    seed_categories(month)
    with engine().begin() as conn:
        rows = conn.execute(
            text("SELECT * FROM budget_categories WHERE month = :month ORDER BY type DESC, name"),
            {"month": month},
        ).fetchall()
    return as_dicts(rows)


def upsert_category(name: str, category_type: str, allocated: float, month: str) -> None:
    if category_type not in {"income", "expense"}:
        raise ValueError("Category type must be income or expense.")
    with engine().begin() as conn:
        row = conn.execute(
            text("SELECT id FROM budget_categories WHERE name = :name AND month = :month"),
            {"name": name.strip(), "month": month},
        ).fetchone()
        if row:
            conn.execute(
                text("UPDATE budget_categories SET type = :kind, allocated = :allocated WHERE id = :id"),
                {"kind": category_type, "allocated": float(allocated), "id": row._mapping["id"]},
            )
        else:
            conn.execute(
                text("INSERT INTO budget_categories(name, type, allocated, month) VALUES (:name, :kind, :allocated, :month)"),
                {"name": name.strip(), "kind": category_type, "allocated": float(allocated), "month": month},
            )


def delete_category(category_id: int) -> None:
    with engine().begin() as conn:
        conn.execute(text("DELETE FROM budget_categories WHERE id = :id"), {"id": category_id})


def add_transaction(date_str: str, description: str, amount: float, category_id: int | None, source: str = "manual", account_number: str | None = None, raw_data: str | None = None) -> None:
    with engine().begin() as conn:
        conn.execute(
            text("INSERT INTO transactions_app(date, description, amount, category_id, account_number, raw_data, source, month) VALUES (:date, :description, :amount, :category_id, :account_number, :raw_data, :source, :month)"),
            {"date": date_str, "description": description.strip(), "amount": float(amount), "category_id": category_id, "account_number": account_number, "raw_data": raw_data, "source": source, "month": date_str[:7]},
        )


def get_transactions(month: str, role: str = "admin") -> list[dict[str, Any]]:
    if role == "coach":
        return []
    query = "SELECT t.id, t.date, t.description, t.amount, t.source, t.month, c.name AS category, c.type AS category_type FROM transactions_app t LEFT JOIN budget_categories c ON c.id = t.category_id WHERE t.month = :month ORDER BY t.date DESC, t.id DESC"
    with engine().begin() as conn:
        rows = conn.execute(text(query), {"month": month}).fetchall()
    return as_dicts(rows)


def delete_transaction(transaction_id: int) -> None:
    with engine().begin() as conn:
        conn.execute(text("DELETE FROM transactions_app WHERE id = :id"), {"id": transaction_id})


def compute_left_to_budget(total_income: float, total_allocated: float) -> float:
    return round(float(total_income) - float(total_allocated), 2)


def left_to_budget_status(left: float) -> str:
    left = round(float(left), 2)
    if left == 0:
        return "balanced"
    return "unallocated" if left > 0 else "overallocated"


def get_budget_summary(month: str) -> dict[str, Any]:
    seed_categories(month)
    with engine().begin() as conn:
        cats = as_dicts(conn.execute(text("SELECT * FROM budget_categories WHERE month = :month"), {"month": month}).fetchall())
        query = "SELECT c.id AS category_id, c.name AS category, c.type AS category_type, c.allocated AS allocated, COALESCE(SUM(t.amount), 0) AS actual FROM budget_categories c LEFT JOIN transactions_app t ON t.category_id = c.id AND t.month = c.month WHERE c.month = :month GROUP BY c.id, c.name, c.type, c.allocated ORDER BY c.type DESC, c.name"
        actuals = as_dicts(conn.execute(text(query), {"month": month}).fetchall())
    income_allocated = sum(item["allocated"] for item in cats if item["type"] == "income")
    expense_allocated = sum(item["allocated"] for item in cats if item["type"] == "expense")
    left = compute_left_to_budget(income_allocated, expense_allocated)
    return {"month": month, "income_allocated": round(income_allocated, 2), "expense_allocated": round(expense_allocated, 2), "left_to_budget": left, "status": left_to_budget_status(left), "category_actuals": actuals}


def get_budget_summary_for_coach(month: str) -> dict[str, Any]:
    return get_budget_summary(month)


def get_category_actuals_for_coach(month: str) -> list[dict[str, Any]]:
    return get_budget_summary(month)["category_actuals"]
