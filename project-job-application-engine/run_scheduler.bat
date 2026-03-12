@echo off
:: ============================================================
:: LanceSoft Job Application Scheduler
:: Triggered by Windows Task Scheduler
:: ============================================================

:: Force UTF-8 encoding (fixes emoji/unicode in log files)
chcp 65001 > nul

cd /d "c:\Users\mahen\OneDrive\Desktop\find\project-job-application-engine"

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Run the scheduler
python scripts\scheduler_worker.py >> logs\scheduler_task.log 2>&1

:: Deactivate
deactivate
