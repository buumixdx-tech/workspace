#!/bin/bash
# run.sh — 一行 feishu_preprocess 管道
#
# preprocess 用 dashscope (qwen3.5-flash), lightrag 用 deepseek+dashscope.
# 两个 LLM key 是一张. 这里只从 run_lr.sh 拿 dashscope embedding key,
# 不用 deepseek (lightrag 独立 env + 独立进程).
#
# 2026-06-20 加 flock 锁: 防止 cron 5min 触发时上一次还没跑完
# (manual / webui / cron 都走这同一把锁)

set -e
cd "$(dirname "$0")"

LOCKFILE=/var/lock/rag_preprocess.lock
CRON_LOG=/var/log/rag_preprocess_cron.log
RUN_LOG=/var/log/rag_preprocess.log

# 取非阻塞锁 — 拿不到说明上次还在跑, 直接退出
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "[$(date '+%F %T')] skipped: another run in progress (lock=$LOCKFILE)" >> "$CRON_LOG"
    exit 0
fi

# 取 EMBEDDING_BINDING_API_KEY (= dashscope key), 在当前 shell 赋值
eval "$(grep -E '^export EMBEDDING_BINDING_API_KEY=' /root/run_lr.sh)"
export DASHSCOPE_API_KEY="$EMBEDDING_BINDING_API_KEY"

# 主管道 — tee 写主 log
echo "[$(date '+%F %T')] start (pid=$$)" >> "$CRON_LOG"
.venv/bin/python rag_preprocess.py 2>&1 | tee -a "$RUN_LOG"
echo "[$(date '+%F %T')] done" >> "$CRON_LOG"
