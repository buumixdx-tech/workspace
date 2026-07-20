#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过 dashscope Batch API 重写窗口内 v3 旧 summary → v4.

跟 rewrite_summaries_v4.py (实时调用版) 并存, 双模式独立:
  - 实时版: asyncio/单条调, 适合 <500 条小批, 跑得快立刻拿结果
  - 本脚本: dashscope Batch 离线任务, 适合大批量, 半价但要等后台排队

流程 (跟阿里云百炼官方流程一致):
  1. prepare 阶段: 读 db → 生成 jsonl 文件
  2. submit  阶段: 上传文件 → 创建 batch 任务 → 拿到 batch_id
  3. poll    阶段: 轮询 batch 状态 → completed 时拿到 output_file_id
  4. fetch   阶段: 下载结果文件 → 解析每行 → UPSERT 进 db

断点续传: 每阶段会写一份状态文件 {prefix}.state.json, 下一阶段自动 skip 已完成阶段.
  - prepare.jsonl      步骤1产物
  - {prefix}.state     {phase: "prepare"|"submit"|"poll"|"fetch", batch_id?, file_id?, output_file_id?}
  - {prefix}.results.json  最终结果摘要 (机读)

用法:
    # 准备 240 条 jsonl, 不提交 (先看 prompt 对不对)
    python scripts/rewrite_summaries_v4_batch.py --phase prepare --limit 5

    # 准备 + 提交 (前台, 拿到 batch_id 后 ctrl-c 退出, 再用 --phase poll 续轮询)
    python scripts/rewrite_summaries_v4_batch.py --phase submit --limit 5

    # 轮询 + 下载 + 写库
    python scripts/rewrite_summaries_v4_batch.py --phase poll
    python scripts/rewrite_summaries_v4_batch.py --phase fetch

    # 一键跑完 (不写库, 只下结果到 json) — 默认行为, 跟你要的 dry-run 等价
    python scripts/rewrite_summaries_v4_batch.py --phase all --no-db

    # 真实写库
    python scripts/rewrite_summaries_v4_batch.py --phase all

模型: qwen3.5-flash (百炼官方 Batch 支持列表里, 半价)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
APP_DIR = HERE.parent
sys.path.insert(0, str(APP_DIR))

# ---------------------------------------------------------------------- #
# config                                                                  #
# ---------------------------------------------------------------------- #

DB = APP_DIR / "data" / "preprocess.db"
WORK_DIR = APP_DIR / "data" / "batch_v4"
WORK_DIR.mkdir(parents=True, exist_ok=True)

# state 文件是 "什么 run" 的唯一标志. 如果已存在 state, 读里面的 jsonl_path;
# 否则新建一个按 ts 命名的 run.
# 这里只设 STATE_PATH, PREFIX/JSONL_PATH/RESULTS_PATH 在 _resolve_paths() 里动态算.
STATE_PATH = None  # type: ignore[assignment]

TZ = _dt.timezone(_dt.timedelta(hours=8))
DEFAULT_SINCE = _dt.datetime(2026, 6, 29, 15, 0, 0, tzinfo=TZ)
DEFAULT_UNTIL = _dt.datetime(2026, 6, 30, 12, 30, 0, tzinfo=TZ)

# batch 模型: qwen3.5-flash (百炼 Batch 支持列表已确认)
BATCH_MODEL = "qwen3.5-flash"
BATCH_ENDPOINT = "/api/v1/services/aigc/text-generation/generation"
BATCH_COMPLETION_WINDOW = "24h"  # 24 小时内完成, 不急

REWRITE_INFO_TYPES = (1, 2, 3, 6)

POLL_INTERVAL_S = 30
POLL_MAX_WAIT_S = 30 * 60  # 30 分钟超时

# ---------------------------------------------------------------------- #
# DB helpers                                                              #
# ---------------------------------------------------------------------- #


def parse_ts(s: str) -> int:
    dt = _dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
    return int(dt.timestamp() * 1000)


