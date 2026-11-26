# ClariQ — Part 1: Windows Setup & Verification Guide

This guide provides end-to-end instructions for configuring the Python environment, MySQL database, running database migrations, executing idempotent seeds, and launching the ClariQ backend service on Windows PowerShell.

> [!TIP]
> All backend dependencies and executables are installed in an **isolated virtual environment** (`backend-python\.venv`) so your system-level Python environment remains completely untouched and safe.

---

## 1. Prerequisites

- **Operating System:** Windows 10/11
- **Shell:** Windows PowerShell 5.1+ or PowerShell 7+
- **Python:** Python 3.11+
- **Database:** MySQL Server 8.0+ (Installed at `C:\Program Files\MySQL\MySQL Server 8.0`)

---

## 2. Dedicated Virtual Environment (`.venv`)

Navigate to `backend-python`:

```powershell
cd C:\Users\agarw\Downloads\Unnati_Anu\ClariQ\backend-python
```

Activate the dedicated virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

*(If you ever need to recreate it from scratch)*:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt alembic pytest httpx httpx2
```

---

## 3. MySQL Server Configuration

### Step A: Verify or Start the MySQL 8.0 Service
Check if the MySQL service is currently running:

```powershell
Get-Service MySQL80 -ErrorAction SilentlyContinue
```

If the service status is `Stopped`, open an Administrator PowerShell and run:

```powershell
Start-Service MySQL80
# Or:
net start MySQL80
```

### Step B: Create Database
Log into MySQL CLI:

```powershell
mysql -u root -p
```

Create the `clariq` database:

```sql
CREATE DATABASE IF NOT EXISTS clariq
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
EXIT;
```

---

## 4. Environment Configuration

In `backend-python`:

```powershell
Copy-Item .env.example .env
```

Open `.env` in your text editor and fill in your MySQL credentials:

```ini
APP_ENV=development
DB_DRIVER=mysql+pymysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=clariq
DB_USER=root
DB_PASSWORD=YourActualMySQLPasswordHere
SECRET_KEY=generate_a_secure_random_key_using_openssl_rand_hex_32
ACCESS_TOKEN_EXPIRE_MINUTES=60
CORS_ORIGINS=http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:5501,http://localhost:5501,http://127.0.0.1:8000,http://localhost:8000
```

> **Security Note:** `.env` is ignored by `.gitignore`. Never commit actual passwords or JWT secret keys to Git.

---

## 5. Database Migrations (Alembic)

Verify that Alembic can detect migration scripts using the virtual environment:

```powershell
.\.venv\Scripts\alembic.exe -c alembic.ini heads
```

Apply all migrations to create tables, indexes, and constraints:

```powershell
.\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
```

To create future migrations when modifying SQLAlchemy models:

```powershell
.\.venv\Scripts\alembic.exe -c alembic.ini revision --autogenerate -m "describe_change"
.\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
```

---

## 6. Seed Data Execution & Verification

Run the idempotent database seeder:

```powershell
.\.venv\Scripts\python.exe seed_data.py
```

Verify that all tables, foreign keys, and records exist without error:

```powershell
.\.venv\Scripts\python.exe seed_data.py --verify
```

Expected output:
```
==================================================
CLARIQ DATABASE VERIFICATION REPORT
==================================================
  Academic Years:      2
  Semesters:           4
  Sections:            12
  Subjects:            10
  Teachers:            11
  Students:            4
  Teacher Assignments: 11
  Syllabus Units:      5
  Syllabus Topics:     22
  Syllabus Subtopics:  65
==================================================
All integrity checks passed successfully!
```

Demo Accounts:
- **Student:** College ID: `S001` | Password: `student123`
- **Teacher:** College ID: `T001` | Password: `teacher123`

---

## 7. Running the Automated Test Suite

Run pytest inside `.venv`:

```powershell
.\.venv\Scripts\pytest.exe -v
```

Expected result:
```
======================= 20 passed, 3 warnings in 0.86s ========================
```

---

## 8. Starting the FastAPI Server

Launch Uvicorn in development mode from the virtual environment:

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive Documentation:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- System Health: `http://127.0.0.1:8000/api/health`
