@echo off
cd /d "%~dp0"
python -m openeuv_abbe
if errorlevel 1 pause
