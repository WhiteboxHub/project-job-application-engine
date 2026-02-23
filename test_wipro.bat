@echo off
cd /d "%~dp0"
echo Testing Wipro (Dry Run)...
venv\Scripts\python.exe scripts\test_site.py --site wipro
pause
