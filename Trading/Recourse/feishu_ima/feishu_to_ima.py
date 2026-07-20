"""feishu_to_ima 主入口.

Pipeline (2026-06-24 重构 v3, ATTACH 模式):
  Step 2: extract_to_txt (水位化分桶, 50 msg/file, 单事务推进水位)
  Step 3: upload_to_ima (aiohttp 直调 IMA OpenAPI, 5 步链, 串行)
  Step 4: mark_ima_posted + 出报告
  (老 Step 1 sync_extracted 已删, ATTACH 上游 db 直接读 feishu_src.*)

DRY RUN / REAL RUN:
  默认 DRY RUN; 传 --real 走真上传
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 让脚本可以直接 python xxx.py 跑 (不用 PYTHONPATH)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from feishu_to_ima_db_writer import (
    connect,
    FEISHU_TO_IMA_DB, IMA_TXT_DIR,
    get_ima_posted_msg_ids, read_bucket_state, get_msg_ids_after_watermark,
    SKIP_TYPE_CODES, heartbeat,
)
from feishu_to_ima_extract_to_txt import extract_to_txt


def main():
    args = sys.argv[1:]
    DRY_RUN = "--real" not in args  # 默认 DRY RUN

    print(f"=== feishu_to_ima {'DRY RUN' if DRY_RUN else 'REAL RUN'} ===\n")
    print(f"feishu_to_ima.db: {FEISHU_TO_IMA_DB}")
    print(f"ima_txt 目录: {IMA_TXT_DIR}\n")

    # 2026-06-23 ATTACH 重构后: 启动一个 con (含 ATTACH feishu_src), 全程复用.
    # 老版本 Step 1 (sync_extracted_from_feishu_preprocess) 已删, 不再需要 close+reopen.
    con = connect()
    heartbeat(con, 'running', f"start, dry_run={DRY_RUN}")

    # Step 2: 拼 TXT
    print("[Step 2] 拼 TXT 文件 (50 msg/file, ts ASC 排序全局分桶)")
    try:
        extract_stats = extract_to_txt(dry_run=DRY_RUN)
    except Exception as e:
        print(f"  ERROR: {e}")
        heartbeat(con, 'failed', f"step2 extract: {e}")
        sys.exit(1)

    if DRY_RUN:
        print("\n[Step 3] 跳过上传 (DRY RUN)")
        print("[Step 4] 跳过 mark_posted (DRY RUN)")
        heartbeat(con, 'done', f"dry_run, txt_files={extract_stats.get('txt_files', 0)}")
    else:
        # Step 3 + 4: 真上传
        print("\n[Step 3] 上传 IMA")
        try:
            import asyncio
            from feishu_to_ima_upload_to_ima import upload_to_ima
            upload_stats = asyncio.run(upload_to_ima())
            print(f"  uploaded: {upload_stats.get('uploaded', 0)}")
            print(f"  skipped:  {upload_stats.get('skipped', 0)}")
            print(f"  failed:   {upload_stats.get('failed', 0)}")
        except Exception as e:
            print(f"  ERROR: {e}")
            heartbeat(con, 'failed', f"step3 upload: {e}")
            sys.exit(1)
        heartbeat(con, 'done', f"real_run, txt_files={extract_stats.get('txt_files', 0)}, uploaded={upload_stats.get('uploaded', 0)}")

    # 出报告 (2026-06-24 v3 水位化)
    print("\n=== 报告 ===")
    total = con.execute("SELECT COUNT(*) FROM feishu_src.extracted").fetchone()[0]
    last_ts, last_msg_id, current_seq = read_bucket_state(con)
    candidates = get_msg_ids_after_watermark(con, last_ts, last_msg_id)
    posted = len(get_ima_posted_msg_ids(con))
    txt_files = con.execute("SELECT COUNT(*) FROM txt_bucket").fetchone()[0]
    pending_uploads = con.execute(
        "SELECT COUNT(*) FROM txt_bucket WHERE posted_at IS NULL OR posted_at = ''"
    ).fetchone()[0]
    print(f"  feishu_src.extracted total: {total}")
    print(f"  watermark:  ({last_ts}, {last_msg_id}), bucket_seq={current_seq}")
    print(f"  unbatched (待分桶): {len(candidates)}")
    print(f"  uploaded msg_ids: {posted}")
    print(f"  txt_bucket 文件数: {txt_files}  (pending uploads: {pending_uploads})")
    print(f"  skip_codes: {sorted(SKIP_TYPE_CODES)}")

    con.close()
    print(f"\n=== done ===")


if __name__ == "__main__":
    main()