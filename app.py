from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from ai_categorizer import clean_csv, import_csv_to_database, local_llm_categorize_transaction
from auth import current_user, login_form, logout_button, require_role
from config import APP_NAME, DB_PATH
from database import (
    BUSINESS_CATEGORIES,
    add_business_entry,
    add_transaction,
    delete_business_entry,
    delete_transaction,
    get_budget_summary,
    get_budget_summary_for_coach,
    get_business_summary,
    get_business_summary_for_coach,
    get_categories,
    get_ledger_entries,
    get_transactions,
    init_db,
    upsert_category,
)

st.set_page_config(page_title=APP_NAME, page_icon="💰", layout="wide")

st.markdown(
    """
<style>
.block-container {padding-top: 1.5rem;}
[data-testid="stMetricValue"] {font-size: 2rem;}
.card {padding: 1rem; border: 1px solid rgba(255,255,255,.08); border-radius: 18px; background: rgba(255,255,255,.03);}
.small-muted {color: #9AA4B2; font-size: .9rem;}
</style>
""",
    unsafe_allow_html=True,
)


def money(value: float | int | None) -> str:
    return "$0.00" if value is None else f"${value:,.2f}"


def pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}%"


def month_picker() -> str:
    return st.sidebar.text_input("Month", value=date.today().strftime("%Y-%m"), help="Use YYYY-MM format")


def render_budget(month: str, role: str) -> None:
    summary = get_budget_summary_for_coach(month) if role == "coach" else get_budget_summary(month)
    st.header("Zero-Based Budget")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Monthly income", money(summary["income_allocated"]))
    c2.metric("Allocated expenses", money(summary["expense_allocated"]))
    c3.metric("Left to budget", money(summary["left_to_budget"]))
    c4.metric("Status", summary["status"].replace("_", " ").title())

    left = summary["left_to_budget"]
    if left == 0:
        st.success("Balanced. Every dollar has a job.")
    elif left > 0:
        st.warning(f"You still need to assign {money(left)}.")
    else:
        st.error(f"You are overallocated by {money(abs(left))}.")

    actuals = pd.DataFrame(summary["category_actuals"])
    if not actuals.empty:
        actuals["actual_abs"] = actuals["actual"].abs()
        st.plotly_chart(px.bar(actuals, x="category", y=["allocated", "actual_abs"], barmode="group", title="Budget vs actual by category"), use_container_width=True)
        expense_actuals = actuals[actuals["category_type"] == "expense"]
        if not expense_actuals.empty and expense_actuals["allocated"].sum() > 0:
            st.plotly_chart(px.pie(expense_actuals, names="category", values="allocated", hole=.45, title="Expense allocation"), use_container_width=True)

    if role == "coach":
        st.info("Coach view is aggregate only. Raw transactions and merchant descriptions are hidden.")
        return

    st.subheader("Manage categories")
    with st.form("category_form"):
        col1, col2, col3 = st.columns([2, 1, 1])
        name = col1.text_input("Category name")
        typ = col2.selectbox("Type", ["expense", "income"])
        allocated = col3.number_input("Allocated", min_value=0.0, step=25.0)
        if st.form_submit_button("Save category") and name.strip():
            upsert_category(name, typ, allocated, month)
            st.success("Category saved.")
            st.rerun()

    categories = get_categories(month)
    st.dataframe(pd.DataFrame(categories), use_container_width=True, hide_index=True)

    st.subheader("Manual transaction")
    with st.form("transaction_form"):
        col1, col2, col3 = st.columns([1, 2, 1])
        t_date = col1.date_input("Date", value=date.today()).strftime("%Y-%m-%d")
        desc = col2.text_input("Description")
        amount = col3.number_input("Amount", step=1.0, help="Expenses should be negative. Income should be positive.")
        cat_names = {f"{c['name']} ({c['type']})": c["id"] for c in categories}
        selected = st.selectbox("Category", list(cat_names.keys())) if cat_names else None
        if st.form_submit_button("Add transaction") and desc.strip() and selected:
            add_transaction(t_date, desc, amount, cat_names[selected])
            st.success("Transaction added.")
            st.rerun()

    transactions = pd.DataFrame(get_transactions(month, role="admin"))
    st.subheader("Transactions")
    if transactions.empty:
        st.caption("No transactions for this month yet.")
    else:
        st.dataframe(transactions, use_container_width=True, hide_index=True)
        with st.expander("Delete transaction"):
            tx_id = st.number_input("Transaction ID", min_value=1, step=1)
            if st.button("Delete selected transaction"):
                delete_transaction(int(tx_id))
                st.rerun()


