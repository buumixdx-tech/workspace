"""mycloud_preprocess DB writer.

Owns the lifecycle of mycloud_preprocess.db (独立于 feishu preprocess.db):
  - messages 表: 从 jcloud 上的 mycloud.db 镜像 (HTTP 走 mycloud_proxy:9623)
  - extracted / extracted_stocks / extracted_terms: mycloud_preprocess 拥有
  - ima_push_batches: IMA 推送批次记录表 (2026-07-05 新增)

Public API:
  ensure_schema(con)              -- idempotent CREATE TABLE IF NOT EXISTS
  sync_mycloud_records(...)       -- 调 jcloud:9623 HTTP 代理增量拉 records
  upsert_extracted(...)           -- 单行 UPSERT (主表 + 2 子表)
  mark_posted_to_ima(...)        -- IMA 推送成功后批量更新 posted 标志
  get_posted_msg_ids(con)        -- SELECT msg_id FROM extracted WHERE posted=1
"""
from __future__ import annotations

import base64
import json
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# schema DDL
# ---------------------------------------------------------------------------

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY,
    ts           INTEGER NOT NULL,
    kind         TEXT    NOT NULL,
    content      TEXT    NOT NULL,
    content_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts);

CREATE TABLE IF NOT EXISTS extracted (
    msg_id     INTEGER PRIMARY KEY,
    ts         INTEGER NOT NULL,
    info_type  INTEGER NOT NULL DEFAULT 10,
    category   TEXT    NOT NULL DEFAULT '',
    summary    TEXT    NOT NULL DEFAULT '',
    posted     INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S+00:00', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_extracted_ts ON extracted(ts);
CREATE INDEX IF NOT EXISTS idx_extracted_info_type ON extracted(info_type);

CREATE TABLE IF NOT EXISTS extracted_stocks (
    msg_id INTEGER NOT NULL,
    stock  TEXT    NOT NULL,
    PRIMARY KEY (msg_id, stock)
);
CREATE INDEX IF NOT EXISTS idx_stocks_stock ON extracted_stocks(stock);

CREATE TABLE IF NOT EXISTS extracted_terms (
    msg_id INTEGER NOT NULL,
    term   TEXT    NOT NULL,
    PRIMARY KEY (msg_id, term)
);
CREATE INDEX IF NOT EXISTS idx_terms_term ON extracted_terms(term);

-- IMA 推送批次表: 每成功推送一批（10条笔记），记录一次
-- 用于水位管理，确保断点续推不丢不漏
CREATE TABLE IF NOT EXISTS ima_push_batches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_seq   INTEGER NOT NULL,          -- 本批序号（按推送时间递增）
    min_ts      INTEGER NOT NULL,          -- 本批最小 ts（水位基准）
    max_ts      INTEGER NOT NULL,          -- 本批最大 ts
    note_ids    TEXT    NOT NULL,         -- JSON 数组: [note_id, ...]
    kb_results  TEXT    NOT NULL,          -- JSON 对象: {kb_id: bool}
    posted      INTEGER NOT NULL DEFAULT 0, -- 0=pending, 1=confirmed
    last_push_ts INTEGER NOT NULL,         -- 本批 max_ts（给 fetch_batch 做水位）
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S+00:00', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_push_batches_ts ON ima_push_batches(last_push_ts);
CREATE INDEX IF NOT EXISTS idx_push_batches_posted ON ima_push_batches(posted);
"""


def ensure_schema(con: sqlite3.Connection) -> None:
    """Idempotent. 在 pipeline 启动时调一次即可."""
    con.execute("PRAGMA busy_timeout = 5000")
    con.executescript(_SCHEMA_DDL)
    con.commit()

    # 2026-07-05: 迁移旧 schema (posted_to_lightrag) → 新 schema (posted)
    migrate_from_lightrag(con)


def migrate_from_lightrag(con: sqlite3.Connection) -> None:
    """把 extracted.posted_to_lightrag → extracted.posted.

    兼容逻辑:
      - 新库: posted_to_lightrag 列不存在，直接跳过
      - 老库: 有 posted_to_lightrag 列，迁移其值到 posted 列
    """
    # 检查旧列是否存在
    cols = {r[1] for r in con.execute("PRAGMA table_info(extracted)")}
    if "posted_to_lightrag" not in cols:
        return  # 新库，无须迁移

    # 迁移值
    con.execute("UPDATE extracted SET posted = posted_to_lightrag WHERE posted = 0 AND posted_to_lightrag = 1")
    con.commit()
    migrated = con.total_changes

    # 删除旧列
    indexes = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='extracted' AND sql LIKE '%posted_to_lightrag%'"
    )]
    for idx in indexes:
        con.execute(f"DROP INDEX IF EXISTS {idx}")

    with con:
        con.execute("ALTER TABLE extracted DROP COLUMN posted_to_lightrag")
        con.execute("ALTER TABLE extracted DROP COLUMN post_track_id")
        con.execute("ALTER TABLE extracted DROP COLUMN posted_at")
    con.commit()
    print(f"[migrate] moved {migrated} rows from posted_to_lightrag → posted, dropped old columns")


# ---------------------------------------------------------------------------
# HTTP 同步 (调 jcloud:9623 mycloud_proxy)
# ---------------------------------------------------------------------------

def _mp_request(url: str, username: str, password: str, *, timeout: int = 30) -> bytes:
    """urllib GET, 带 Basic Auth, 返 bytes. Retry 3 times."""
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Basic {auth}",
                "User-Agent": "mycloud_preprocess/1.0",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"mycloud_proxy GET failed after 3 retries: {url} : {last_err!r}")


def _mp_get_health(base_url: str, username: str, password: str) -> dict:
    body = _mp_request(f"{base_url}/health", username, password)
    return json.loads(body.decode("utf-8"))


def _mp_get_incremental(base_url: str, username: str, password: str,
                        since_id: int, limit: int,
                        category: str, types: str) -> list[dict]:
    qs = urllib.parse.urlencode({
        "since_id": since_id, "limit": limit,
        "category": category, "types": types,
    })
    body = _mp_request(f"{base_url}/sync/records/incremental?{qs}", username, password)
    data = json.loads(body.decode("utf-8"))
    return data.get("rows", [])


def sync_mycloud_records(
    con: sqlite3.Connection,
    *,
    base_url: str,
    username: str,
    password: str,
    category: str = "stock",
    types: str = "text,md",
    page_size: int = 5000,
    max_pages: int = 100,
) -> dict:
    base_url = base_url.rstrip("/")
    health = _mp_get_health(base_url, username, password)
    sync_total = int(health["stock_text_md_count"])
    sync_max_id = int(health["max_id"])

    pre_max_id = con.execute(
        "SELECT COALESCE(MAX(id), 0) FROM messages"
    ).fetchone()[0]

    since_id = pre_max_id
    synced = 0
    page = 0
    while page < max_pages:
        page += 1
        rows = _mp_get_incremental(base_url, username, password,
                                    since_id, page_size, category, types)
        if not rows:
            break
        with con:
            con.executemany(
                "INSERT OR IGNORE INTO messages (id, ts, kind, content, content_hash) "
                "VALUES (?, ?, ?, ?, ?)",
                [(r["id"], r["ts"], r["kind"], r["content"], r.get("content_hash"))
                 for r in rows],
            )
        synced += len(rows)
        last_id = rows[-1]["id"]
        if last_id == since_id:
            break
        since_id = last_id
        if len(rows) < page_size:
            break

    pre_total = con.execute("SELECT count(*) FROM messages").fetchone()[0]
    con.commit()

    return {
        "synced": synced,
        "preprocess_total": pre_total,
        "sync_total": sync_total,
        "pre_max_id": pre_max_id,
        "sync_max_id": sync_max_id,
        "category": category,
        "types": types,
    }


# ---------------------------------------------------------------------------
# extracted 表写入
# ---------------------------------------------------------------------------

def upsert_extracted(
    con: sqlite3.Connection,
    *,
    msg_id: int,
    ts: int,
    result,  # TaskResult from prompts.schemas
) -> None:
    """单行 UPSERT 到 extracted 主表 + 2 子表."""
    con.execute("""
        INSERT INTO extracted (msg_id, ts, info_type, category, summary, created_at)
        VALUES (?, ?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%S+00:00', 'now'))
        ON CONFLICT(msg_id) DO UPDATE SET
            ts        = excluded.ts,
            info_type = excluded.info_type,
            category  = excluded.category,
            summary   = excluded.summary
    """, (msg_id, ts, result.info_type, result.category or '', result.summary or ''))
    # stocks 子表
    con.execute("DELETE FROM extracted_stocks WHERE msg_id = ?", (msg_id,))
    for stock in (result.involved_stocks or []):
        con.execute(
            "INSERT OR IGNORE INTO extracted_stocks (msg_id, stock) VALUES (?, ?)",
            (msg_id, stock),
        )
    # terms 子表
    con.execute("DELETE FROM extracted_terms WHERE msg_id = ?", (msg_id,))
    for term in (result.core_tech_terms or []):
        con.execute(
            "INSERT OR IGNORE INTO extracted_terms (msg_id, term) VALUES (?, ?)",
            (msg_id, term),
        )


# ---------------------------------------------------------------------------
# IMA push 标记
# ---------------------------------------------------------------------------

def mark_posted_to_ima(
    con: sqlite3.Connection,
    msg_ids: list[int],
    last_push_ts: int,
) -> int:
    """IMA 推送成功后，批量更新 extracted.posted 标志。

    last_push_ts 会被记录到 ima_push_batches.last_push_ts，用于水位管理。
    """
    if not msg_ids:
        return 0
    n = 0
    for i in range(0, len(msg_ids), 1000):
        chunk = msg_ids[i:i + 1000]
        placeholders = ",".join("?" * len(chunk))
        cur = con.execute(
            f"UPDATE extracted SET posted = 1 WHERE msg_id IN ({placeholders}) AND posted = 0",
            chunk,
        )
        n += cur.rowcount
    # 更新 ima_push_batches 水位（如果存在的话）
    con.execute(
        "UPDATE ima_push_batches SET posted = 1, last_push_ts = ? WHERE last_push_ts <= ? AND posted = 0",
        (last_push_ts, last_push_ts),
    )
    con.commit()
    return n


def get_posted_msg_ids(con: sqlite3.Connection) -> set[int]:
    """返回所有 posted=1 的 msg_id 集合."""
    return {r[0] for r in con.execute(
        "SELECT msg_id FROM extracted WHERE posted = 1"
    )}


def count_unposted(con: sqlite3.Connection) -> int:
    return con.execute(
        "SELECT count(*) FROM extracted WHERE posted = 0"
    ).fetchone()[0]
