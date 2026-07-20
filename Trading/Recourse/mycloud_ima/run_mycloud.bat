@echo off
REM mycloud_preprocess startup script (Windows)
REM
REM Usage:
REM   .\run_mycloud.bat                                Normal run (single batch 50k chars)
REM   set FEISHU_PREPROCESS_DRY_RUN_LIGHTRAG=1 ^& .\run_mycloud.bat   DRY RUN
REM   set FEISHU_PREPROCESS_MAX_TOTAL_CHARS=200000 ^& .\run_mycloud.bat  Big batch
REM
REM Decisions (2026-06-22 buumi):
REM   1. Reuse feishu historical.md prompt
REM   2. Don't sync images/files
REM   3. Don't write back to mycloud.db
REM   4. No cron, manual trigger only
REM   5. lightrag file_source prefix "my"
REM   6. Single batch max 50000 chars
REM   7. mycloud: ALL info_types POST (no SKIP)
REM
REM Run repeatedly until "no new mycloud records, exit 0"

REM Force UTF-8 for cmd console (fixes Chinese comments)
chcp 65001 >nul 2>&1

setlocal

cd /d "%~dp0"

REM jcloud mycloud_proxy reverse proxy URL (nginx via buumicloud.com.cn/mycloud-api/)
set REMOTE_MYCLOUD_URL=https://buumicloud.com.cn/mycloud-api

REM Basic Auth (shared with /rag/ htpasswd_rag)
set REMOTE_MYCLOUD_USER=buumi
set REMOTE_MYCLOUD_PASS=xdxis1234

REM DashScope API key (single source: D:\workspace\LightRAG\secrets\feishu_preprocess.env)
REM Don't hardcode here. .env has the real value (NOT Googleapikey.txt placeholder)
REM 2026-06-23 09:30 read from .env directly to avoid two-place maintenance
for /f "usebackq tokens=1,2 delims==" %%a in ("D:\workspace\LightRAG\secrets\feishu_preprocess.env") do (
    if /i "%%a"=="DASHSCOPE_API_KEY" set "DASHSCOPE_API_KEY=%%b"
)

REM lightrag same-host
set LIGHTRAG_URL=http://127.0.0.1:9621

REM prompt mode (historical = feishu default, matches stock/industry themes)
set FEISHU_PREPROCESS_MODE=historical

REM Default 50k chars (decision #6), override via env for big batch
REM set FEISHU_PREPROCESS_MAX_TOTAL_CHARS=200000

if "%FEISHU_PREPROCESS_DRY_RUN_LIGHTRAG%"=="1" (
    echo [run_mycloud] DRY RUN mode - no real POST to lightrag
) else (
    echo [run_mycloud] REAL POST mode
)

python mycloud_preprocess.py %*

endlocal