def query_window(con, since_ts: int, until_ts: int, limit: int = 0) -> list[dict]:
    rows = con.execute(
        """
        SELECT m.id, m.ts, m.content, e.summary, e.info_type
        FROM messages m
        JOIN extracted e ON m.id = e.msg_id
        WHERE m.kind = 't' AND length(m.content) > 10
          AND e.info_type IN (1, 2, 3, 6)
          AND m.ts > ? AND m.ts <= ?
        ORDER BY m.ts ASC
        """,
        (since_ts, until_ts),
    ).fetchall()
    cols = ["id", "ts", "content", "summary", "info_type"]
    out = [dict(zip(cols, r)) for r in rows]
    if limit:
        out = out[:limit]
    return out


def upsert_summary(con, msg_id: int, new_summary: str) -> None:
    """UPSERT extracted.summary (跟实时版 upsert_one 一致, 只动 summary)."""
    con.execute(
        "UPDATE extracted SET summary = ? WHERE msg_id = ?",
        (new_summary, msg_id),
    )


# ---------------------------------------------------------------------- #
# phase 1: prepare jsonl                                                   #
# ---------------------------------------------------------------------- #


def phase_prepare(since_ts: int, until_ts: int, limit: int) -> dict:
    jsonl_path, state_path, results_path = _resolve_paths()
    """读 db → 用 v4 prompt 模板 → 生成 jsonl 文件.

    官方 OpenAI 兼容 Batch API 格式 (百炼 batch 文档):
        {
          "custom_id": "msg_<msg_id>",
          "method": "POST",
          "url": "/v1/chat/completions",
          "body": {
            "model": "qwen3.5-flash",
            "messages": [
              {"role": "system", "content": "<v4 system prompt>"},
              {"role": "user", "content": "<user prompt>"}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "enable_thinking": false
          }
        }
    注意: enable_thinking 必须在 body 顶层, 不能放 extra_body.
    """
    from prompts.schemas import LLMInput, InputItem
    from prompts.loader import load_prompt

    placeholder_item = InputItem(idx=1, ts=0, text="PLACEHOLDER", orig_len=10)
    placeholder_payload = LLMInput(count=1, items=[placeholder_item])
    system_template, user_template, fm = load_prompt("historical", placeholder_payload)

    if fm.get("version") != 4:
        print(f"[WARN] prompt version={fm.get('version')}, expected 4 — continue anyway")

    con = sqlite3.connect(str(DB))
    try:
        rows = query_window(con, since_ts, until_ts, limit=limit)
    finally:
        con.close()

    print(f"[prepare] window rows: {len(rows)}")

    n = 0
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for row in rows:
            item = InputItem(idx=1, ts=row["ts"], text=row["content"], orig_len=len(row["content"]))
            payload = LLMInput(count=1, items=[item])
            user_filled = user_template.replace(
                "{{input_json}}",
                json.dumps(payload.model_dump(), ensure_ascii=False, indent=2),
            )
            record = {
                "custom_id": f"msg_{row['id']}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": BATCH_MODEL,
                    "messages": [
                        {"role": "system", "content": system_template},
                        {"role": "user", "content": user_filled},
                    ],
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"},
                    "enable_thinking": False,
                },
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            n += 1

    size_bytes = jsonl_path.stat().st_size
    print(f"[prepare] wrote {n} records to {jsonl_path} ({size_bytes:,} bytes)")
    print(f"[prepare] sample first line (前 300 字):")
    with open(jsonl_path, "r", encoding="utf-8") as f:
        first = f.readline()
        print(f"  {first[:300]}...")

    state = _read_state()
    state["phase"] = "prepare"
    state["jsonl_path"] = str(jsonl_path)
    state["state_path"] = str(state_path)
    state["results_path"] = str(results_path)
    state["record_count"] = n
    state["model"] = BATCH_MODEL
    _write_state(state)
    return state


# ---------------------------------------------------------------------- #
# phase 2: submit                                                          #
# ---------------------------------------------------------------------- #


