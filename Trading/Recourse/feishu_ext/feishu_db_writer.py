"""feishu_preprocess DB writer.

Owns the lifecycle of preprocess.db (/root/rag_preprocess/data/preprocess.db):
  - messages 表: 从 feishu_sync.messages.db 镜像 (ATTACH + INSERT 增量同步)
  - extracted / extracted_stocks / extracted_terms: preprocess 拥有

feishu_sync 完全不感知 preprocess.db; preprocess 自己建、自己同步、自己写.

2026-06-21 架构变化:
  - 老库: messages 用隐式 rowid (SQLite 会复用删除后留下的空号)
  - 新库: messages 用显式 id INTEGER PRIMARY KEY AUTOINCREMENT (永不复用)
  - 迁移函数: migrate_messages_id_column(con) -- 老库首跑自动加列
  - 上游路径: SYNC_MESSAGES_DB 环境变量 (默认 jcloud 绝对路径, 无软链接)

下游引用: extracted.msg_id 和 extracted_stocks / extracted_terms 都引用 messages.id,
数值与历史 rowid 一致, 30w 滚动删除场景下不会指错.

列名重命名 (msg_rowid → msg_id):
  - extracted / extracted_stocks / extracted_terms 表的 msg_rowid 列改名为 msg_id
  - 数值含义不变 (= messages.id), 只是去掉误导性的 "rowid" 字样
  - 迁移函数: migrate_extracted_rename_msg_id(con) -- 老库首跑自动 RENAME COLUMN

Functions:
  ensure_schema(con)              -- idempotent CREATE TABLE IF NOT EXISTS
  migrate_messages_id_column(con) -- 老库 (无 id 列) → 新库 (AUTOINCREMENT)
  migrate_extracted_rename_msg_id(con) -- 老库 (msg_rowid) → 新库 (msg_id)
  sync_messages_from(con, src)    -- ATTACH sync.messages.db + INSERT 新消息
  sync_messages_from_remote(...)  -- HTTP 增量同步 (远端 jcloud)
  upsert_extracted(...)           -- single-row UPSERT (主表 + 2 子表)
  iter_unprocessed(...)           -- yield (msg_id, ts, content) of unprocessed text rows
"""
from __future__ import annotations

import sqlite3
import urllib.request
import urllib.parse
import base64
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# schema DDL (preprocess 私有表)
# ---------------------------------------------------------------------------

# messages 表 schema 必须跟 feishu_sync.messages 完全一致:
#   sync 端是 (id INTEGER PRIMARY KEY AUTOINCREMENT,
#              ts INTEGER NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL, content_hash TEXT)
#   id 显式 AUTOINCREMENT，永不复用；extracted.msg_id 和 extracted_stocks/terms 都引用它
# preprocess 端是 mirror, INSERT FROM sync_db.messages, 不写不更新.
#
# extracted.msg_id 列名（不是 msg_rowid，避免跟 SQLite 隐式 rowid 混淆）；
# 数值含义 = messages.id，与历史 rowid 数值一致。
_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           INTEGER NOT NULL,
    kind         TEXT    NOT NULL,
    content      TEXT    NOT NULL,
    content_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts);

