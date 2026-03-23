@echo off
REM ================================================================
REM  Job Application Engine - Windows Task Scheduler Launcher
REM ================================================================

SET PROJECT_DIR=C:\Users\remot\Desktop\automation\project-job-application-engine
SET PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe
SET SCRIPT=%PROJECT_DIR%\scripts\main.py
SET LOG_DIR=%PROJECT_DIR%\logs

REM Create log directory if it does not exist
IF NOT EXIST "%LOG_DIR%" MKDIR "%LOG_DIR%"

REM Get timestamp using PowerShell (wmic removed in Windows 11)
FOR /F "usebackq" %%T IN (`powershell -NoProfile -Command "Get-Date -Format 'yyyyMMdd_HHmm'"`) DO SET DT=%%T
SET LOG_FILE=%LOG_DIR%\run_%DT%.log

REM Change to project root (critical: .env is loaded from CWD)
cd /d "%PROJECT_DIR%"

echo ============================================================ >> "%LOG_FILE%"
echo  JOB ENGINE START: %DATE% %TIME% >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

"%PYTHON%" "%SCRIPT%" >> "%LOG_FILE%" 2>&1

echo ============================================================ >> "%LOG_FILE%"
echo  JOB ENGINE END: %DATE% %TIME%  ExitCode=%ERRORLEVEL% >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

exit /b %ERRORLEVEL%
