@echo off
title Job Application Agent
echo ==========================================
echo   Job Application Agent - Local Server
echo ==========================================
echo.

cd /d "%~dp0"

echo [1/2] Starting Cloudflare Tunnel...
start "Cloudflare Tunnel" cmd /c "cloudflared tunnel run job-agent-api"
timeout /t 2 /nobreak >nul

echo [2/2] Starting FastAPI backend on http://127.0.0.1:8000 ...
echo.
echo   Dashboard: https://www.h4s.live
echo   Health:    http://127.0.0.1:8000/health
echo.
echo   Close this window to stop the server.
echo ==========================================
echo.
.venv\Scripts\python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
