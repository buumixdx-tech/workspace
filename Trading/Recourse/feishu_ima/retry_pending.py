"""retry_pending.py — 只重传 txt_bucket 里 posted_at IS NULL 的 TXT,水位不动。

设计动机:
  feishu_to_ima.py --real 在拼完 TXT 后,水位已推进,但 upload 阶段因 aiohttp 缺失/
  网络抽风/凭证临时失效等原因挂掉,3 个 TXT 留在 posted_at IS NULL 状态。
  完整重跑会把水位之后的候选继续拼新 TXT,旧的不再重试。
  本脚本只调 upload_to_ima(),其内部 SQL 已经精确挑 pending 行 (posted_at IS NULL),
  不动 bucket_state。

用法:
  python retry_pending.py            # 自动确认(因为是 retry 已落盘的 TXT,无新数据风险)
  python retry_pending.py --dry-run  # 只打印 pending TXT 列表,不动 IMA

不动:
  - bucket_state 水位 (last_ts/last_msg_id/bucket_seq)
  - 上次失败的 heartbeat (留作审计),本脚本成功后只 print 不写
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from feishu_to_ima_db_writer import connect, FEISHU_TO_IMA_DB, IMA_TXT_DIR
from feishu_to_ima_upload_to_ima import upload_to_ima
from ima_config import IMA_CLIENT_ID, IMA_API_KEY, IMA_KB_ID


def list_pending(con) -> list[dict]:
    cur = con.execute("""
        SELECT txt_filename, doc_count, msg_ids_json, total_chars, created_at
        FROM txt_bucket
        WHERE posted_at IS NULL OR posted_at = ''
        ORDER BY txt_filename ASC
    """)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="只打印 pending TXT,不传 IMA")
    args = p.parse_args()

    print(f"=== retry_pending {'(DRY)' if args.dry_run else '(REAL)'} ===\n")
    print(f"feishu_to_ima.db: {FEISHU_TO_IMA_DB}")
    print(f"ima_txt 目录: {IMA_TXT_DIR}")
    print(f"IMA_KB_ID: {IMA_KB_ID}")
    print(f"ClientID loaded: {bool(IMA_CLIENT_ID)}")
    print(f"APIKey loaded: {bool(IMA_API_KEY)}\n")

    if not IMA_CLIENT_ID or not IMA_API_KEY:
        print("[ERROR] IMA 凭证缺失(IMA_CLIENT_ID / IMA_API_KEY),检查 ~/.config/ima/ 或 env",
              file=sys.stderr)
        return 2

    con = connect()
    pending = list_pending(con)
    con.close()

    if not pending:
        print("📭 没有 pending TXT,无需 retry")
        return 0

    total_msgs = sum(len(json.loads(r["msg_ids_json"])) for r in pending)
    total_chars = sum(r["total_chars"] for r in pending)
    print(f"📦 pending TXT: {len(pending)} 个, 覆盖 {total_msgs} msg, 总字符 {total_chars:,}\n")
    for r in pending:
        msg_ids = json.loads(r["msg_ids_json"])
        print(f"  - {r['txt_filename']:38s}  doc={r['doc_count']:3d}  "
              f"chars={r['total_chars']:>6,}  msg_id 范围 "
              f"{min(msg_ids)} ~ {max(msg_ids)}  created={r['created_at']}")
    print()

    if args.dry_run:
        print("⏭️ --dry-run, 跳过上传")
        return 0

    print("🚀 开始上传 IMA (max_concurrent=1 串行)...\n")
    stats = asyncio.run(upload_to_ima())
    print()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())