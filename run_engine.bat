@echo off
cd /d "%~dp0"

:: Activate the virtual environment
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
) else (
    echo [WARNING] venv not found. Using system Python.
)

:: Run the engine
echo Starting Job Application Engine...
python scripts\main.py

:: Keep the window open if not run from a scheduler specifically
pause
