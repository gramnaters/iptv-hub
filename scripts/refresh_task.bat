@echo off
cd /d "%~dp0.."
if not exist logs mkdir logs
python scripts\refresh.py >> logs\task.log 2>&1
