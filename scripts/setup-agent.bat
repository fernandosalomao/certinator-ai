@echo off
REM Navigate to the maf directory
cd /d "%~dp0\..\maf" || exit /b 1

REM Install dependencies and create virtual environment using uv
uv sync 