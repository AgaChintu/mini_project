# ClariQ — MySQL to Supabase PostgreSQL Migration Guide

This document outlines the procedure to safely transfer data from a local MySQL database to Supabase PostgreSQL using `scripts/migrate_mysql_to_supabase.py`.

---

## 1. Migration Overview & Rules

- **Zero Data Loss:** Source records in MySQL are read-only; no drops, truncations, or deletions occur in MySQL.
- **Dependency-Ordered Processing:** 24 tables are processed in foreign-key dependency order (from `academic_years` down to `session_doubts`).
- **Idempotency:** Safe to run repeatedly; existing primary keys in Supabase PostgreSQL are detected and skipped without failure.
- **Sequence Synchronization:** Resets PostgreSQL `SERIAL` sequences after migration so subsequent application inserts do not conflict.

---

## 2. Pre-Migration Checklist

1. **Verify MySQL Running:** Ensure local MySQL service `MySQL80` is running on port 3306 (`Start-Service MySQL80`).
2. **Verify Supabase Database:** Ensure tables exist in Supabase PostgreSQL by running `alembic upgrade head`.
3. **Environment Setup:** Set `DATABASE_URL` in `backend-python/.env` pointing to Supabase PostgreSQL.

---

## 3. Execution Commands

### Step A: Dry Run (Simulation)
```powershell
cd C:\Users\agarw\Downloads\Unnati_Anu\ClariQ
.\backend-python\.venv\Scripts\python.exe scripts/migrate_mysql_to_supabase.py --dry-run
```

### Step B: Live Migration
```powershell
.\backend-python\.venv\Scripts\python.exe scripts/migrate_mysql_to_supabase.py
```

### Step C: Post-Migration Verification
```powershell
.\backend-python\.venv\Scripts\python.exe backend-python/seed_data.py --verify
```

---

## 4. Rollback & Troubleshooting

- If a table insert fails, the error is logged with the row ID and processing continues for remaining rows.
- If MySQL is stopped, the migration script outputs a clean `[MIGRATION BLOCKED]` status without crashing.
