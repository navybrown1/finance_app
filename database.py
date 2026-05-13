from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from config import DB_PATH, ensure_data_dir


DEFAULT_CATEGORIES = [
    ("Income", "income", 0.0),
    ("Housing", "expense", 0.0),
    ("Groceries", "expense", 0.0),
    ("Transportation", "expense", 0.0),
    ("Utilities", "expense", 0.0),
    ("Insurance", "expense", 0.0),
    ("Debt", "expense", 0.0),
    ("Investments", "expense", 0.0),
    ("Savings", "expense", 0.0),
    ("Entertainment", "expense", 0.0),
    ("Other", "expense", 0.0),
]
BUSINESS_CATEGORIES = {
    "bundle_sale": "revenue",
    "nail_service": "revenue",
    "lash_service": "revenue",
    "supply_cost": "expense",
    "marketing": "expense",
    "tools_equipment": "expense",
    "other_expense": "expense",
}


def current_month() -> str:
    return date.today().strftime("%Y-%m")


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = os.urandom(16)
    rounds = 210_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return "pbkdf2_sha256${}${}${}".format(
        rounds,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    if not password or not stored_hash:
        return False
    try:
        algorithm, rounds_s, salt_s, digest_s = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        salt = base64.b64decode(salt_s.encode("ascii"))
        expected = base64.b64decode(digest_s.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


@contextmanager
def get_connection(db_path: str | Path | None = None):
    ensure_data_dir()
    path = Path(db_path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def init_db(db_path: str | Path | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','coach')),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS BudgetCategories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('income','expense')),
                allocated REAL NOT NULL DEFAULT 0,
                month TEXT NOT NULL,
                UNIQUE(name, month)
            );
            CREATE TABLE IF NOT EXISTS Transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                category_id INTEGER,
                account_number TEXT,
                raw_data TEXT,
                source TEXT DEFAULT 'manual',
                month TEXT NOT NULL,
                FOREIGN KEY(category_id) REFERENCES BudgetCategories(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS BusinessLedger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('revenue','expense')),
                amount REAL NOT NULL,
                month TEXT NOT NULL
            );
            """
        )
        create_user("admin", "admin123", "admin", conn=conn)
        create_user("coach", "coach123", "coach", conn=conn)
        seed_month(current_month(), conn=conn)


def create_user(username: str, password: str, role: str, conn: sqlite3.Connection | None = None) -> bool:
    if role not in {"admin", "coach"}:
        raise ValueError("Role must be admin or coach.")

    def _insert(c: sqlite3.Connection) -> bool:
        try:
            c.execute(
                "INSERT INTO Users(username, password_hash, role) VALUES (?, ?, ?)",
                (username.strip(), hash_password(password), role),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    if conn is not None:
        return _insert(conn)
    with get_connection() as c:
        return _insert(c)


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM Users WHERE username = ?", (username.strip(),)).fetchone()
        if row and verify_password(password, row["password_hash"]):
            user = dict(row)
            user.pop("password_hash", None)
            return user
    return None


def seed_month(month: str, conn: sqlite3.Connection | None = None) -> None:
    def _seed(c: sqlite3.Connection) -> None:
        for name, typ, amount in DEFAULT_CATEGORIES:
            c.execute(
                "INSERT OR IGNORE INTO BudgetCategories(name, type, allocated, month) VALUES (?, ?, ?, ?)",
                (name, typ, amount, month),
            )
    if conn is not None:
        _seed(conn)
    else:
        with get_connection() as c:
            _seed(c)


def get_categories(month: str) -> list[dict[str, Any]]:
    seed_month(month)
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM BudgetCategories WHERE month = ? ORDER BY type DESC, name", (month,)).fetchall()
    return rows_to_dicts(rows)


def upsert_category(name: str, category_type: str, allocated: float, month: str) -> None:
    if category_type not in {"income", "expense"}:
        raise ValueError("Category type must be income or expense.")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO BudgetCategories(name, type, allocated, month)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name, month) DO UPDATE SET type=excluded.type, allocated=excluded.allocated
            """,
            (name.strip(), category_type, float(allocated), month),
        )


def delete_category(category_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM BudgetCategories WHERE id = ?", (category_id,))


def add_transaction(date_str: str, description: str, amount: float, category_id: int | None, source: str = "manual", account_number: str | None = None, raw_data: str | None = None) -> None:
    month = date_str[:7]
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO Transactions(date, description, amount, category_id, account_number, raw_data, source, month)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (date_str, description.strip(), float(amount), category_id, account_number, raw_data, source, month),
        )


def get_transactions(month: str, role: str = "admin") -> list[dict[str, Any]]:
    if role == "coach":
        return []
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.date, t.description, t.amount, t.source, t.month,
                   c.name AS category, c.type AS category_type
            FROM Transactions t
            LEFT JOIN BudgetCategories c ON c.id = t.category_id
            WHERE t.month = ?
            ORDER BY t.date DESC, t.id DESC
            """,
            (month,),
        ).fetchall()
    return rows_to_dicts(rows)


def delete_transaction(transaction_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM Transactions WHERE id = ?", (transaction_id,))


def compute_left_to_budget(total_income: float, total_allocated: float) -> float:
    return round(float(total_income) - float(total_allocated), 2)


def left_to_budget_status(left: float) -> str:
    left = round(float(left), 2)
    if left == 0:
        return "balanced"
    if left > 0:
        return "unallocated"
    return "overallocated"


def get_budget_summary(month: str) -> dict[str, Any]:
    seed_month(month)
    with get_connection() as conn:
        cats = rows_to_dicts(conn.execute("SELECT * FROM BudgetCategories WHERE month = ?", (month,)).fetchall())
        actuals = rows_to_dicts(
            conn.execute(
                """
                SELECT c.id AS category_id, c.name AS category, c.type AS category_type,
                       c.allocated AS allocated, COALESCE(SUM(t.amount), 0) AS actual
                FROM BudgetCategories c
                LEFT JOIN Transactions t ON t.category_id = c.id AND t.month = c.month
                WHERE c.month = ?
                GROUP BY c.id, c.name, c.type, c.allocated
                ORDER BY c.type DESC, c.name
                """,
                (month,),
            ).fetchall()
        )
    income_allocated = sum(c["allocated"] for c in cats if c["type"] == "income")
    expense_allocated = sum(c["allocated"] for c in cats if c["type"] == "expense")
    left = compute_left_to_budget(income_allocated, expense_allocated)
    return {
        "month": month,
        "income_allocated": round(income_allocated, 2),
        "expense_allocated": round(expense_allocated, 2),
        "left_to_budget": left,
        "status": left_to_budget_status(left),
        "category_actuals": actuals,
    }


def get_budget_summary_for_coach(month: str) -> dict[str, Any]:
    return get_budget_summary(month)


def get_category_actuals_for_coach(month: str) -> list[dict[str, Any]]:
    return get_budget_summary(month)["category_actuals"]


def add_business_entry(date_str: str, description: str, category: str, amount: float) -> None:
    category = category.strip()
    entry_type = BUSINESS_CATEGORIES.get(category)
    if entry_type is None:
        raise ValueError(f"Unsupported business category: {category}")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO BusinessLedger(date, description, category, type, amount, month)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (date_str, description.strip(), category, entry_type, abs(float(amount)), date_str[:7]),
        )


def get_ledger_entries(month: str, role: str = "admin") -> list[dict[str, Any]]:
    if role == "coach":
        return []
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM BusinessLedger WHERE month = ? ORDER BY date DESC, id DESC", (month,)).fetchall()
    return rows_to_dicts(rows)


def delete_business_entry(entry_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM BusinessLedger WHERE id = ?", (entry_id,))


def get_business_summary(month: str) -> dict[str, Any]:
    with get_connection() as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT category, type, SUM(amount) AS total
                FROM BusinessLedger
                WHERE month = ?
                GROUP BY category, type
                ORDER BY type DESC, category
                """,
                (month,),
            ).fetchall()
        )
    revenue = sum(r["total"] for r in rows if r["type"] == "revenue")
    expense = sum(r["total"] for r in rows if r["type"] == "expense")
    net = revenue - expense
    margin = round((net / revenue) * 100, 2) if revenue else None
    return {
        "month": month,
        "total_revenue": round(revenue, 2),
        "total_expense": round(expense, 2),
        "net_profit": round(net, 2),
        "profit_margin_pct": margin,
        "breakdown": rows,
        "expense_allocation_note": "Service-specific margins require service-specific expense tagging. Without that, only overall margin is exact.",
    }


def get_business_summary_for_coach(month: str) -> dict[str, Any]:
    return get_business_summary(month)


def required_tables_exist(db_path: str | Path | None = None) -> bool:
    required = {"Users", "Transactions", "BudgetCategories", "BusinessLedger"}
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return required.issubset({row["name"] for row in rows})
