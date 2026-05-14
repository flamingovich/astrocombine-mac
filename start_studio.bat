@echo off
setlocal

cd /d "%~dp0"

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm not found. Install Node.js first.
  pause
  exit /b 1
)

if not exist "node_modules" (
  echo [INFO] Installing npm dependencies...
  npm install
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
  )
)

echo [INFO] Starting Politics Studio...
npm run dev

if errorlevel 1 (
  echo [ERROR] Application exited with an error.
  pause
  exit /b 1
)

endlocal
