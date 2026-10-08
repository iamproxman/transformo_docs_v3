@echo off
cd /d "%~dp0"
echo ========================================================
echo  Starting TransformoDocs Server with Virtual Environment
echo ========================================================
".venv\Scripts\uvicorn.exe" app.main:app --reload --host 127.0.0.1 --port 8000
pause
