@echo off
setlocal
cd /d "%~dp0"
title DocuGen - AI Document Studio

rem ---- find Python ----
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY ( where py >nul 2>nul && set "PY=py" )
if not defined PY (
  echo Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer, then run this file again.
  pause
  exit /b 1
)

rem ---- create the virtual environment on first run ----
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 ( echo Could not create the virtual environment. & pause & exit /b 1 )
)

rem ---- install or update dependencies ----
echo Checking dependencies (first run may take a minute)...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if errorlevel 1 ( echo Dependency installation failed. Check your internet connection. & pause & exit /b 1 )

echo Starting DocuGen... a browser tab will open. Close this window to stop the app.
".venv\Scripts\python.exe" -m streamlit run app.py
pause
