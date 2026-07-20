"""audit_ima.py - IMA KB 对账脚本.

验证 feishu_to_ima.db 跟 IMA KB 真实状态的对齐:

Invariant A (推送完整):
  feishu_src.extracted - SKIP_TYPE_CODES ⊆ {msg_ids 已上传 IMA 的 msg_ids}

Invariant B (db 记载完整):
  {msg_ids 在 IMA 端的 txt 中} ⊆ {msg_ids 本地 db 里 msg_ids_json 记载}

注: 当前 IMA API 不暴露下载 TXT 内容接口, 我们只能 verify:
  - Title-level: 拉 IMA get_knowledge_list 拿到所有 title, 比对本地 txt_bucket.txt_filename
  - msg_id-level: 仅对 has_msg_id=1 的 TXT 做内容解析 (本地有完整 msg_ids_json)
  - 对账 msg_ids_json 中每个 msg_id 是否在 feishu_src.extracted 中 (避免孤儿)
  - 不验证 IMA 端的 TXT 实际包含哪些 msg_id (那需要下载 TXT 内容, IMA API 不支持)

输出: 报告写入 logs/audit_ima_<timestamp>.txt
"""
from __future__ import annotations

import asyncio
import datetime
import json
import sqlite3
from pathlib import Path

import aiohttp

import sys
# 2026-07-04 迁移: 项目从 D:\workspace\LightRAG 搬到了 D:\WorkSpace\Trading\Recourse 下
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from feishu_to_ima_db_writer import (
    connect, SKIP_TYPE_CODES, FEISHU_TO_IMA_DB,
)
from ima_config import (
    IMA_CLIENT_ID, IMA_API_KEY, IMA_KB_ID, IMA_BASE_URL, IMA_SKILL_VERSION,
)


# ---------------------------------------------------------------------------
# IMA 端拉数据
# ---------------------------------------------------------------------------
async def fetch_all_ima_titles() -> list[dict]:
    """拉 KB 全部条目. 返回 [{title, media_id, ...}, ...]"""
    items = []
    cursor = ""
    async with aiohttp.ClientSession() as session:
        while True:
            headers = {
                "ima-openapi-clientid": IMA_CLIENT_ID,
                "ima-openapi-apikey": IMA_API_KEY,
                "ima-openapi-ctx": f"skill_version={IMA_SKILL_VERSION}",
                "Content-Type": "application/json",
            }
            async with session.post(
                f"{IMA_BASE_URL}/openapi/wiki/v1/get_knowledge_list",
                json={"knowledge_base_id": IMA_KB_ID, "cursor": cursor, "limit": 50},
                headers=headers,
            ) as resp:
                data = json.loads(await resp.text())
            if data.get("code") != 0:
                print(f"  [IMA] page error: code={data.get('code')} msg={data.get('msg')}")
                break
            d = data.get("data") or {}
            items.extend(d.get("knowledge_list") or [])
            if d.get("is_end"):
                break
            cursor = d.get("next_cursor") or ""
            if not cursor:
                break
            await asyncio.sleep(0.2)
    return items


# ---------------------------------------------------------------------------
# 本地 db 对账
# ---------------------------------------------------------------------------
def audit_local_invariants(con: sqlite3.Connection) -> dict:
    """对 feishu_to_ima.db 跟 feishu_src.extracted 做对账 (不需要 IMA)."""
    # 1. SHOULD be in IMA: feishu_src.extracted - SKIP
    should = set()
    skip_list = sorted(SKIP_TYPE_CODES)
    placeholders = ",".join("?" * len(skip_list))
    for r in con.execute(
        f"SELECT msg_id FROM feishu_src.extracted WHERE info_type NOT IN ({placeholders}) "
        "ORDER BY msg_id",
        skip_list,
    ):
        should.add(int(r[0]))

    # 2. TRACKED as uploaded (txt_bucket.msg_ids_json where posted_at IS NOT NULL)
    tracked = set()
    for r in con.execute(
        "SELECT msg_ids_json FROM txt_bucket WHERE posted_at IS NOT NULL AND posted_at != ''"
    ):
        tracked.update(json.loads(r[0]))

    # 3. Invariant A: SHOULD ⊆ TRACKED?
    a_drift = should - tracked
    a_extra = tracked - should  # 跟踪了但不在 SHOULD 里 (被 re-classify 成了 SKIP)

    # 4. msg_ids_json 完整性: txt_bucket 里每个 msg_id 都在 feishu_src.extracted 中
    orphan_msg_ids = []
    for r in con.execute(
        "SELECT txt_filename, msg_ids_json FROM txt_bucket WHERE has_msg_id=1"
    ):
        fname, raw = r[0], r[1]
        for mid in json.loads(raw):
            row = con.execute(
                "SELECT 1 FROM feishu_src.extracted WHERE msg_id=?", (mid,)
            ).fetchone()
            if not row:
                orphan_msg_ids.append((fname, mid))

    # 5. txt_bucket 自身: 每行 posted_at IS NULL 的应该没被 upload (但 DRY RUN 也写)
    pending = list(con.execute(
        "SELECT txt_filename, doc_count, created_at FROM txt_bucket "
        "WHERE posted_at IS NULL OR posted_at = ''"
    ))

    return {
        "should_in_ima": len(should),
        "tracked_in_ima": len(tracked),
        "invariant_a_drift": sorted(a_drift),  # should upload but not tracked
        "invariant_a_extra": sorted(a_extra),  # tracked but no longer should
        "orphan_msg_ids": orphan_msg_ids,      # msg_id in txt_bucket but not in extracted
        "pending_uploads": pending,            # txt_bucket posted_at IS NULL
    }


