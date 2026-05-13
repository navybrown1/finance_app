from __future__ import annotations

from typing import Any

from sqlalchemy import text

from db_constants import BUSINESS_CATEGORIES
from db_state import as_dicts, engine


def add_business_entry(date_str: str, description: str, category: str, amount: float) -> None:
    entry_type = BUSINESS_CATEGORIES.get(category.strip())
    if entry_type is None:
        raise ValueError(f"Unsupported business category: {category}")
    with engine().begin() as conn:
        conn.execute(
            text("INSERT INTO business_ledger(date, description, category, type, amount, month) VALUES (:date, :description, :category, :type, :amount, :month)"),
            {"date": date_str, "description": description.strip(), "category": category.strip(), "type": entry_type, "amount": abs(float(amount)), "month": date_str[:7]},
        )


def get_ledger_entries(month: str, role: str = "admin") -> list[dict[str, Any]]:
    if role == "coach":
        return []
    with engine().begin() as conn:
        rows = conn.execute(text("SELECT * FROM business_ledger WHERE month = :month ORDER BY date DESC, id DESC"), {"month": month}).fetchall()
    return as_dicts(rows)


def delete_business_entry(entry_id: int) -> None:
    with engine().begin() as conn:
        conn.execute(text("DELETE FROM business_ledger WHERE id = :id"), {"id": entry_id})


def get_business_summary(month: str) -> dict[str, Any]:
    with engine().begin() as conn:
        rows = as_dicts(conn.execute(text("SELECT category, type, SUM(amount) AS total FROM business_ledger WHERE month = :month GROUP BY category, type ORDER BY type DESC, category"), {"month": month}).fetchall())
    revenue = sum(row["total"] for row in rows if row["type"] == "revenue")
    expense = sum(row["total"] for row in rows if row["type"] == "expense")
    net = revenue - expense
    margin = round((net / revenue) * 100, 2) if revenue else None
    return {"month": month, "total_revenue": round(revenue, 2), "total_expense": round(expense, 2), "net_profit": round(net, 2), "profit_margin_pct": margin, "breakdown": rows, "expense_allocation_note": "Service-specific margins require service-specific expense tagging. Without that, only overall margin is exact."}


def get_business_summary_for_coach(month: str) -> dict[str, Any]:
    return get_business_summary(month)
