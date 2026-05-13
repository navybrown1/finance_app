from __future__ import annotations

import os
import tempfile
from pathlib import Path


def check(name: str, condition: bool, failures: list[str]) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}")
    if not condition:
        failures.append(name)


def main() -> int:
    tmp = tempfile.TemporaryDirectory()
    os.environ["FINANCE_APP_DB_PATH"] = str(Path(tmp.name) / "test_finance.db")
    failures: list[str] = []

    try:
        import app  # noqa: F401
        import ai_categorizer
        import database
        check("Modules import", True, failures)
    except Exception as exc:
        check(f"Modules import: {exc}", False, failures)
        return 1

    try:
        database.init_db()
        check("Database initializes", True, failures)
        check("Required tables exist", database.required_tables_exist(), failures)
        check("Admin authenticates", database.authenticate_user("admin", "admin123") is not None, failures)
        check("Coach authenticates", database.authenticate_user("coach", "coach123") is not None, failures)
        h = database.hash_password("test-pass")
        check("PBKDF2 hash created", h.startswith("pbkdf2_sha256$"), failures)
        check("PBKDF2 verifies", database.verify_password("test-pass", h), failures)
        check("Bad password fails", not database.verify_password("wrong", h), failures)
    except Exception as exc:
        check(f"Database tests: {exc}", False, failures)

    try:
        check("Zero balanced", database.compute_left_to_budget(5000, 5000) == 0, failures)
        check("Zero unallocated", database.compute_left_to_budget(5000, 4500) == 500, failures)
        check("Zero overallocated", database.compute_left_to_budget(5000, 5200) == -200, failures)
    except Exception as exc:
        check(f"Budget math tests: {exc}", False, failures)

    samples = {
        "amount": "Date,Description,Amount\n2026-05-01,Payroll,5000\n2026-05-02,Walmart,-25.50\n",
        "debit credit": "Date,Description,Debit,Credit\n2026-05-01,Payroll,,5000\n2026-05-02,Aldi,30.25,\n",
        "withdrawal deposit": "Posted Date,Payee,Withdrawal,Deposit\n2026-05-01,Payroll,,5000\n2026-05-02,Rent,1800,\n",
    }
    for label, text in samples.items():
        try:
            df = ai_categorizer.clean_csv(text)
            check(f"CSV cleaner handles {label}", len(df) == 2 and list(df.columns) == ["date", "description", "amount", "category", "source"], failures)
        except Exception as exc:
            check(f"CSV cleaner handles {label}: {exc}", False, failures)

    try:
        cats = database.get_categories("2026-05")
        income_id = next(c["id"] for c in cats if c["name"] == "Income")
        groceries_id = next(c["id"] for c in cats if c["name"] == "Groceries")
        database.add_transaction("2026-05-01", "Payroll Merchant Raw", 5000, income_id, account_number="1234", raw_data="secret")
        database.add_transaction("2026-05-02", "Walmart Raw Merchant", -40, groceries_id, account_number="9999", raw_data="secret")
        coach_rows = database.get_transactions("2026-05", role="coach")
        coach_summary = str(database.get_budget_summary_for_coach("2026-05"))
        check("Coach cannot fetch raw transactions", coach_rows == [], failures)
        check("Coach summary hides descriptions", "Walmart Raw Merchant" not in coach_summary, failures)
        check("Coach summary hides raw data", "secret" not in coach_summary and "9999" not in coach_summary, failures)
    except Exception as exc:
        check(f"Coach privacy tests: {exc}", False, failures)

    try:
        database.add_business_entry("2026-05-01", "Nails", "nail_service", 100)
        database.add_business_entry("2026-05-02", "Supplies", "supply_cost", 25)
        summary = database.get_business_summary_for_coach("2026-05")
        check("Business revenue total", summary["total_revenue"] == 100, failures)
        check("Business expense total", summary["total_expense"] == 25, failures)
        check("Business profit margin", summary["profit_margin_pct"] == 75, failures)
    except Exception as exc:
        check(f"Business tests: {exc}", False, failures)

    if failures:
        print("\nFailed checks:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
