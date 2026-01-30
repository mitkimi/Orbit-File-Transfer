@echo off
echo Building Orbit File Transfer application...

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Run the build script
python build_app.py

echo.
echo Build process completed!
echo.
pause