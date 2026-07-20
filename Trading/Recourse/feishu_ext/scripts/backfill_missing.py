#!/usr/bin/env python3
"""一次性补处理 missing extracted（251条 ts < 13:18:56 的老文字消息）。

用法:
    python backfill_missing.py              # 预览模式
    python backfill_missing.py --apply     # 正式处理
"""
from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys
import time
from pathlib import Path

# 让脚本可以直接 python 跑
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from openai import OpenAI
from prompts.schemas import LLMInput, InputItem
from prompts.loader import load_prompt
from feishu_db_writer import ensure_schema, upsert_extracted

TZ = datetime.timezone(datetime.timedelta(hours=8))
DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODE = "historical"
MAX_TOTAL_CHARS = 50000  # 同 feishu_preprocess.py
MAX_ITEMS_PER_BATCH = 50  # 每批最多50条，防止 prompt token 膨胀
DB_PATH = HERE / "data" / "preprocess.db"


def call_llm(batch, mode):
    """调 qwen3.5-flash，返回 (out, usage)."""
    payload_items = [
        InputItem(idx=i+1, ts=ts, text=text, orig_len=len(text))
        for i, (_msg_id, ts, text) in enumerate(batch)
    ]
    input_payload = LLMInput(count=len(payload_items), items=payload_items)
    system, user, fm = load_prompt(mode, input_payload)
    key = os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError("DASHSCOPE_API_KEY not set")
    client = OpenAI(api_key=key, base_url=DASHSCOPE_BASE)
    # retry logic
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=fm["model"],
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.01,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            out_dict = __import__("json").loads(raw)
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
            }
            from prompts.schemas import LLMOutput
            out = LLMOutput.model_validate(out_dict)
            return out, {**usage, "raw_content": raw}
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def main():
    parser = argparse.ArgumentParser(description="补处理 missing extracted 消息")
    parser.add_argument("--apply", action="store_true", help="正式处理（不加则预览）")
    args = parser.parse_args()

    if not os.environ.get("DASHSCOPE_API_KEY"):
        print("ERROR: DASHSCOPE_API_KEY not set")
        return 1

    con = sqlite3.connect(str(DB_PATH))
    con.execute("PRAGMA busy_timeout = 5000")
    ensure_schema(con)

    # 找出所有 missing
    rows = con.execute("""
        SELECT m.id, m.ts, m.content
        FROM messages m
        LEFT JOIN extracted e ON m.id = e.msg_id
        WHERE e.msg_id IS NULL AND m.kind = 't' AND m.id <= 51965
        ORDER BY m.id ASC
    """).fetchall()
    con.close()

    print(f"共 {len(rows)} 条待处理")

    # 分批（按字符数 + 每批条数上限）
    batches = []
    current_batch = []
    current_chars = 0
    for row in rows:
        if (current_chars + len(row[2]) > MAX_TOTAL_CHARS or len(current_batch) >= MAX_ITEMS_PER_BATCH) and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_chars = 0
        current_batch.append(row)
        current_chars += len(row[2])
    if current_batch:
        batches.append(current_batch)

    print(f"分为 {len(batches)} 批")
    for i, b in enumerate(batches, 1):
        print(f"  批{i}: {len(b)} 条, ~{sum(len(r[2]) for r in b):,} 字符")

    if not args.apply:
        print("\n预览模式，加 --apply 正式处理")
        return 0

    # 正式处理
    con = sqlite3.connect(str(DB_PATH))
    con.execute("PRAGMA busy_timeout = 5000")
    ensure_schema(con)

    total_written = 0
    for batch_i, batch in enumerate(batches, 1):
        print(f"\n处理批 {batch_i}/{len(batches)} ({len(batch)} 条) …", end=" ", flush=True)
        try:
            out, usage = call_llm(batch, MODE)
        except Exception as e:
            print(f"LLM 错误: {e}")
            continue

        # task_id 1-to-1 mapping
        by_task = {r.task_id: r for r in out.results}
        aligned = [
            (msg_id, ts, text, by_task[i+1])
            for i, (msg_id, ts, text) in enumerate(batch)
            if (i+1) in by_task
        ]

        for msg_id, ts, _text, result in aligned:
            upsert_extracted(con, msg_id=msg_id, ts=ts, result=result)
        con.commit()
        print(f"写入 {len(aligned)} 行")
        total_written += len(aligned)
        time.sleep(0.5)

    con.close()
    print(f"\n完成，共写入 {total_written} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
