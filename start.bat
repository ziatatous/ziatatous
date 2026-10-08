@echo off
REM Lance ASFALTO sous Windows
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
start "" http://127.0.0.1:8000
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
