@echo off
cd /d "%~dp0"
set PY=python
%PY% -m pip install -r requirements.txt --quiet
%PY% -m uvicorn app:app --host 0.0.0.0 --port 8010
