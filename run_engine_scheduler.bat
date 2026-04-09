@echo off
REM ================================================================
REM  Job Application Engine — Windows Task Scheduler launcher
REM  Uses this folder as project root (%~dp0). Edit .env for API auth.
REM ================================================================

SET "PROJECT_DIR=%~dp0"
IF "%PROJECT_DIR:~-1%"=="\" SET "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

SET "PYTHON=%PROJECT_DIR%\.venv\Scripts\python.exe"
IF NOT EXIST "%PYTHON%" SET "PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe"
SET "SCRIPT=%PROJECT_DIR%\scripts\main.py"
SET "LOG_DIR=%PROJECT_DIR%\logs"

IF NOT EXIST "%LOG_DIR%" MKDIR "%LOG_DIR%"

FOR /F "usebackq" %%T IN (`powershell -NoProfile -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"`) DO SET "DT=%%T"
SET "LOG_FILE=%LOG_DIR%\scheduled_run_%DT%.log"

cd /d "%PROJECT_DIR%"
IF NOT EXIST "%PYTHON%" (
    echo ERROR: Python not found. Create venv: python -m venv venv  ^&^& venv\Scripts\pip install -r requirements.txt
    echo ERROR: Python not found. >> "%LOG_FILE%"
    exit /b 1
)

echo ============================================================ >> "%LOG_FILE%"
echo  JOB ENGINE START: %DATE% %TIME% >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

"%PYTHON%" "%SCRIPT%" >> "%LOG_FILE%" 2>&1
SET "EC=%ERRORLEVEL%"

echo ============================================================ >> "%LOG_FILE%"
echo  JOB ENGINE END: %DATE% %TIME%  ExitCode=%EC% >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

exit /b %EC%
