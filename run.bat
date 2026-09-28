@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Please run install.bat first.
    echo.
    pause
    exit /b 1
)

.venv\Scripts\python.exe ripper.py

pause