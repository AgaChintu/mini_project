@echo off
title ClariQ Frontend Server
echo ===================================================
echo Starting ClariQ Frontend Server on port 5500
echo ===================================================
cd /d "%~dp0frontend"
echo Open your browser at: http://127.0.0.1:5500/student-pages/login.html
echo.
python -m http.server 5500
pause
