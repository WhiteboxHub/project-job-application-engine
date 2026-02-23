@echo off
cd /d "%~dp0"
echo Testing Infosys (Dry Run)...
venv\Scripts\python.exe scripts\test_site.py --site infosys
pause
