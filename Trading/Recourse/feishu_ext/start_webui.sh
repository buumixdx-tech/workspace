#!/bin/bash
# start_webui.sh — 启动 feishu_preprocess 控制台
#
# 用法: /root/rag_preprocess/start_webui.sh
# 默认端口 8080, 可用 WEBUI_PORT 环境变量覆盖
set -e
cd /root/rag_preprocess

export WEBUI_PORT="${WEBUI_PORT:-8080}"

nohup .venv/bin/python web_ui.py > /var/log/rag_preprocess_webui.log 2>&1 &
disown
sleep 1
ps -ef | grep web_ui.py | grep -v grep
echo "listening on :${WEBUI_PORT}"
