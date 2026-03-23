@echo off
REM ================================================================
REM  Job Application Engine - Windows Task Scheduler Launcher
REM  Runs all ACTIVE + FULLY AUTOMATED sites (KForce, LanceSoft)
REM ================================================================

SET PROJECT_DIR=c:\Users\mahen\OneDrive\Desktop\set_up\project-job-application-engine
SET PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe
SET SCRIPT=%PROJECT_DIR%\scripts\main.py
SET LOG_DIR=%PROJECT_DIR%\data\logs

REM Create log directory if it does not exist
IF NOT EXIST "%LOG_DIR%" MKDIR "%LOG_DIR%"

REM Build timestamped log filename  (YYYYMMDD_HHMM)
FOR /F "tokens=2 delims==" %%I IN ('wmic os get localdatetime /value') DO SET DT=%%I
SET LOG_FILE=%LOG_DIR%\run_%DT:~0,8%_%DT:~8,4%.log

REM ---------------------------------------------------------------
REM Change to project root first (critical: .env is loaded from CWD)
REM ---------------------------------------------------------------
cd /d "%PROJECT_DIR%"

echo ============================================================ >> "%LOG_FILE%"
echo  JOB ENGINE START: %DATE% %TIME%                            >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

echo [INFO] Engine is now starting. Keep this window open...
"%PYTHON%" "%SCRIPT%"

echo ============================================================ >> "%LOG_FILE%"
echo  JOB ENGINE END:   %DATE% %TIME%  ExitCode=%ERRORLEVEL%     >> "%LOG_FILE%"
echo ============================================================ >> "%LOG_FILE%"

echo.
echo [INFO] Press any key to close this window...
pause >nul

exit /b %ERRORLEVEL%
