# FinVault

FinVault is a local-first personal finance app built with Streamlit, Python, SQLite, Pandas, and Plotly.

The app is designed to run independently from one computer. It can run locally, inside Docker, or on a hosted service that provides persistent storage.

## Core features

- Zero-based monthly budgeting
- CSV bank statement import
- Rule-based local transaction categorization
- Business ledger for side ventures
- Profit and margin summaries
- Admin and coach views
- Coach-safe aggregate reporting
- SQLite local data storage
- Environment-based database path configuration
- Docker and Docker Compose deployment
- Verification script for basic health checks

## Privacy model

The app does not use external AI services, cloud categorization, telemetry, or analytics.

Coach access is restricted to aggregate summaries. Coach views are designed to avoid raw transaction rows, merchant details, account identifiers, and CSV import tools.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python verify_app.py
streamlit run app.py
```

## Run with Docker

```bash
docker compose up --build
```

Then open:

```text
http://localhost:8501
```

Docker Compose stores the SQLite database in a named volume called `finance_app_data`. That keeps the database outside the project folder and makes the app easier to move between machines or servers.

## Environment variables

```text
FINANCE_APP_NAME=FinVault
FINANCE_APP_DATA_DIR=/data
FINANCE_APP_DB_PATH=/data/finance_data.db
FINANCE_APP_DEMO_MODE=true
FINANCE_APP_ALLOW_SIGNUP=false
```

## Deployment notes

For real use, deploy somewhere with persistent disk support. SQLite needs a stable file path. If a platform wipes the filesystem on redeploy, the finance database will be lost.

Good deployment targets include:

1. Docker Compose on a VPS
2. Render with a persistent disk
3. Fly.io with a mounted volume
4. Railway with persistent storage

Streamlit Community Cloud is useful for demos, but it is not the best target for private financial data or durable SQLite storage.

## CSV formats supported

The importer supports these common formats:

```text
Date, Description, Amount
Date, Description, Debit, Credit
Posted Date, Payee, Withdrawal, Deposit
```

The cleaner handles dollar signs, commas, blank cells, and parentheses such as `($45.20)`.

## Local categorization

`local_llm_categorize_transaction(description)` currently uses local rules. It is structured so a local Ollama or llama.cpp call can be added later without sending financial data to a commercial cloud API.

## Verification

Run:

```bash
python verify_app.py
```

The script checks imports, database initialization, required tables, local access validation, zero-based budget math, CSV parsing, coach privacy behavior, and business margin calculations.

## Security reminder

This app is private by design, but the database file still needs to be protected. Do not commit database files, environment files, or Streamlit secrets. Change the generated demo access values before using real financial data.
