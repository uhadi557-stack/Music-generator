@echo off
title AI Urdu & Pashto Song Generator
echo ========================================================
echo Starting AI Urdu & Pashto Song Generator (Suroor AI)
echo ========================================================
echo.

echo [1/2] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "Song Generator Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\activate.bat && python run_backend.py"

echo [2/2] Starting React Vite Frontend on http://localhost:5173 ...
start "Song Generator Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

timeout /t 3 >nul
start http://localhost:5173
echo System running! Check the opened browser window.
