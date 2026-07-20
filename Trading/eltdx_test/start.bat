@echo off
chcp 65001 >nul
cd /d %~dp0

REM 一键启动 eltdx_test Web 服务

if not exist .venv (
    echo [start] 创建虚拟环境 .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [start] 虚拟环境创建失败
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

echo [start] 安装依赖 ...
pip install -r requirements.txt -q

echo [start] 启动 Flask ...
python app.py
pause