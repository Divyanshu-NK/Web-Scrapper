@echo off
title Saheli Kurti Trend Intelligence Platform
cd /d "%~dp0"

echo ======================================================================
echo       SAHELI KURTI TREND INTELLIGENCE PLATFORM (LOCAL LAUNCHER)
echo ======================================================================
echo.
echo Starting FastAPI Backend (Port 8000) & Streamlit Dashboard (Port 8501)...
echo.

start "" "http://localhost:8501"

python run.py

pause
