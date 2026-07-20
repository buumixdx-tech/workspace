#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""最简化版 summary 重写脚本 (2026-06-30).

跟 rewrite_summaries_v4.py 的区别:
  - prompt 简化: 只输出 summary 一个字段, 不分类/不抽实体/不抽股票不抽术语
  - prompt 文件: prompts/extract_summary.md (新)
  - 异步并发: asyncio + Semaphore(6), 预计 269 条 ~40-80 秒跑完
  - 输出: 极简 json (msg_id / ts / info_type / summary_old / summary_new) + md 留痕

用法:
    # dry-run 出 json + md, 不动 db
    python scripts/rewrite_summaries_simple.py --dry-run

    # 真 UPSERT 进 db
    python scripts/rewrite_summaries_simple.py --apply
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# === paths ===
SCRIPT_DIR = Path(__file__).resolve().parent
APP_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(APP_DIR))
DB = APP_DIR / "data" / "preprocess.db"
OUT_MD = APP_DIR / "feishu_summary_rewrite_simple_dryrun.md"
OUT_JSON = APP_DIR / "feishu_summary_rewrite_simple_dryrun.json"

# === config ===
CONCURRENCY = int(os.environ.get("REWRITE_CONCURRENCY", "6"))
TZ_OFFSET_HOURS = 8
REWRITE_INFO_TYPES = (1, 2, 3, 6)
DEFAULT_SINCE = "2026-06-29 15:00:00"
DEFAULT_UNTIL = "2026-06-30 14:00:00"  # now-ish


def _get_api_key() -> str:
    k = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if not k:
        raise SystemExit("FAIL: DASHSCOPE_API_KEY env not set")
    if "\u2026" in k or "..." in k:
        raise SystemExit("FAIL: DASHSCOPE_API_KEY 含 U+2026 (horiz ellipsis) 占位符, 不是真 key")
    return k


def parse_ts(s: str) -> int:
    """'YYYY-MM-DD HH:MM:SS' (Asia/Shanghai) → 毫秒时间戳."""
    import datetime as _dt
    dt = _dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    return int((dt - _dt.datetime(1970, 1, 1)).total_seconds() * 1000) - TZ_OFFSET_HOURS * 3600 * 1000


def query_window(con: sqlite3.Connection, since_ts: int, until_ts: int, msg_ids=None) -> list[dict]:
    """读 extracted 表窗口内 summary != '' 且 info_type IN (1,2,3,6) 的行.
    顺便 join messages 表拿原始 content (摘要提炼要原文)."""
    if msg_ids:
        placeholders = ",".join("?" * len(msg_ids))
        sql = f"""
            SELECT e.msg_id, e.ts, e.info_type, e.summary, m.content
            FROM extracted e
            LEFT JOIN messages m ON m.id = e.msg_id
            WHERE e.summary != '' AND e.info_type IN (1,2,3,6)
              AND e.msg_id IN ({placeholders})
            ORDER BY e.ts ASC
        """
        rows = con.execute(sql, msg_ids).fetchall()
    else:
        sql = """
            SELECT e.msg_id, e.ts, e.info_type, e.summary, m.content
            FROM extracted e
            LEFT JOIN messages m ON m.id = e.msg_id
            WHERE e.summary != '' AND e.info_type IN (1,2,3,6)
              AND e.ts >= ? AND e.ts < ?
            ORDER BY e.ts ASC
        """
        rows = con.execute(sql, (since_ts, until_ts)).fetchall()
    cols = ["msg_id", "ts", "info_type", "summary", "content"]  
    return [dict(zip(cols, r)) for r in rows]


def load_prompt_simple() -> tuple[str, str]:
    """读 prompts/extract_summary.md, 拆出 system 和 user 模板.
    这个 prompt 自己就是完整的 user 指令, 不需要 {{input_json}} 替换."""
    path = APP_DIR / "prompts" / "extract_summary.md"
    text = path.read_text(encoding="utf-8")
    # 拆 frontmatter
    if text.startswith("---"):
        end = text.find("\n---", 4)
        if end > 0:
            body = text[end + 5:].lstrip("\n")
        else:
            body = text
    else:
        body = text
    # 极简: 整个 prompt 当 system, user 只放 input_json
    # 这样既支持 batch API, 也方便迭代 system prompt
    return body, "{{input_json}}"


async def call_one(client, system: str, user_template: str, row: dict, semaphore) -> dict:
    """asyncio 调一次 LLM, 返回 {msg_id, new_summary, error}."""
    async with semaphore:
        content = row.get("content") or ""
        payload = {
            "count": 1,
            "items": [{"idx": 1, "ts": row["ts"], "text": content, "orig_len": len(content)}],
        }
        user_filled = user_template.replace("{{input_json}}", json.dumps(payload, ensure_ascii=False, indent=2))
        t0 = time.time()
        try:
            resp = await client.chat.completions.create(
                model="qwen3.5-flash",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_filled},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
                extra_body={"enable_thinking": False},
            )
            content = resp.choices[0].message.content
            data = json.loads(content)
            results = data.get("results", [])
            if not results:
                return {"msg_id": row["msg_id"], "new_summary": None, "error": "no results in response"}
            return {"msg_id": row["msg_id"], "new_summary": results[0].get("summary", ""), "error": None}
        except Exception as e:
            return {"msg_id": row["msg_id"], "new_summary": None, "error": repr(e)}


