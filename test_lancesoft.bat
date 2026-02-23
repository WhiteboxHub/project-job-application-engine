@echo off
cd /d "%~dp0"
echo Testing LanceSoft (Dry Run)...
venv\Scripts\python.exe scripts\test_site.py --site lancesoft
pause
