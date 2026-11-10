@echo off
cd /d "%~dp0frontend"
if not exist "node_modules" (
  call npm install
  if errorlevel 1 (
    echo Failed to install frontend dependencies.
    pause
    exit /b 1
  )
)
echo Frontend URL: http://localhost:5173
call npm run dev
pause
