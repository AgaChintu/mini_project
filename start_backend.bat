@echo off
title ClariQ Backend Server
echo ===================================================
echo Starting ClariQ FastAPI Backend (Supabase Connected)
echo ===================================================
cd /d "%~dp0backend-python"
if not exist ".venv\Scripts\activate.bat" (
    echo Error: Virtual environment .venv not found!
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
echo Starting Uvicorn on http://127.0.0.1:8000...
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
