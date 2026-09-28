@echo off
cd /d "%~dp0"

echo ========================================
echo FlashbackRipper - Installation
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    python -m venv .venv

    if errorlevel 1 (
        echo.
        echo ERROR: Could not create virtual environment.
        echo Make sure Python is installed and available as "python".
        pause
        exit /b 1
    )
)

echo.
echo Installing requirements...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Installation complete!
echo ========================================
echo.
pause