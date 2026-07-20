"""feishu_to_ima_extract_to_txt: 水位化版本, 从 feishu_src.extracted 拼 TXT 文件.

2026-06-24 重构 v3 (2026-07-16 再优化):
  - 上游表全部走 feishu_src.* (ATTACH 上游 db)
  - 用 (last_ts, last_msg_id) 复合水位查 feishu_src.extracted
  - 50/桶切片, 全局 bucket_seq 自增 (避免历史 220 条 ghost 撞名)
  - 每条 msg 块头部加 【msg_id】<id> 行 (audit 时可解析)
  - 单事务: 写 txt_bucket + 推进水位 (每文件推进到自己的 seq, 崩溃续传无空洞)
  - 独立 skip 规则 (从 feishu_to_ima_db_writer.SKIP_TYPE_CODES 拿, 默认 {4,5,7,8,9,10})
  - 批量 JOIN 取数据 (每 500 msg 3 query, 不再每 msg 4 query)

TXT 文件名格式 (无中文):
    feishu_<YYYYMMDD_first>_<YYYYMMDD_last>_<bucket_seq:03d>.txt
    例: feishu_20260301_20260302_217.txt
    例: feishu_20260520_20260623_344.txt

TXT 单条 msg 格式:
    【msg_id】47686
    【信息类型】个股点评
    【行业赛道】半导体设备/ALD
    【涉及个股】联发科
    【核心概念】成本上扬, 涨价, 通知客户涨价
    【核心摘要】联发科受通膨影响成本上升, 已通知客户涨价
    【发布时间】2026-04-28 21:56:10

    --- 原文 ---

    <原始消息内容>

    ============================================================
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import sys
from pathlib import Path

from feishu_to_ima_db_writer import (
    connect,
    read_bucket_state,
    advance_bucket_state,
    get_msg_ids_after_watermark,
    write_txt_bucket,
    IMA_TXT_DIR,
    SKIP_TYPE_CODES,
)

TZ_BEIJING = datetime.timezone(datetime.timedelta(hours=8))

# 50 msg/文件
DOCS_PER_FILE = 50

# 批量取数据时单批 msg_id 上限 (避开 SQLITE_MAX_VARIABLE_NUMBER, 默认 999)
_FETCH_BATCH = 500


# ---------------------------------------------------------------------------
# info_type label (复用 feishu_ext 的 CODE_TO_LABELS, 模块级 import 一次)
# ---------------------------------------------------------------------------
_CODE_TO_LABELS: dict[int, str] | None = None
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "feishu_ext"))
    from prompts.schemas import CODE_TO_LABELS as _CODE_TO_LABELS  # type: ignore
except ImportError:
    _CODE_TO_LABELS = None


def _code_to_label(code: int) -> str:
    """info_type 整数 -> 中文 label. 复用 feishu_ext 的 CODE_TO_LABELS (单源).

    路径: feishu_ima/feishu_to_ima_extract_to_txt.py -> ../../feishu_ext/prompts/schemas.py
    注意: feishu_ext 是 feishu_preprocess 的替代品(2026-07-03 改名).
    schemas.py 缺失时退回 "未知(code)".
    """
    if _CODE_TO_LABELS is not None:
        return _CODE_TO_LABELS.get(int(code), f"未知({code})")
    return f"未知({code})"


# ---------------------------------------------------------------------------
# 文本生成
# ---------------------------------------------------------------------------
def _ts_to_str(ts_ms: int) -> str:
    return datetime.datetime.fromtimestamp(ts_ms / 1000, TZ_BEIJING).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _ts_to_yyyymmdd(ts_ms: int) -> str:
    return datetime.datetime.fromtimestamp(ts_ms / 1000, TZ_BEIJING).strftime("%Y%m%d")


# ---------------------------------------------------------------------------
# 批量取数据 (替代 N+1: 每 msg 4 query -> 每 500 msg 3 query)
# ---------------------------------------------------------------------------
def _fetch_payloads(con: sqlite3.Connection, msg_ids: list[int]) -> dict[int, dict]:
    """一次取回多个 msg 的完整字段. 返回 {msg_id: {info_type, category, summary, ts, content, stocks, terms}}.

    分批 IN (?,...) 每批 _FETCH_BATCH 个, 避开 SQLite 参数上限.
    stocks/terms 用子查询排序后 GROUP_CONCAT, 保持 'A, B' 顺序与原实现一致.
    """
    payloads: dict[int, dict] = {}
    if not msg_ids:
        return payloads

    for i in range(0, len(msg_ids), _FETCH_BATCH):
        batch = msg_ids[i:i + _FETCH_BATCH]
        ph = ",".join("?" * len(batch))

        # 1) extracted JOIN messages
        rows = con.execute(
            f"SELECT e.msg_id, e.info_type, e.category, e.summary, e.ts, m.content "
            f"FROM feishu_src.extracted e "
            f"LEFT JOIN feishu_src.messages m ON m.id = e.msg_id "
            f"WHERE e.msg_id IN ({ph})",
            batch,
        ).fetchall()
        for mid, itype, category, summary, ts, content in rows:
            payloads[int(mid)] = {
                "info_type": itype,
                "category": category or "",
                "summary": summary or "",
                "ts": int(ts),
                "content": content if content is not None else f"(msg_id={mid} 原文缺失)",
                "stocks": "",
                "terms": "",
            }

        # 2) stocks (子查询排序后聚合, 保持顺序)
        for mid, joined in con.execute(
            f"SELECT msg_id, GROUP_CONCAT(stock, ', ') FROM ("
            f"  SELECT msg_id, stock FROM feishu_src.extracted_stocks "
            f"  WHERE msg_id IN ({ph}) ORDER BY msg_id, stock"
            f") GROUP BY msg_id",
            batch,
        ):
            mid_i = int(mid)
            if mid_i in payloads:
                payloads[mid_i]["stocks"] = joined or ""

        # 3) terms
        for mid, joined in con.execute(
            f"SELECT msg_id, GROUP_CONCAT(term, ', ') FROM ("
            f"  SELECT msg_id, term FROM feishu_src.extracted_terms "
            f"  WHERE msg_id IN ({ph}) ORDER BY msg_id, term"
            f") GROUP BY msg_id",
            batch,
        ):
            mid_i = int(mid)
            if mid_i in payloads:
                payloads[mid_i]["terms"] = joined or ""

    return payloads


def _build_one_message(payload: dict, msg_id: int) -> tuple[str, int]:
    """从内存 payload 拼一条信息块 (头部加 【msg_id】<id>). 不查 DB.

    Returns: (text_block, ts_ms).
    """
    label = _code_to_label(payload["info_type"])
    head = [
        f"【msg_id】{msg_id}",
        f"【信息类型】{label}",
        f"【行业赛道】{payload['category'] or '(无)'}",
        f"【涉及个股】{payload['stocks'] or '(无)'}",
        f"【核心概念】{payload['terms'] or '(无)'}",
        f"【核心摘要】{payload['summary'] or '(无)'}",
        f"【发布时间】{_ts_to_str(payload['ts'])}",
    ]
    block = "\n".join(head + [
        "",
        "--- 原文 ---",
        "",
        payload["content"],
        "",
        "============================================================",
        "",
    ])
    return block, payload["ts"]


# ---------------------------------------------------------------------------
# 分桶 + 切片 (水位 + bucket_seq 全局)
# ---------------------------------------------------------------------------
def collect_into_buckets(
    candidates: list[tuple[int, int]],
    start_seq: int,
) -> list[tuple[str, list[tuple[int, int]]]]:
    """全局 ts 模式分桶 + 50/桶切片. 返回 [(txt_filename, [(msg_id, ts), ...]), ...].

    每个文件 seq = start_seq + 文件序号 + 1 (从 start_seq+1 起, 连续).
    """
    sliced = []
    for i in range(0, len(candidates), DOCS_PER_FILE):
        chunk = candidates[i:i + DOCS_PER_FILE]
        seq = start_seq + i // DOCS_PER_FILE + 1
        ts_first, ts_last = chunk[0][1], chunk[-1][1]
        d_first, d_last = _ts_to_yyyymmdd(ts_first), _ts_to_yyyymmdd(ts_last)
        fname = f"feishu_{d_first}_{d_last}_{seq:03d}.txt"
        sliced.append((fname, chunk))
    return sliced


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def extract_to_txt(dry_run: bool = False) -> dict:
    """水位化分桶 + 写文件 + 推进水位 (每文件单事务, 推进到本文件 seq)."""
    con = connect()
    try:
        last_ts, last_msg_id, current_seq = read_bucket_state(con)
        print(f"[watermark] last_ts={last_ts}, last_msg_id={last_msg_id}, current_seq={current_seq}")

        candidates = get_msg_ids_after_watermark(con, last_ts, last_msg_id)
        print(f"[query] 水位后候选: {len(candidates)} 个 msg_id (skip 独立规则 {sorted(SKIP_TYPE_CODES)})")

        if not candidates:
            print("[query] 没有新候选, 退出")
            return {"buckets": 0, "txt_files": 0, "msg_ids": 0}

        sliced = collect_into_buckets(candidates, current_seq)
        print(f"[bucket] {len(sliced)} 个 TXT 文件 (seq {current_seq+1} ~ {current_seq + len(sliced)})")

        # 批量取数据 (一次, 替代 N+1)
        all_msg_ids = [mid for mid, _ts in candidates]
        payloads = _fetch_payloads(con, all_msg_ids)
        missing = [mid for mid in all_msg_ids if mid not in payloads]
        if missing:
            raise ValueError(f"{len(missing)} 个 msg_id 不在 feishu_src.extracted: {missing[:10]}...")

        # 写文件 + 单事务推进水位
        txt_files_written = 0
        total_chars = 0
        last_processed_ts = last_ts
        last_processed_msg_id = last_msg_id

        for idx, (fname, chunk) in enumerate(sliced):
            # 拼内容
            content_parts = []
            file_chars = 0
            for msg_id, _ts in chunk:
                block, _ts = _build_one_message(payloads[msg_id], msg_id)
                content_parts.append(block)
                file_chars += len(block)
            full_content = "".join(content_parts)
            total_chars += file_chars

            if not dry_run:
                txt_path = IMA_TXT_DIR / fname
                txt_path.write_bytes(full_content.encode("utf-8"))

                # 单事务: 写 txt_bucket + 推进水位 (失败回滚)
                # bucket_seq 推进到本文件实际 seq, 崩溃续传不会留空洞
                this_seq = current_seq + idx + 1
                try:
                    msg_ids_in_chunk = [m for m, _ in chunk]
                    write_txt_bucket(
                        con, fname, msg_ids_in_chunk,
                        info_type=0, category="",
                        bucket_yyyymm=_ts_to_yyyymmdd(chunk[0][1])[:6],
                        total_chars=file_chars,
                        has_msg_id=True,
                    )
                    # 推进水位到本批最后一条
                    last_processed_ts = chunk[-1][1]
                    last_processed_msg_id = chunk[-1][0]
                    advance_bucket_state(
                        con, last_processed_ts, last_processed_msg_id,
                        bucket_seq=this_seq,
                        last_post_track=fname,
                    )
                    con.commit()
                except Exception:
                    con.rollback()
                    raise

                txt_files_written += 1

        stats = {
            "buckets": len(sliced),
            "txt_files": txt_files_written if not dry_run else 0,
            "msg_ids": len(candidates),
            "total_chars": total_chars,
            "dry_run": dry_run,
            "watermark_before": (last_ts, last_msg_id),
            "watermark_after": (last_processed_ts, last_processed_msg_id) if not dry_run else None,
            "new_seq_range": (current_seq + 1, current_seq + len(sliced)),
            "skip_codes": sorted(SKIP_TYPE_CODES),
        }

        print()
        print(f"[done] {'DRY RUN' if dry_run else 'REAL'}")
        print(f"  TXT 文件: {stats['txt_files'] if not dry_run else len(sliced)}")
        print(f"  覆盖 msg_id: {stats['msg_ids']}")
        print(f"  总字符: {stats['total_chars']:,}")
        print(f"  seq 范围: {stats['new_seq_range']}")
        if not dry_run:
            print(f"  水位推进: ({stats['watermark_before']}) -> ({stats['watermark_after']})")
        print(f"  TXT 目录: {IMA_TXT_DIR}")

        return stats
    finally:
        con.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv or "-n" in sys.argv
    print(f"=== feishu_to_ima extract_to_txt {'DRY RUN' if dry else 'REAL RUN'} ===\n")
    stats = extract_to_txt(dry_run=dry)
    print(f"\n=== done ===")
    print(json.dumps(stats, ensure_ascii=False, indent=2, default=str))
