@echo off
cd /d "%~dp0"
echo Testing KForce (Dry Run)...
venv\Scripts\python.exe scripts\test_site.py --site kforce
pause
