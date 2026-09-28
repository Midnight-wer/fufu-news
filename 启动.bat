@echo off
title fufu-news Launcher
cd /d "%~dp0"

echo ==================================
echo   Checking environment...
echo ==================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)

echo [OK] Environment check passed.
echo.
echo Launching fufu news...
echo.

python launch.py

pause > nul
