@echo off
echo ========================================
echo  LLM Awareness Emergence System
echo ========================================
echo.

cd /d %~dp0

echo Checking Python...
python --version
if errorlevel 1 (
    echo Python is not installed or not in PATH!
    pause
    exit /b 1
)

echo.
echo Starting Awareness UI...
echo.

python -m awareness_ui

pause
