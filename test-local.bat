@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [ERROR] Python environment missing. Follow the README quick start first.
  goto :fail
)

echo.
echo [1/3] Django configuration check
"%PY%" manage.py check
if errorlevel 1 goto :fail

echo.
echo [2/3] Detect missing model migrations
"%PY%" manage.py makemigrations --check --dry-run
if errorlevel 1 goto :fail

echo.
echo [3/3] Run complete Django test suite
"%PY%" manage.py test --noinput
if errorlevel 1 goto :fail

echo.
echo [PASS] All checks and tests completed successfully.
pause
exit /b 0

:fail
echo.
echo [FAIL] A check failed. Review the error messages above.
pause
exit /b 1