def audit_ima_vs_local(con: sqlite3.Connection, ima_items: list[dict]) -> dict:
    """IMA title vs 本地 txt_bucket.txt_filename 比对."""
    ima_titles = {it["title"]: it for it in ima_items if it.get("title")}
    local_filenames = {r[0] for r in con.execute("SELECT txt_filename FROM txt_bucket")}

    return {
        "ima_total_items": len(ima_items),
        "ima_unique_titles": len(ima_titles),
        "local_total_filenames": len(local_filenames),
        "in_ima_only": sorted(ima_titles.keys() - local_filenames),
        "in_local_only": sorted(local_filenames - ima_titles.keys()),
        "in_both": sorted(ima_titles.keys() & local_filenames),
    }


# ---------------------------------------------------------------------------
# 报告输出
# ---------------------------------------------------------------------------
def render_report(local_inv: dict, ima_inv: dict, ima_items: list[dict]) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append(f"  IMA KB Audit Report")
    lines.append(f"  Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  KB ID: {IMA_KB_ID}")
    lines.append("=" * 70)
    lines.append("")

    lines.append("--- Title-level: IMA vs local txt_bucket ---")
    lines.append(f"  IMA items total:           {ima_inv['ima_total_items']}")
    lines.append(f"  IMA unique titles:         {ima_inv['ima_unique_titles']}")
    lines.append(f"  Local txt_bucket rows:     {ima_inv['local_total_filenames']}")
    lines.append(f"  In both:                   {len(ima_inv['in_both'])}")
    lines.append(f"  In IMA only (ghosts):      {len(ima_inv['in_ima_only'])}")
    lines.append(f"  In local only (not yet uploaded): {len(ima_inv['in_local_only'])}")
    if ima_inv["in_ima_only"]:
        lines.append(f"  Ghost titles:")
        for t in ima_inv["in_ima_only"]:
            lines.append(f"    - {t}")
    if ima_inv["in_local_only"]:
        lines.append(f"  Pending local titles (not yet uploaded):")
        for t in ima_inv["in_local_only"]:
            lines.append(f"    - {t}")
    lines.append("")

    lines.append("--- Invariant A (推送完整) ---")
    lines.append(f"  SHOULD be in IMA (extracted - SKIP):     {local_inv['should_in_ima']}")
    lines.append(f"  TRACKED in IMA (msg_ids_json posted):   {local_inv['tracked_in_ima']}")
    lines.append(f"  Drift (should but not tracked):         {len(local_inv['invariant_a_drift'])}")
    if local_inv["invariant_a_drift"]:
        lines.append(f"  Sample (first 20): {local_inv['invariant_a_drift'][:20]}")
    lines.append(f"  Extra (tracked but no longer should):   {len(local_inv['invariant_a_extra'])}")
    if local_inv["invariant_a_extra"]:
        lines.append(f"  Sample (first 20): {local_inv['invariant_a_extra'][:20]}")
    lines.append("")

    lines.append("--- Invariant B (db 记载完整 / 引用完整性) ---")
    lines.append(f"  Orphan msg_ids (in txt_bucket but NOT in extracted): {len(local_inv['orphan_msg_ids'])}")
    if local_inv["orphan_msg_ids"]:
        lines.append(f"  Sample (first 10):")
        for fname, mid in local_inv["orphan_msg_ids"][:10]:
            lines.append(f"    {fname}: msg_id={mid}")
    lines.append("")

    lines.append("--- Pending uploads (txt_bucket.posted_at IS NULL) ---")
    lines.append(f"  Count: {len(local_inv['pending_uploads'])}")
    for fname, count, created in local_inv["pending_uploads"]:
        lines.append(f"    {fname}  ({count} msg_ids, created {created})")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
async def main():
    print("=== IMA KB Audit ===\n")

    print("[1/3] connecting local db...")
    con = connect()
    try:
        print("[2/3] computing local invariants...")
        local_inv = audit_local_invariants(con)

        print("[3/3] fetching IMA KB contents (paginated)...")
        ima_items = await fetch_all_ima_titles()
        ima_inv = audit_ima_vs_local(con, ima_items)
    finally:
        con.close()

    report = render_report(local_inv, ima_inv, ima_items)
    print()
    print(report)

    # Write to logs/
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path(HERE).parent / "logs" / f"audit_ima_{ts}.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(report, encoding="utf-8")
    print(f"\n[report saved] {log_path}")


if __name__ == "__main__":
    asyncio.run(main())