def phase_submit() -> dict:
    """上传 jsonl → 创建 batch 任务 → 返回 batch_id. 用 OpenAI 兼容 SDK (百炼要求)."""
    state = _read_state()
    if not state.get("jsonl_path") or not Path(state["jsonl_path"]).exists():
        raise SystemExit(f"FAIL: jsonl not found at {state.get('jsonl_path')}, run --phase prepare first")

    api_key = _get_api_key()
    client = _openai_client(api_key)

    print(f"[submit] uploading {state['jsonl_path']} ...")
    with open(state["jsonl_path"], "rb") as f:
        uploaded = client.files.create(file=f, purpose="batch")
    input_file_id = uploaded.id
    print(f"[submit] uploaded, file_id={input_file_id}")

    print(f"[submit] creating batch task (model={BATCH_MODEL}, window={BATCH_COMPLETION_WINDOW}) ...")
    batch = client.batches.create(
        input_file_id=input_file_id,
        endpoint="/v1/chat/completions",
        completion_window=BATCH_COMPLETION_WINDOW,
        metadata={
            "ds_name": "feishu_summary_v4_rewrite",
            "ds_description": f"window {state.get('since')} → {state.get('until')}, model {BATCH_MODEL}",
        },
    )
    batch_id = batch.id
    state["phase"] = "submit"
    state["input_file_id"] = input_file_id
    state["batch_id"] = batch_id
    state["submitted_at"] = _dt.datetime.now(TZ).isoformat(timespec="seconds")
    _write_state(state)

    print(f"[submit] OK, batch_id={batch_id}")
    print(f"[submit] next: python scripts/rewrite_summaries_v4_batch.py --phase poll")
    return state


# ---------------------------------------------------------------------- #
# phase 3: poll                                                            #
# ---------------------------------------------------------------------- #


def phase_poll() -> dict:
    """轮询 batch 状态, completed 时拿 output_file_id."""
    state = _read_state()
    batch_id = state.get("batch_id")
    if not batch_id:
        raise SystemExit("FAIL: no batch_id in state, run --phase submit first")

    api_key = _get_api_key()
    client = _openai_client(api_key)

    started = time.time()
    print(f"[poll] watching batch_id={batch_id} (interval={POLL_INTERVAL_S}s, max={POLL_MAX_WAIT_S}s)")
    while True:
        if time.time() - started > POLL_MAX_WAIT_S:
            raise SystemExit(f"FAIL: poll timeout after {POLL_MAX_WAIT_S}s")

        b = client.batches.retrieve(batch_id)
        status = b.status
        completed = getattr(b.request_counts, "completed", 0)
        total = getattr(b.request_counts, "total", 0)
        print(f"[poll] status={status}  {completed}/{total} done  elapsed={time.time()-started:.0f}s")

        if status == "completed":
            state["output_file_id"] = b.output_file_id
            state["phase"] = "poll"
            state["completed_at"] = _dt.datetime.now(TZ).isoformat(timespec="seconds")
            _write_state(state)
            print(f"[poll] completed, output_file_id={state['output_file_id']}")
            print(f"[poll] next: python scripts/rewrite_summaries_v4_batch.py --phase fetch")
            return state
        elif status in ("failed", "expired", "cancelled"):
            err = getattr(b, "errors", None)
            raise SystemExit(f"FAIL: batch ended with status={status}, errors={err}")

        time.sleep(POLL_INTERVAL_S)


# ---------------------------------------------------------------------- #
# phase 4: fetch + apply                                                   #
# ---------------------------------------------------------------------- #


