@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create a virtual environment first: py -3.13 -m venv .venv
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt || exit /b 1
".venv\Scripts\python.exe" manage.py migrate || exit /b 1
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
