@echo off
title Job Engine Scheduler
echo Starting the Job Engine Automatic Scheduler...
cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo.
echo Running scheduler.py...
python scheduler.py

pause