def phase_fetch(apply_db: bool) -> dict:
    """下载结果文件, 解析每行, 可选 UPSERT 进 db, 出极简 json."""
    import dashscope
    from http import HTTPStatus

    state = _read_state()
    output_file_id = state.get("output_file_id")
    if not output_file_id:
        raise SystemExit("FAIL: no output_file_id, run --phase poll first")

    api_key = _get_api_key()
    dashscope.api_key = api_key

    output_jsonl = jsonl_path.with_suffix(".output.jsonl")
    print(f"[fetch] downloading file_id={output_file_id} to {output_jsonl}")
    client = _openai_client(api_key)
    print(f"[fetch] downloading file_id={output_file_id} to {output_jsonl}")
    file_resp = client.files.content(output_file_id)
    output_jsonl.write_bytes(file_resp.content)
    print(f"[fetch] downloaded, {output_jsonl.stat().st_size:,} bytes")

    # 解析
    items: list[dict] = []
    parse_failures = 0
    with open(output_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                parse_failures += 1
                continue
            custom_id = obj.get("custom_id", "")
            msg_id = int(custom_id.replace("msg_", "")) if custom_id.startswith("msg_") else None
            content = None
            err = None
            try:
                response = obj.get("response", {})
                body = response.get("body", {}) or {}
                choices = body.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
            except Exception as e:
                err = str(e)

            # 解析 LLM 输出的 JSON string → summary
            summary_new = None
            info_type_new = None
            if content:
                try:
                    parsed = json.loads(content)
                    results = parsed.get("results", [])
                    if results:
                        summary_new = results[0].get("summary")
                        info_type_new = results[0].get("info_type")
                except Exception as e:
                    err = f"LLM JSON parse: {e}"

            items.append({
                "msg_id": msg_id,
                "summary_new": summary_new,
                "info_type_new": info_type_new,
                "err": err,
            })

    print(f"[fetch] parsed {len(items)} records, parse_failures={parse_failures}")

    # 关联原 v3 summary + ts
    con = sqlite3.connect(str(DB))
    try:
        for it in items:
            if it["msg_id"]:
                row = con.execute(
                    "SELECT ts, summary, info_type FROM extracted WHERE msg_id=?",
                    (it["msg_id"],),
                ).fetchone()
                if row:
                    it["ts"] = int(row[0])
                    it["summary_old"] = row[1]
                    it["info_type_old"] = int(row[2])
    finally:
        con.close()

    # 写极简 json (items 只含 msg_id/ts/info_type/summary — 跟实时版一致)
    out_items = []
    for it in items:
        out_items.append({
            "msg_id": it.get("msg_id"),
            "ts": it.get("ts"),
            "info_type": it.get("info_type_old") or it.get("info_type_new"),
            "summary_old": it.get("summary_old"),
            "summary_new": it.get("summary_new"),
        })
    result_obj = {
        "mode": "batch",
        "model": BATCH_MODEL,
        "since": state.get("since", ""),
        "until": state.get("until", ""),
        "batch_id": state.get("batch_id"),
        "items": out_items,
    }
    # 共用实时版的极简 json 输出路径 (覆盖), 让 daily_report/scripts_backup 只看一份
    # 实时版会覆盖这个文件. 你想要历史保留就改 out_items 不在这里覆盖, 写到 PREFIX.results.json
    results_path.write_text(json.dumps(result_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[fetch] wrote {results_path} ({results_path.stat().st_size:,} bytes)")

    # UPSERT (apply 模式)
    if apply_db:
        n = 0
        con = sqlite3.connect(str(DB))
        try:
            for it in items:
                if it.get("msg_id") and it.get("summary_new"):
                    upsert_summary(con, it["msg_id"], it["summary_new"])
                    n += 1
            con.commit()
        finally:
            con.close()
        print(f"[fetch] UPSERTed {n} summaries to extracted")
    else:
        print(f"[fetch] DRY mode (--no-db), no DB writes")

    state["phase"] = "fetch"
    state["results_count"] = len(out_items)
    state["results_json"] = str(results_path)
    state["applied"] = apply_db
    _write_state(state)
    return state


# ---------------------------------------------------------------------- #
# state helpers                                                            #
# ---------------------------------------------------------------------- #


def _read_state() -> dict:
    if _state_path().exists():
        return json.loads(_state_path().read_text(encoding="utf-8"))
    return {}


def _write_state(state: dict) -> None:
    _state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _state_path() -> Path:
    """唯一的 state 路径: WORK_DIR/latest.state.json (覆盖式, 代表 "当前这个 run")."""
    return WORK_DIR / "latest.state.json"


def _resolve_paths() -> tuple[Path, Path, Path]:
    """读 state 拿到当前 run 的文件路径. 若 state 不存在, 用 ts 初始化一个新 run."""
    state = _read_state()
    if state.get("jsonl_path"):
        jsonl_path = Path(state["jsonl_path"])
        # 同 stem 的 .state.json / .results.json
        state_path = jsonl_path.with_suffix(".state.json")
        results_path = jsonl_path.with_suffix(".results.json")
        return jsonl_path, state_path, results_path
    # 新 run: 按 ts 命名
    new_prefix = WORK_DIR / _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return (
        new_prefix.with_suffix(".jsonl"),
        new_prefix.with_suffix(".state.json"),
        new_prefix.with_suffix(".results.json"),
    )


def _get_api_key() -> str:
    k = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not k:
        raise SystemExit("FAIL: DASHSCOPE_API_KEY env not set")
    if "\u2026" in k or "..." in k:
        raise SystemExit("FAIL: DASHSCOPE_API_KEY 含 U+2026 (horiz ellipsis) 占位符, 不是真 key")
    return k


def _openai_client(api_key: str):
    """百炼 batch API 走 OpenAI 兼容 SDK (dashscope SDK 没有 batches 模块).
    base_url 是兼容端点 (跟实时 chat completion 一样)."""
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")


# ---------------------------------------------------------------------- #
# main                                                                    #
# ---------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase", default="all",
        choices=["prepare", "submit", "poll", "fetch", "all"],
        help="执行哪一阶段 (default: all)",
    )
    parser.add_argument("--since", default=DEFAULT_SINCE.strftime("%Y-%m-%d %H:%M:%S"))
    parser.add_argument("--until", default=DEFAULT_UNTIL.strftime("%Y-%m-%d %H:%M:%S"))
    parser.add_argument("--limit", type=int, default=0, help="最多处理多少条 (调试)")
    parser.add_argument("--apply", action="store_true", help="fetch 阶段真实 UPSERT 进 db")
    parser.add_argument("--no-db", action="store_true", help="fetch 阶段不下结果到 db (dry-run, 默认)")
    parser.add_argument("--poll-once", action="store_true", help="poll 阶段只查一次就退出, 不循环 (手动用)")
    args = parser.parse_args()

    # apply / no-db 二选一
    if args.apply and args.no_db:
        print("FAIL: --apply 和 --no-db 不能同时给")
        return 2
    apply_db = args.apply
    if not args.apply and not args.no_db:
        # 默认 dry-run
        apply_db = False
        print("[plan] 默认 dry-run 模式 (不写 db), 加 --apply 真实 UPSERT")

    print(f"[plan] phase={args.phase}  since={args.since}  until={args.until}  limit={args.limit or '(all)'}  apply_db={apply_db}")

    since_ts = parse_ts(args.since)
    until_ts = parse_ts(args.until)

    state = _read_state()
    state["since"] = args.since
    state["until"] = args.until
    _write_state(state)

    if args.phase in ("prepare", "all"):
        phase_prepare(since_ts, until_ts, args.limit)
    if args.phase in ("submit", "all"):
        phase_submit()
    if args.phase in ("poll", "all"):
        if args.poll_once:
            # 仅查一次: state 里拿 batch_id, retrieve 后退出
            state = _read_state()
            api_key = _get_api_key()
            client = _openai_client(api_key)
            b = client.batches.retrieve(state["batch_id"])
            print(f"[poll-once] status={b.status}  request_counts={b.request_counts}  output_file_id={b.output_file_id}")
            if b.status == "completed":
                state["output_file_id"] = b.output_file_id
                _write_state(state)
                print(f"[poll-once] updated state.output_file_id; ready for --phase fetch")
        else:
            phase_poll()
    if args.phase in ("fetch", "all"):
        phase_fetch(apply_db=apply_db)

    print(f"\n[done] state file: {_state_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())