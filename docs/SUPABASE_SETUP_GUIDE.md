# ClariQ — Supabase Setup & Execution Guide (Windows PowerShell)

This guide details how to configure Supabase PostgreSQL, set up the dedicated Python environment, run Alembic migrations, execute the idempotent database seeder, and launch the FastAPI server on Windows PowerShell.

---

## 1. Environment & Prerequisites

- **OS:** Windows 10/11
- **PowerShell:** Windows PowerShell 5.1 or 7+
- **Python:** 3.11+
- **Supabase Project:** `https://xkxpptzhirajzjntkrlb.supabase.co`

---

## 2. Dedicated Virtual Environment (`.venv`)

Activate the dedicated `.venv` in `backend-python/`:

```powershell
cd C:\Users\agarw\Downloads\Unnati_Anu\ClariQ\backend-python
.\.venv\Scripts\Activate.ps1
```

*(If you ever need to reinstall dependencies into `.venv`)*:
```powershell
.\.venv\Scripts\pip.exe install -r requirements.txt
```

---

## 3. Environment Variables Configuration

Copy `.env.example` to `.env` if not already created:

```powershell
Copy-Item .env.example .env
```

Open `.env` and configure your credentials:

```ini
APP_ENV=development

# Supabase Project Credentials
SUPABASE_URL=https://xkxpptzhirajzjntkrlb.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_VQNuPCj6EPq6BcaGMu3fvg_jIj-9RvJ
SUPABASE_SECRET_KEY=YOUR_ROTATED_SUPABASE_SERVICE_ROLE_KEY
SUPABASE_JWKS_URL=https://xkxpptzhirajzjntkrlb.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_STORAGE_BUCKET=clariq-attachments

# Supabase PostgreSQL Connection String (Direct or Session Pooler)
# Format: postgresql+psycopg://postgres:[YOUR-PASSWORD]@db.xkxpptzhirajzjntkrlb.supabase.co:5432/postgres
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@db.xkxpptzhirajzjntkrlb.supabase.co:5432/postgres

# ClariQ Application JWT Secret
JWT_SECRET_KEY=clariq-development-secret-change-this
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

---

## 4. Database Migrations (Alembic)

Verify migration head with psycopg 3:

```powershell
.\.venv\Scripts\alembic.exe -c alembic.ini heads
```

Apply migrations to Supabase PostgreSQL:

```powershell
.\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
```

---

## 5. Seed Data Execution & Verification

Run the idempotent database seeder:

```powershell
.\.venv\Scripts\python.exe seed_data.py
```

Verify that all tables, foreign keys, and records exist in Supabase:

```powershell
.\.venv\Scripts\python.exe seed_data.py --verify
```

---

## 6. Running the Automated Test Suite

Execute the 28 automated tests covering models, APIs, Supabase Storage, and migration dependencies:

```powershell
.\.venv\Scripts\pytest.exe -v
```

---

## 7. Starting the FastAPI Backend

Launch the Uvicorn development server:

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive Documentation:
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health Endpoint: `http://127.0.0.1:8000/api/health`
- Database Health Check: `http://127.0.0.1:8000/api/health/database`
