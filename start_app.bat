@echo off
title Saheli Kurti Trend Intelligence Platform
cd /d "%~dp0\kurti_trend_platform"

echo ======================================================================
echo       SAHELI KURTI TREND INTELLIGENCE PLATFORM (LOCAL LAUNCHER)
echo ======================================================================
echo.
echo Launching Saheli Kurti Trend Intelligence Web Dashboard...
echo.

start "" "http://localhost:8501"

python run.py

pause
