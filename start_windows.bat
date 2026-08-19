@echo off
chcp 65001 >nul
cd /d %~dp0
if not exist .venv (
  echo Tworze srodowisko Python...
  py -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
if "%LIVE_TENNIS_API_KEY%"=="" (
  echo.
  echo Brak LIVE_TENNIS_API_KEY - uruchamiam tryb reczny.
  echo Aby miec dzisiejsze mecze automatycznie, ustaw darmowy klucz Live Tennis API.
  echo.
)
python backend\update.py
if errorlevel 1 pause & exit /b 1
start "" http://localhost:8080
python -m http.server 8080 -d frontend
