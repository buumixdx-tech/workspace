@echo off
chcp 65001 >nul
cd /d %~dp0

if not exist .venv (
    echo creating .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo failed to create venv
        pause
        exit /b 1
    )
)

echo installing deps ...
.venv\Scripts\pip.exe install -r requirements.txt -q

echo starting flask ...
.venv\Scripts\python.exe app.py
pause
