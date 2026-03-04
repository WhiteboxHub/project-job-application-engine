@echo off
title Run Hiring Cafe Pipeline
echo Triggering the pipeline manually...
cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo.
echo Running run_hiring_cafe_pipeline.py...
python run_hiring_cafe_pipeline.py

echo.
echo Pipeline execution finished.
pause
