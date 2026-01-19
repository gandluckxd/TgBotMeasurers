# Google Sheets Exporter

This folder contains a standalone exporter for Google Sheets. It reads measurements from the bot SQLite DB and enriches rows with Altawin data by order code (Unique_code).

## Setup
1) Create/update `.env` in this folder (see the existing file for required variables).
2) Place `credentials.json` (Google service account) in this folder or update `GOOGLE_CREDENTIALS_FILE`.
3) Ensure Altawin Firebird DB is reachable from this machine.

## Run
```
venv\Scripts\python.exe sheets_exporter.py
```

## Notes
- Reads from `DATABASE_URL` (defaults to the bot SQLite DB path).
- Altawin fields are fetched by `altawin_order_code` with fallback to legacy fields when code is missing or not found.
