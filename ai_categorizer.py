from __future__ import annotations

import json
import re
from io import StringIO
from typing import Iterable

import pandas as pd

from database import add_transaction, get_categories

DATE_NAMES = ["date", "transaction date", "posted date", "post date", "posting date"]
DESCRIPTION_NAMES = ["description", "memo", "details", "merchant", "payee", "transaction", "name"]
AMOUNT_NAMES = ["amount", "transaction amount"]
DEBIT_NAMES = ["debit", "withdrawal", "withdrawals", "payment", "charge", "spent"]
CREDIT_NAMES = ["credit", "deposit", "deposits", "received"]


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower().replace("_", " ").replace("-", " "))


def _find_column(columns: Iterable[str], candidates: list[str]) -> str | None:
    lookup = {_norm(c): c for c in columns}
    for candidate in candidates:
        if candidate in lookup:
            return lookup[candidate]
    for normalized, original in lookup.items():
        if any(candidate in normalized for candidate in candidates):
            return original
    return None


def parse_amount(value) -> float:
    if pd.isna(value) or str(value).strip() == "":
        return 0.0
    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.replace("$", "").replace(",", "").replace("(", "").replace(")", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", ".", "-"}:
        return 0.0
    amount = float(text)
    return -abs(amount) if negative else amount


def local_llm_categorize_transaction(description: str) -> str:
    """Local-first categorization stub.

    This function intentionally uses local rules only. To add Ollama or llama.cpp later,
    replace the rule block with a local subprocess or localhost call. Do not send bank
    data to a commercial cloud API from this function.
    """
    text = (description or "").lower()
    rules = [
        ("Groceries", ["walmart", "aldi", "kroger", "wegmans", "grocery", "market", "costco"]),
        ("Transportation", ["shell", "exxon", "gas", "fuel", "uber", "lyft"]),
        ("Housing", ["rent", "mortgage", "landlord"]),
        ("Utilities", ["electric", "utility", "water", "internet", "spectrum", "verizon", "tmobile"]),
        ("Insurance", ["insurance", "geico", "progressive", "usaa"]),
        ("Entertainment", ["netflix", "spotify", "cinema", "theater", "hulu"]),
        ("Debt", ["loan", "credit card", "amex", "chase", "capital one"]),
        ("Investments", ["brokerage", "vanguard", "fidelity", "robinhood"]),
        ("Income", ["payroll", "deposit", "salary", "direct dep"]),
    ]
    for category, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return category
    return "Other"


def clean_csv(file_obj) -> pd.DataFrame:
    try:
        if isinstance(file_obj, (str, bytes)):
            df = pd.read_csv(StringIO(file_obj.decode() if isinstance(file_obj, bytes) else file_obj))
        else:
            df = pd.read_csv(file_obj)
    except Exception as exc:
        raise ValueError(f"Unable to read CSV file: {exc}") from exc

    if df.empty:
        raise ValueError("CSV file is empty.")

    date_col = _find_column(df.columns, DATE_NAMES)
    desc_col = _find_column(df.columns, DESCRIPTION_NAMES)
    amount_col = _find_column(df.columns, AMOUNT_NAMES)
    debit_col = _find_column(df.columns, DEBIT_NAMES)
    credit_col = _find_column(df.columns, CREDIT_NAMES)

    missing = []
    if not date_col:
        missing.append("date")
    if not desc_col:
        missing.append("description")
    if not amount_col and not (debit_col or credit_col):
        missing.append("amount or debit/credit")
    if missing:
        raise ValueError("Could not detect required CSV columns: " + ", ".join(missing))

    cleaned_rows = []
    skipped = 0
    for _, row in df.iterrows():
        date_value = pd.to_datetime(row.get(date_col), errors="coerce")
        description = str(row.get(desc_col, "")).strip()
        if pd.isna(date_value) or not description:
            skipped += 1
            continue

        if amount_col:
            amount = parse_amount(row.get(amount_col))
        else:
            debit = abs(parse_amount(row.get(debit_col))) if debit_col else 0.0
            credit = abs(parse_amount(row.get(credit_col))) if credit_col else 0.0
            if debit and credit:
                amount = credit - debit
            elif debit:
                amount = -debit
            else:
                amount = credit

        if amount == 0:
            skipped += 1
            continue

        cleaned_rows.append(
            {
                "date": date_value.strftime("%Y-%m-%d"),
                "description": description,
                "amount": round(float(amount), 2),
                "category": local_llm_categorize_transaction(description),
                "source": "bank_import",
            }
        )

    result = pd.DataFrame(cleaned_rows, columns=["date", "description", "amount", "category", "source"])
    result.attrs["skipped_rows"] = skipped
    if result.empty:
        raise ValueError("No valid transactions found after cleaning the CSV.")
    return result


def import_csv_to_database(cleaned_df: pd.DataFrame, month: str | None = None) -> int:
    if cleaned_df.empty:
        return 0
    imported = 0
    category_rows = get_categories(month or str(cleaned_df.iloc[0]["date"])[:7])
    category_by_name = {row["name"]: row["id"] for row in category_rows}
    for _, row in cleaned_df.iterrows():
        category_id = category_by_name.get(row["category"]) or category_by_name.get("Other")
        add_transaction(
            str(row["date"]),
            str(row["description"]),
            float(row["amount"]),
            category_id,
            source="bank_import",
            raw_data=json.dumps(row.to_dict(), default=str),
        )
        imported += 1
    return imported