def render_import(month: str) -> None:
    st.header("CSV Import")
    st.write("Upload a bank CSV. Data is cleaned inside this app and never sent to an external API.")
    uploaded = st.file_uploader("CSV statement", type=["csv"])
    if not uploaded:
        return
    try:
        cleaned = clean_csv(uploaded)
        st.success(f"Cleaned {len(cleaned)} transactions. Skipped {cleaned.attrs.get('skipped_rows', 0)} invalid rows.")
        st.dataframe(cleaned, use_container_width=True, hide_index=True)
        if st.button("Import cleaned transactions", type="primary"):
            imported = import_csv_to_database(cleaned, month=month)
            st.success(f"Imported {imported} transactions.")
    except Exception as exc:
        st.error(str(exc))


def render_business(month: str, role: str) -> None:
    summary = get_business_summary_for_coach(month) if role == "coach" else get_business_summary(month)
    st.header("Business Ledger")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", money(summary["total_revenue"]))
    c2.metric("Expenses", money(summary["total_expense"]))
    c3.metric("Net profit", money(summary["net_profit"]))
    c4.metric("Margin", pct(summary["profit_margin_pct"]))
    st.caption(summary["expense_allocation_note"])

    breakdown = pd.DataFrame(summary["breakdown"])
    if not breakdown.empty:
        st.plotly_chart(px.bar(breakdown, x="category", y="total", color="type", title="Business totals by category"), use_container_width=True)
        st.dataframe(breakdown, use_container_width=True, hide_index=True)

    if role == "coach":
        st.info("Coach view shows totals and margins only. Individual ledger entries are hidden.")
        return

    st.subheader("Add business entry")
    with st.form("business_form"):
        col1, col2 = st.columns([1, 2])
        b_date = col1.date_input("Entry date", value=date.today()).strftime("%Y-%m-%d")
        desc = col2.text_input("Entry description")
        category = st.selectbox("Category", list(BUSINESS_CATEGORIES.keys()))
        amount = st.number_input("Amount", min_value=0.0, step=1.0)
        if st.form_submit_button("Add entry") and desc.strip():
            add_business_entry(b_date, desc, category, amount)
            st.success("Entry added.")
            st.rerun()

    entries = pd.DataFrame(get_ledger_entries(month, role="admin"))
    st.subheader("Ledger entries")
    if entries.empty:
        st.caption("No business entries yet.")
    else:
        st.dataframe(entries, use_container_width=True, hide_index=True)
        with st.expander("Delete ledger entry"):
            entry_id = st.number_input("Entry ID", min_value=1, step=1)
            if st.button("Delete selected entry"):
                delete_business_entry(int(entry_id))
                st.rerun()


def render_settings(month: str) -> None:
    st.header("Settings")
    st.write(f"Database path: `{DB_PATH}`")
    st.write("Use Docker or a hosted deployment with a mounted persistent volume to keep this app independent of a single machine.")
    with st.expander("Rule-based categorization preview"):
        sample = st.text_input("Transaction description", "Walmart grocery purchase")
        st.write(local_llm_categorize_transaction(sample))


def main() -> None:
    init_db()
    if not login_form():
        return
    user = current_user() or {}
    role = user.get("role", "coach")
    st.sidebar.title(APP_NAME)
    st.sidebar.caption(f"Signed in as {user.get('username')} ({role})")
    month = month_picker()
    pages = ["Budget", "Business Ledger"]
    if role == "admin":
        pages.extend(["CSV Import", "Settings"])
    page = st.sidebar.radio("Navigation", pages)
    logout_button()

    if page == "Budget":
        render_budget(month, role)
    elif page == "Business Ledger":
        render_business(month, role)
    elif page == "CSV Import" and require_role("admin"):
        render_import(month)
    elif page == "Settings" and require_role("admin"):
        render_settings(month)
    else:
        st.error("Access denied.")


if __name__ == "__main__":
    main()
