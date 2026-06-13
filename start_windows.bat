@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (
  echo Python 3.10+ is required.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" python -m venv .venv
".venv\Scripts\python.exe" -m pip install -r requirements-api.txt

where npm >nul 2>nul || (
  echo Node.js 18+ is required to build the frontend.
  pause
  exit /b 1
)

pushd frontend
call npm install
call npm run build
popd

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process 'http://127.0.0.1:8000'"
".venv\Scripts\python.exe" -m uvicorn api_server:app --host 0.0.0.0 --port 8000
