@echo off
cd /d "%~dp0"

:: Activate the virtual environment
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
) else (
    echo [WARNING] venv not found. Using system Python.
)

:: Run the engine — output is logged to logs\scheduler_run.log
echo Starting Job Application Engine...
python scripts\main.py >> "logs\scheduler_run.log" 2>&1
