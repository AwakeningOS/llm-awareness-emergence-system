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
echo (Press Ctrl+C in this window to stop properly)
echo.

python -m awareness_ui

echo.
echo ========================================
echo  Cleaning up...
echo ========================================

REM Kill any remaining Python processes on Gradio ports
for %%p in (7860 7861 7862 7863) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:%%p" ^| findstr "LISTENING"') do (
        tasklist /FI "PID eq %%a" | findstr /i "python" >nul
        if not errorlevel 1 (
            echo Killing zombie process on port %%p (PID %%a)
            taskkill /F /PID %%a >nul 2>&1
        )
    )
)

echo Done. All ports released.
pause