CREATE TABLE IF NOT EXISTS extracted (
    msg_id             INTEGER PRIMARY KEY,
    ts                 INTEGER NOT NULL,
    -- 2026-06-23 拍板: info_type 从 TEXT (中文) 改为 INTEGER (1-10 code).
    -- 单源映射见 prompts.schemas.INFO_TYPE_CODES.
    info_type          INTEGER NOT NULL DEFAULT 10,
    category           TEXT    NOT NULL DEFAULT '',
    summary            TEXT    NOT NULL DEFAULT '',
    -- TZ FIX 2026-06-22: datetime('now') returns UTC, but we want to mark timezone explicitly
    -- so downstream consumers (dashboard, push_state, ops) parse correctly. Format: 'YYYY-MM-DD HH:MM:SS+00:00'.
    created_at         TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S+00:00', 'now'))
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
"""


def ensure_schema(con: sqlite3.Connection) -> None:
    """Idempotent. 在 pipeline / demo 启动时调一次即可.

    注意: 仅对不存在的表 CREATE IF NOT EXISTS,不会对已存在的表加列。
    老库需要先调用 migrate_messages_id_column() / migrate_extracted_rename_msg_id()。
    """
    # busy_timeout: 锁竞争时等 5s 再抛错, 防止 sync/search/preprocess 三方并发时崩
    con.execute("PRAGMA busy_timeout = 5000")
    con.executescript(_SCHEMA_DDL)
    con.commit()


def migrate_messages_id_column(con: sqlite3.Connection) -> bool:
    """老库（messages 表无 id 列）升级为带 id INTEGER PRIMARY KEY AUTOINCREMENT。

    与 feishu_sync.store._migrate_id_column 同思路: "建新表 + 倒数据 + 改名" 三步走。

    preprocess.messages 镜像来自 sync.messages, 但 preprocess 还有自己的 extracted 3 表,
    这些表的 msg_id 列存的是 messages.id（AUTOINCREMENT 后与 rowid 数值一致）。

    迁移保证 id == 老 rowid 数值, 这样 extracted.msg_id 引用全部保持有效.

    返回: True 表示做了迁移, False 表示已是新 schema 或迁移被跳过。

    迁移可重入: 检测到 id 列已存在直接返回 False。
    """
    cols = {row[1] for row in con.execute("PRAGMA table_info(messages)")}
    if "id" in cols:
        return False

    # 老 schema: messages(ts, kind, content, content_hash) + 隐式 rowid
    # 新 schema: messages(id, ts, kind, content, content_hash) + 显式 AUTOINCREMENT id
    with con:  # 自动事务
        con.execute("ALTER TABLE messages RENAME TO messages_legacy")
        con.execute("""
            CREATE TABLE messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ts           INTEGER NOT NULL,
                kind         TEXT    NOT NULL,
                content      TEXT    NOT NULL,
                content_hash TEXT
            )
        """)
        con.execute("""
            INSERT INTO messages (id, ts, kind, content, content_hash)
            SELECT rowid, ts, kind, content, content_hash
            FROM messages_legacy
        """)
        con.execute("DROP TABLE messages_legacy")
        con.execute("CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts)")
    return True


def migrate_extracted_rename_msg_id(con: sqlite3.Connection) -> bool:
    """老库（extracted / 子表用 msg_rowid 列名）→ 新库（msg_id 列名）。

    SQLite 3.25+ 原生支持 ALTER TABLE ... RENAME COLUMN, 一次事务里 3 张表全改。
    数值含义不变, 只是列名变化. 配合 migrate_messages_id_column 一起做完整迁移.

    触发时机: 任何 msg_rowid 列还存在的时候, 自动 RENAME COLUMN. 全部已改名后跳过.

    行为:
      - 检测到 extracted.msg_rowid → RENAME COLUMN msg_rowid TO msg_id
      - 检测到 extracted_stocks.msg_rowid → 同上
      - 检测到 extracted_terms.msg_rowid → 同上
      - 3 张表都改完后返回 True; 任何一张没改返回 False
    """
    targets = ["extracted", "extracted_stocks", "extracted_terms"]
    changed_any = False
    for table in targets:
        cols = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
        if "msg_rowid" not in cols:
            continue
        # 用 RENAME COLUMN 走 SQLite 原子操作, 不需要重导数据
        con.execute(f"ALTER TABLE {table} RENAME COLUMN msg_rowid TO msg_id")
        changed_any = True
    if changed_any:
        con.commit()
    return changed_any


def migrate_info_type_text_to_int(con: sqlite3.Connection) -> dict:
    """2026-06-23 拍板: 把 extracted.info_type 从 TEXT (中文) 迁到 INTEGER (1-10 code).

    迁移原理:
      1. 检测当前 schema, info_type 已是 INTEGER 就 skip (return changed=False)
      2. 加临时列 info_type_int
      3. UPDATE 反查 (用 prompts.schemas.INFO_TYPE_CODES)
      4. 验证: 找出所有反查不到的 (中文不在 dict 里) — 记为 unmapped
      5. 如果 unmapped 为空: 删 TEXT 列, 重命名 int 列
         如果 unmapped 非空: raise RuntimeError (让运维手动处理: fallback 到 10 还是报错?)
    6. CREATE INDEX on info_type

    返回: {"changed": bool, "total_rows": int, "mapped": int, "unmapped": list[str]}
    """
    # 1. 检测
    cols = {row[1] for row in con.execute("PRAGMA table_info(extracted)")}
    if "info_type" not in cols:
        raise RuntimeError("extracted 表没有 info_type 列, 无法迁移")
    # 看类型
    info_type_def = next(row for row in con.execute("PRAGMA table_info(extracted)") if row[1] == "info_type")
    if info_type_def[2].upper() == "INTEGER":
        return {"changed": False, "total_rows": 0, "mapped": 0, "unmapped": []}

    # 2. 加临时列
    con.execute("ALTER TABLE extracted ADD COLUMN info_type_int INTEGER")

    # 3. UPDATE 反查
    # import in function to avoid cycle
    import sys
    _f2i_root = Path(__file__).resolve().parent
    if str(_f2i_root) not in sys.path:
        sys.path.insert(0, str(_f2i_root))
    from prompts.schemas import INFO_TYPE_CODES, CODE_TO_LABELS  # noqa: E402

    total = con.execute("SELECT COUNT(*) FROM extracted").fetchone()[0]
    mapped = 0
    for label, code in INFO_TYPE_CODES.items():
        n = con.execute("UPDATE extracted SET info_type_int = ? WHERE info_type = ?", (code, label)).rowcount
        mapped += n

    # 4. unmapped 检查
    unmapped_rows = con.execute(
        "SELECT DISTINCT info_type FROM extracted WHERE info_type_int IS NULL"
    ).fetchall()
    unmapped = [r[0] for r in unmapped_rows if r[0] is not None]

    # 防御性: LLM 偶尔会输出 "其他" 等带空格/换行的, 修剪后再试一次
    if unmapped:
        for bad_label in list(unmapped):
            stripped = bad_label.strip()
            if stripped in INFO_TYPE_CODES:
                con.execute("UPDATE extracted SET info_type_int = ? WHERE info_type = ?", (INFO_TYPE_CODES[stripped], bad_label))
                mapped += 1
                unmapped.remove(bad_label)
        con.commit()

    if unmapped:
        # 不报错, fallback 到 10 (其他) 然后警告; 运维可以选择重跑
        # 但这样不严格; 还是报错让用户决策
        con.execute(
            "UPDATE extracted SET info_type_int = 10 WHERE info_type_int IS NULL"
        )
        # commit + 报警
        con.commit()
        print(f"⚠️ migrate_info_type_text_to_int: {len(unmapped)} 个 info_type 未在映射表, fallback 到 code=10 (其他):")
        for u in unmapped:
            print(f"   - '{u}'")

    # 5. SQLite 不支持 DROP COLUMN, 要重建表
    # 2026-06-23: 用 SQLite 3.35+ 的 ALTER TABLE DROP COLUMN (已验证可用)
    # 实际上 SQLite 3.35.0 (2021-03-12) 起支持 DROP COLUMN. Python 3.13 默认带 SQLite ≥ 3.40+
    # 防御: DROP COLUMN 之前先把依赖该列的索引 drop 掉 (SQLite 会拒绝其他).
    indexes_on_info_type = [
        r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='extracted' AND sql LIKE '%info_type%'"
        )
    ]
    for idx_name in indexes_on_info_type:
        con.execute(f"DROP INDEX IF EXISTS {idx_name}")
    with con:
        con.execute("ALTER TABLE extracted DROP COLUMN info_type")
        con.execute("ALTER TABLE extracted RENAME COLUMN info_type_int TO info_type")

    # 6. 加索引
    con.execute("CREATE INDEX IF NOT EXISTS idx_extracted_info_type ON extracted(info_type)")
    con.commit()

    return {
        "changed": True,
        "total_rows": total,
        "mapped": mapped,
        "unmapped": unmapped,
    }


# ---------------------------------------------------------------------------
# sync mirror: 从 feishu_sync.messages.db ATTACH + 增量同步到 preprocess.messages
# ---------------------------------------------------------------------------

def sync_messages_from(con: sqlite3.Connection, src_path: str) -> dict:
    """从 sync.messages.db ATTACH, 把新消息增量同步到 preprocess.messages.

    增量水位: preprocess.messages.id > (sync.messages.id 中的最大值).
    用 LEFT JOIN 跳过已存在的（理论上同 id 必同步相同内容, 但 JOIN 防御更稳）.

    注意: 这里用 id 做增量条件, 因为 sync.messages 的 id 是 AUTOINCREMENT 严格单调.
    """
    # ATTACH sync db
    cur = con.execute("ATTACH DATABASE ? AS sync_db", (src_path,))
    try:
        # 1. 拿 sync 的 max id
        sync_max_id = con.execute("SELECT COALESCE(MAX(id), 0) FROM sync_db.messages").fetchone()[0]
        # 2. 拿 preprocess 的 max id
        pre_max_id = con.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]
        # 3. 增量同步: 同步 sync_max_id - pre_max_id 区间内的新消息
        if sync_max_id > pre_max_id:
            con.execute("""
                INSERT INTO messages (id, ts, kind, content, content_hash)
                SELECT id, ts, kind, content, content_hash
                FROM sync_db.messages
                WHERE id > ?
            """, (pre_max_id,))
        # 4. 统计
        pre_total = con.execute("SELECT count(*) FROM messages").fetchone()[0]
        sync_total = con.execute("SELECT count(*) FROM sync_db.messages").fetchone()[0]
        synced = pre_total - (pre_max_id - 0)  # 简化统计
        con.commit()
    finally:
        con.execute("DETACH DATABASE sync_db")
    return {
        "synced": max(sync_max_id - pre_max_id, 0),
        "preprocess_total": pre_total,
        "sync_total": sync_total,
        "pre_max_id": pre_max_id,
        "sync_max_id": sync_max_id,
    }


def sync_messages_from_remote(
    con: sqlite3.Connection,
    *,
    base_url: str,
    username: str,
    password: str,
    page_size: int = 5000,
    max_pages: int = 100,
) -> dict:
    """走 jcloud 上的 messages_proxy HTTP 接口, 增量同步到 preprocess.messages.

    原理: 调 GET {base_url}/sync/messages/incremental?since_id=N&limit=M
    按 id ASC 返回 since_id<N 的 M 行, 我们拿 max(rows.id) 当下一轮的 since_id.
    循环到 rows 为空 or 翻到 max_pages.

    返回 dict 跟 sync_messages_from 一致:
      {synced, preprocess_total, sync_total (estimate), pre_max_id, sync_max_id}

    sync_total / sync_max_id 从 /health 拿, 避免多次调用.

    Requirements:
      - messages_proxy 路径: /sync/messages/incremental
      - 认证: HTTP Basic Auth (nginx 反代侧也套了认证, 这里送一次足够)
      - 网络: 容忍偶发 ConnectionError (重试 3 次)
    """
    base_url = base_url.rstrip("/")

    # 1. 先 /health 拿 sync_total / sync_max_id
    sync_total, sync_max_id = _mp_get_health(base_url, username, password)

    # 2. 当前 preprocess 端水位
    pre_max_id = con.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]

    # 3. 翻页增量
    since_id = pre_max_id
    synced = 0
    page = 0
    while page < max_pages:
        page += 1
        rows = _mp_get_incremental(base_url, username, password, since_id, page_size)
        if not rows:
            break
        # batch insert
        with con:
            con.executemany(
                "INSERT OR IGNORE INTO messages (id, ts, kind, content, content_hash) "
                "VALUES (?, ?, ?, ?, ?)",
                [(r["id"], r["ts"], r["kind"], r["content"], r.get("content_hash")) for r in rows],
            )
        synced += len(rows)
        # rows 按 id ASC, 最后一条就是 max
        last_id = rows[-1]["id"]
        if last_id == since_id:
            # 服务端可能卡了（不该发生），跳过防死循环
            break
        since_id = last_id
        if len(rows) < page_size:
            break  # 最后一页

    # 4. 统计
    pre_total = con.execute("SELECT count(*) FROM messages").fetchone()[0]
    con.commit()

    return {
        "synced": synced,
        "preprocess_total": pre_total,
        "sync_total": sync_total,
        "pre_max_id": pre_max_id,
        "sync_max_id": sync_max_id,
    }


def _mp_request(url: str, username: str, password: str, *, timeout: int = 30):
    """urllib GET, 带 Basic Auth, 返 bytes. Retry 3 times."""
    import time
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Basic {auth}",
                "User-Agent": "feishu_preprocess/1.0",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"messages_proxy GET failed after 3 retries: {url} : {last_err!r}")


def _mp_get_health(base_url: str, username: str, password: str) -> tuple[int, int]:
    """GET /health. return (messages_count, max_id)."""
    body = _mp_request(f"{base_url}/health", username, password)
    data = json.loads(body.decode("utf-8"))
    return int(data["messages_count"]), int(data["max_id"])


def _mp_get_incremental(base_url: str, username: str, password: str,
                         since_id: int, limit: int) -> list[dict]:
    """GET /sync/messages/incremental?since_id=N&limit=M. return list of row dicts."""
    qs = urllib.parse.urlencode({"since_id": since_id, "limit": limit})
    body = _mp_request(f"{base_url}/sync/messages/incremental?{qs}", username, password)
    data = json.loads(body.decode("utf-8"))
    return data.get("rows", [])


# ---------------------------------------------------------------------------
# extracted 表写入 (LLM 抽取结果 UPSERT)
# ---------------------------------------------------------------------------

def upsert_extracted(
    con: sqlite3.Connection,
    *,
    msg_id: int,
    ts: int,
    result,  # TaskResult from prompts.schemas, no type hint to avoid import cycle
) -> None:
    """单行 UPSERT 到 extracted 主表 + 2 子表.

    ON CONFLICT(msg_id) DO UPDATE: 重复抽取的同一条消息用最新结果覆盖.
    子表 (extracted_stocks / extracted_terms) 先 DELETE 再 INSERT, 避免残留旧词.
    """
    # TZ FIX 2026-06-22: pass created_at explicitly (DEFAULT only applies to new tables, not existing schema)
    # 2026-06-23: result.info_type 是 int (1-10), 直接存. 防御性 fallback 到 10 (其他).
    import sys
    _root = Path(__file__).resolve().parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from prompts.schemas import INFO_TYPE_CODES  # noqa: E402

    # 兼容老 caller (中文 result.info_type) — 反查; 查不到 fallback 10
    raw = result.info_type
    if isinstance(raw, int):
        info_type_code = raw
    elif isinstance(raw, str):
        info_type_code = INFO_TYPE_CODES.get(raw.strip(), 10)
    else:
        info_type_code = 10

    con.execute("""
        INSERT INTO extracted (msg_id, ts, info_type, category, summary, created_at)
        VALUES (?, ?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%S+00:00', 'now'))
        ON CONFLICT(msg_id) DO UPDATE SET
            ts        = excluded.ts,
            info_type = excluded.info_type,
            category  = excluded.category,
            summary   = excluded.summary
    """, (msg_id, ts, info_type_code, result.category or '', result.summary or ''))
    # 子表: stocks
    con.execute("DELETE FROM extracted_stocks WHERE msg_id = ?", (msg_id,))
    for stock in (result.involved_stocks or []):
        con.execute(
            "INSERT OR IGNORE INTO extracted_stocks (msg_id, stock) VALUES (?, ?)",
            (msg_id, stock),
        )
    # 子表: terms
    con.execute("DELETE FROM extracted_terms WHERE msg_id = ?", (msg_id,))
    for term in (result.core_tech_terms or []):
        con.execute(
            "INSERT OR IGNORE INTO extracted_terms (msg_id, term) VALUES (?, ?)",
            (msg_id, term),
        )


# ---------------------------------------------------------------------------
# iter: 给 preprocess pipeline 找未处理的 text 行
# ---------------------------------------------------------------------------

def iter_unprocessed(con: sqlite3.Connection, *, safety_max_items: int = 500):
    """yield (msg_id, ts, content) of unprocessed text rows.

    主水位: ts > (SELECT MAX(ts) FROM extracted)
    次保护: LEFT JOIN extracted, e.rowid IS NULL 表示还没处理.
    用 m.id 不用 m.rowid: id 是显式 AUTOINCREMENT, 永不复用.
    排序按 m.ts ASC (跟业务时间线一致).
    """
    cursor_ts = con.execute("SELECT COALESCE(MAX(ts), 0) FROM extracted").fetchone()[0]
    for row in con.execute("""
        SELECT m.id, m.ts, m.content FROM messages m
        LEFT JOIN extracted e ON m.id = e.msg_id
        WHERE m.kind = 't' AND length(m.content) > 10
          AND m.ts > ?
          AND e.rowid IS NULL
        ORDER BY m.ts ASC LIMIT ?
    """, (cursor_ts, safety_max_items)):
        # rowid IS NULL 是 SQLite 标准 LEFT JOIN 模式, 跟 msg_id 列名无关, 不能改
        yield int(row[0]), int(row[1]), row[2]