async def run_all(rows: list[dict], since_str: str, until_str: str, apply_db: bool) -> list[dict]:
    api_key = _get_api_key()
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    system, user_tpl = load_prompt_simple()
    sem = asyncio.Semaphore(CONCURRENCY)

    # 为了按顺序输出进度, 我们先并发跑, 再按 msg_id 排序
    tasks = [call_one(client, system, user_tpl, row, sem) for row in rows]
    print(f"[run] starting {len(tasks)} concurrent calls (sem={CONCURRENCY}) ...", flush=True)
    t0 = time.time()
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - t0
    print(f"[run] done in {elapsed:.1f}s, avg {elapsed/len(rows):.2f}s/req", flush=True)

    # 把 results 按 msg_id 对齐到 row, 记 plan
    by_mid = {r["msg_id"]: r for r in results}
    plan = []
    for row in rows:
        r = by_mid[row["msg_id"]]
        plan.append({"row": row, "new_summary": r["new_summary"], "error": r["error"]})

    # 可选 UPSERT
    if apply_db:
        con = sqlite3.connect(str(DB))
        try:
            for p in plan:
                if p["new_summary"] is None:
                    continue
                con.execute(
                    "UPDATE extracted SET summary = ? WHERE msg_id = ?",
                    (p["new_summary"], p["row"]["msg_id"]),
                )
            con.commit()
        finally:
            con.close()

    return plan


def render_md(plan: list[dict], since_str: str, until_str: str, applied: bool) -> str:
    import datetime as _dt
    lines = [
        "# feishu_preprocess Summary Rewrite (SIMPLE, extract only)",
        "",
        f"- Run at: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Window: {since_str} → {until_str} (Asia/Shanghai)",
        f"- DB: `{DB}`",
        f"- Prompt: `prompts/extract_summary.md` v1 (only summary, no classify/extract)",
        f"- Mode: {'APPLIED (UPSERT)' if applied else 'DRY RUN (no DB writes)'}",
        f"- Items: {len(plan)}",
        f"- Failures: {sum(1 for p in plan if p['new_summary'] is None)}",
        "",
        "## Diff",
        "",
    ]
    for i, p in enumerate(plan, 1):
        row = p["row"]
        old = row["summary"]
        new = p["new_summary"] or "(failed)"
        lines.append(f"### {i}. msg_id={row['msg_id']}  type={row['info_type']}  ts={row['ts']}")
        lines.append(f"- old ({len(old)}字): {old}")
        if p["error"]:
            lines.append(f"- ERROR: {p['error']}")
        else:
            lines.append(f"- new ({len(new)}字): {new}")
        lines.append("")
    return "\n".join(lines)


def render_json(plan: list[dict], since_str: str, until_str: str, applied: bool) -> str:
    return json.dumps({
        "since": since_str,
        "until": until_str,
        "applied": applied,
        "items": [
            {
                "msg_id": p["row"]["msg_id"],
                "ts": p["row"]["ts"],
                "info_type": p["row"]["info_type"],
                "summary_old": p["row"]["summary"],
                "summary_new": p["new_summary"],
            }
            for p in plan
        ],
    }, ensure_ascii=False, indent=2)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="出 json+md, 不动 db (默认)")
    p.add_argument("--apply", action="store_true", help="真 UPSERT summary 进 db")
    p.add_argument("--since", default=DEFAULT_SINCE)
    p.add_argument("--until", default=DEFAULT_UNTIL)
    p.add_argument("--msg-ids", default="", help="逗号分隔 msg_id (调试, 优先)")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--out", default=str(OUT_MD))
    p.add_argument("--out-json", default=str(OUT_JSON))
    args = p.parse_args()

    if args.dry_run and args.apply:
        print("FAIL: --dry-run 和 --apply 不能同时"); return 2
    apply = args.apply

    msg_ids = [int(x) for x in args.msg_ids.split(",") if x.strip()] if args.msg_ids else None

    since_ts = parse_ts(args.since)
    until_ts = parse_ts(args.until)

    con = sqlite3.connect(str(DB))
    try:
        rows = query_window(con, since_ts, until_ts, msg_ids=msg_ids)
    finally:
        con.close()
    if args.limit:
        rows = rows[: args.limit]

    print(f"[plan] window {args.since} → {args.until} (Asia/Shanghai)", flush=True)
    print(f"[plan] mode={'APPLY (UPSERT)' if apply else 'DRY RUN'}", flush=True)
    print(f"[plan] rows to rewrite: {len(rows)}", flush=True)

    if not rows:
        print("[plan] no rows, exit")
        return 0

    plan = asyncio.run(run_all(rows, args.since, args.until, apply_db=apply))

    md = render_md(plan, args.since, args.until, applied=apply)
    Path(args.out).write_text(md, encoding="utf-8")
    print(f"[done] wrote {args.out} ({len(md):,} chars)", flush=True)

    js = render_json(plan, args.since, args.until, applied=apply)
    Path(args.out_json).write_text(js, encoding="utf-8")
    print(f"[done] wrote {args.out_json} ({len(js):,} chars)", flush=True)

    fail = sum(1 for p in plan if p["new_summary"] is None)
    if fail:
        print(f"[done] ⚠ {fail} failures, see md for details", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())