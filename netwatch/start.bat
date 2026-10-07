@echo off
REM NETWATCH launcher (Windows). One command: installs what is missing, starts backend + UI, opens the browser.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.12+ not found. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause & exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)"
if errorlevel 1 (
  echo Python 3.12 or newer is required. See README.md
  pause & exit /b 1
)

if not exist .venv (
  echo creating Python environment ^(first run only^)...
  python -m venv .venv
)
if not exist .venv\.deps-ok (
  echo installing Python dependencies...
  .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
  .venv\Scripts\python.exe -m pip install --quiet -r backend\requirements.txt
  if errorlevel 1 ( echo dependency installation failed & pause & exit /b 1 )
  echo ok> .venv\.deps-ok
)
if not exist .env if exist .env.example ( copy .env.example .env >nul & echo created .env from .env.example )

if not exist frontend\dist\index.html (
  where npm >nul 2>nul
  if errorlevel 1 ( echo Node.js 20+ is needed once to build the interface: https://nodejs.org/ & pause & exit /b 1 )
  echo building the interface ^(first run only, about 1 minute^)...
  pushd frontend
  call npm install --no-audit --no-fund --silent
  call npm run build --silent
  popd
)

set PORT=8000
start "" cmd /c "timeout /t 4 >nul & start http://127.0.0.1:%PORT%"
echo NETWATCH running on http://127.0.0.1:%PORT%  (close this window to stop)
cd backend
..\.venv\Scripts\python.exe -m app.main %*
