@echo off
REM Navigate to the maf directory
cd /d %~dp0\..\maf

REM Run the maf using uv
uv run src/main.py 