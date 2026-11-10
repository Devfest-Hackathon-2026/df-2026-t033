@echo off
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
  if errorlevel 1 (
    echo Python environment could not be created.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install backend dependencies.
  pause
  exit /b 1
)
echo Backend URL: http://localhost:8000/api/health
".venv\Scripts\python.exe" -m uvicorn main:app --reload --port 8000
pause
