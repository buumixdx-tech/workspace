#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""列昨天下午 3 点之后的批次 (按时段分组, 每批展示 5 条样本)"""
import sqlite3, datetime
# 2026-07-04 迁移: 路径更新
con = sqlite3.connect(r"D:\WorkSpace\Trading\Recourse\feishu_ext\data\preprocess.db")
cur = con.cursor()

TZ = datetime.timezone(datetime.timedelta(hours=8))
START_TS = int(datetime.datetime(2026, 6, 29, 15, 0, 0, tzinfo=TZ).timestamp() * 1000)
END_TS = int(datetime.datetime.now(TZ).timestamp() * 1000)

# 1) 已抽取 (extracted 里有) vs 未抽取 (只在 messages 里有)
cur.execute("""
    SELECT COUNT(*) FROM messages m
    LEFT JOIN extracted e ON m.id = e.msg_id
    WHERE m.kind = 't' AND length(m.content) > 10
      AND m.ts >= ? AND m.ts <= ?
""", (START_TS, END_TS))
total_in_window = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) FROM messages m
    JOIN extracted e ON m.id = e.msg_id
    WHERE m.kind = 't' AND length(m.content) > 10
      AND m.ts >= ? AND m.ts <= ?
      AND e.info_type IN (1,2,3,6)
""", (START_TS, END_TS))
already_extracted = cur.fetchone()[0]

# 未抽取: 还在 messages 等 v4 处理
cur.execute("""
    SELECT COUNT(*) FROM messages m
    LEFT JOIN extracted e ON m.id = e.msg_id
    WHERE m.kind = 't' AND length(m.content) > 10
      AND m.ts >= ? AND m.ts <= ?
      AND e.rowid IS NULL
""", (START_TS, END_TS))
not_yet = cur.fetchone()[0]

print(f"窗口: 2026-06-29 15:00 → 2026-06-30 12:28 (Asia/Shanghai)")
print(f"  total msg: {total_in_window}")
print(f"  已 extracted (info_type 1/2/3/6): {already_extracted}")
print(f"  未抽取 (LEFT JOIN missing): {not_yet}")

# 看未抽取样本 (按 ts ASC 取前 10)
cur.execute("""
    SELECT m.id, m.ts, m.content FROM messages m
    LEFT JOIN extracted e ON m.id = e.msg_id
    WHERE m.kind = 't' AND length(m.content) > 10
      AND m.ts >= ? AND m.ts <= ?
      AND e.rowid IS NULL
    ORDER BY m.ts ASC LIMIT 10
""", (START_TS, END_TS))
print(f"\n--- 未抽取样本 (按 ts ASC 前 10 条) ---")
for mid, ts_ms, content in cur.fetchall():
    dt = datetime.datetime.fromtimestamp(ts_ms/1000, TZ).strftime("%Y-%m-%d %H:%M:%S")
    head = content[:80].replace("\n", " ")
    print(f"  msg_id={mid:>6}  {dt}  len={len(content):>4}  | {head}…")

# 看已抽取样本 (按 ts ASC 前 5 条 info_type 1/2/3/6) — 这些是 v3 出的旧 summary
cur.execute("""
    SELECT m.id, m.ts, m.content, e.summary, e.info_type FROM messages m
    JOIN extracted e ON m.id = e.msg_id
    WHERE m.kind = 't' AND length(m.content) > 10
      AND m.ts >= ? AND m.ts <= ?
      AND e.info_type IN (1,2,3,6)
    ORDER BY m.ts ASC LIMIT 5
""", (START_TS, END_TS))
print(f"\n--- 已抽取 (v3 旧 summary) 样本前 5 条 ---")
for mid, ts_ms, content, summary, it in cur.fetchall():
    dt = datetime.datetime.fromtimestamp(ts_ms/1000, TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n  msg_id={mid}  {dt}  info_type={it}  orig_len={len(content)}")
    print(f"    OLD summary (len={len(summary)}): [{summary}]")
    print(f"    ORIGINAL (前 120 字): [{content[:120]}…]")

con.close()