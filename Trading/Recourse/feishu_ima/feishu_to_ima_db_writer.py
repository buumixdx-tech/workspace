r"""feishu_to_ima DB writer.

本地 SQLite db: D:\WorkSpace\Trading\Recourse\feishu_ima\data\feishu_to_ima.db

数据流 (2026-06-24 重构 v3 - 干净版, 无迁移):
  - 上游表 (messages / extracted / extracted_stocks / extracted_terms) 通过 ATTACH feishu_src 读
  - 本地 4 张表:
      bucket_state   -- 单行, 复合水位 (last_ts, last_msg_id) + 全局 bucket_seq
      txt_bucket     -- TXT 文件元数据 + msg_ids_json, 含 has_msg_id 标记
      settings       -- KV 配置
      heartbeat      -- 单行状态

水位语义 (跟 feishu_preprocess 同语义):
  - watermark = (last_ts, last_msg_id): 已处理过的最后一个 msg
  - 每次只处理 feishu_src.extracted WHERE (ts, msg_id) > (last_ts, last_msg_id) AND NOT skip
  - 单事务写 txt_bucket + 推进水位, 失败回滚 -> 下次跑重做

独立 skip 规则 (不依赖 feishu_preprocess):
  - 默认 SKIP_TYPE_CODES = {4, 5, 7, 8, 9, 10}
  - 可通过环境变量 FEISHU_TO_IMA_SKIP_TYPES 覆盖 (逗号分隔整数)

msg_id 嵌入 TXT:
  - 每条 msg 块头部加 【msg_id】<id> 行
  - has_msg_id=1 标记新 TXT (可解析)
  - 历史 TXT (impossible in this clean version) has_msg_id=0 跳过 audit

bucket_seq 起步 (避免历史 220 条 ghost 撞名):
  - 起步 1000, 第一个新 TXT seq=1001
  - IMA Stock KB 已有 seq 1-216, 不会撞

Invariant A (推送完整): feishu_src.extracted - SKIP ⊆ 已上传 IMA 的 msg_ids
Invariant B (db 记载完整): IMA 端 msg_ids ⊆ 本地 txt_bucket.msg_ids_json
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# 路径配置
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
IMA_TXT_DIR = DATA_DIR / "ima_txt"
IMA_TXT_DIR.mkdir(parents=True, exist_ok=True)

FEISHU_TO_IMA_DB = str(DATA_DIR / "feishu_to_ima.db")

# 上游 feishu_preprocess.db (ATTACH 用)
# 2026-07-04 迁移: 项目根从 D:\workspace\LightRAG 搬到了 D:\WorkSpace\Trading\Recourse
FEISHU_PREPROCESS_DB = os.environ.get(
    "FEISHU_PREPROCESS_DB",
    r"D:\WorkSpace\Trading\Recourse\feishu_ext\data\preprocess.db",
)

# ---------------------------------------------------------------------------
# 独立 skip 规则 (2026-06-24 决定: 不复用 feishu_preprocess 的 SKIP_TYPE_CODES)
# ---------------------------------------------------------------------------
def _parse_skip_types() -> frozenset[int]:
    """读 env FEISHU_TO_IMA_SKIP_TYPES (逗号分隔整数). 默认 {4,5,7,8,9,10}."""
    raw = os.environ.get("FEISHU_TO_IMA_SKIP_TYPES", "").strip()
    if not raw:
        return frozenset({4, 5, 7, 8, 9, 10})
    try:
        return frozenset(int(x.strip()) for x in raw.split(",") if x.strip())
    except ValueError:
        return frozenset({4, 5, 7, 8, 9, 10})


# 模块级常量: 导入此模块时计算一次 (env 可后续修改, 调用方需 reload)
SKIP_TYPE_CODES = _parse_skip_types()

# bucket_seq 起步值 (避免跟 IMA Stock KB 历史 1-216 撞名)
INITIAL_BUCKET_SEQ = 1000


# ---------------------------------------------------------------------------
# Schema DDL (干净版, 无迁移逻辑)
# ---------------------------------------------------------------------------
_SCHEMA_DDL = """
-- 本地表 1/4: 复合水位
CREATE TABLE IF NOT EXISTS bucket_state (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    last_ts         INTEGER NOT NULL DEFAULT 0,
    last_msg_id     INTEGER NOT NULL DEFAULT 0,
    bucket_seq      INTEGER NOT NULL DEFAULT 1000,
    last_posted_at  TEXT,
    last_post_track TEXT,
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S+00:00', 'now'))
);
INSERT OR IGNORE INTO bucket_state (id, bucket_seq) VALUES (1, 1000);

-- 本地表 2/4: TXT 文件元数据
-- has_msg_id=1 标记新 TXT (头部有 【msg_id】<id> 行)
CREATE TABLE IF NOT EXISTS txt_bucket (
    txt_filename    TEXT PRIMARY KEY,
    info_type       INTEGER NOT NULL DEFAULT 0,
    category        TEXT NOT NULL DEFAULT '',
    bucket_yyyymm   TEXT NOT NULL,
    doc_count       INTEGER NOT NULL,
    msg_ids_json    TEXT NOT NULL,
    total_chars     INTEGER NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S+00:00', 'now')),
    media_id        TEXT,
    kb_id           TEXT,
    posted_at       TEXT,
    has_msg_id      INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_txt_bucket_posted ON txt_bucket(posted_at);
CREATE INDEX IF NOT EXISTS idx_txt_bucket_has_msg ON txt_bucket(has_msg_id);

-- 本地表 3/4: K-V 配置
CREATE TABLE IF NOT EXISTS settings (
    k TEXT PRIMARY KEY,
    v TEXT
);

-- 本地表 4/4: heartbeat
CREATE TABLE IF NOT EXISTS heartbeat (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    last_run_at TEXT,
    status      TEXT,
    note        TEXT
);
INSERT OR IGNORE INTO heartbeat (id, status) VALUES (1, 'idle');
"""


def ensure_schema(con: sqlite3.Connection) -> None:
    """Idempotent. 启动时调一次即可."""
    con.executescript(_SCHEMA_DDL)
    con.commit()


def connect() -> sqlite3.Connection:
    """返回 feishu_to_ima.db 的 connection (确保 schema + ATTACH 上游 db)."""
    con = sqlite3.connect(FEISHU_TO_IMA_DB, timeout=120)
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")
    con.execute("PRAGMA busy_timeout = 120000")
    ensure_schema(con)

    # ATTACH 上游 feishu_preprocess.db 作为 feishu_src schema
    if not os.path.exists(FEISHU_PREPROCESS_DB):
        raise FileNotFoundError(
            f"上游 feishu_preprocess.db 不存在: {FEISHU_PREPROCESS_DB}\n"
            f"设置 FEISHU_PREPROCESS_DB 环境变量指向正确位置."
        )
    con.execute("ATTACH DATABASE ? AS feishu_src", (FEISHU_PREPROCESS_DB,))
    con.execute("PRAGMA feishu_src.busy_timeout = 60000")
    return con


# ---------------------------------------------------------------------------
# 水位辅助
# ---------------------------------------------------------------------------
def read_bucket_state(con: sqlite3.Connection) -> tuple[int, int, int]:
    """返回 (last_ts, last_msg_id, bucket_seq). 默认 (0, 0, INITIAL_BUCKET_SEQ)."""
    row = con.execute(
        "SELECT last_ts, last_msg_id, bucket_seq FROM bucket_state WHERE id = 1"
    ).fetchone()
    if not row:
        return (0, 0, INITIAL_BUCKET_SEQ)
    return (int(row[0]), int(row[1]), int(row[2]))


def advance_bucket_state(
    con: sqlite3.Connection,
    last_ts: int,
    last_msg_id: int,
    bucket_seq: int,
    last_post_track: str | None = None,
) -> None:
    """推进水位. 单事务调用方控制."""
    con.execute(
        "UPDATE bucket_state SET last_ts=?, last_msg_id=?, bucket_seq=?, "
        "last_post_track=COALESCE(?, last_post_track), "
        "updated_at=strftime('%Y-%m-%d %H:%M:%S+00:00', 'now') "
        "WHERE id = 1",
        (last_ts, last_msg_id, bucket_seq, last_post_track),
    )


def get_msg_ids_after_watermark(
    con: sqlite3.Connection,
    last_ts: int,
    last_msg_id: int,
    skip_codes: frozenset[int] = SKIP_TYPE_CODES,
) -> list[tuple[int, int]]:
    """水位之后的候选. 返回 [(msg_id, ts), ...] 按 (ts, msg_id) ASC.

    用 SQLite row value 比较 (ts, msg_id) > (?, ?) 正确处理同 ts 的 msg_id ties.
    """
    skip_list = sorted(skip_codes)
    placeholders = ",".join("?" * len(skip_list))
    sql = (
        "SELECT msg_id, ts FROM feishu_src.extracted "
        "WHERE (ts, msg_id) > (?, ?) "
        f"  AND info_type NOT IN ({placeholders}) "
        "ORDER BY ts ASC, msg_id ASC"
    )
    params = [last_ts, last_msg_id] + skip_list
    return [(int(r[0]), int(r[1])) for r in con.execute(sql, params)]


# ---------------------------------------------------------------------------
# TXT 桶写入 (单事务)
# ---------------------------------------------------------------------------
def write_txt_bucket(
    con: sqlite3.Connection,
    txt_filename: str,
    msg_ids: list[int],
    info_type: int,
    category: str,
    bucket_yyyymm: str,
    total_chars: int,
    has_msg_id: bool = True,
) -> None:
    """写一行 txt_bucket. 调用方负责事务 (跟水位推进放在同一事务里)."""
    con.execute(
        "INSERT OR REPLACE INTO txt_bucket "
        "(txt_filename, info_type, category, bucket_yyyymm, doc_count, "
        " msg_ids_json, total_chars, has_msg_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            txt_filename,
            info_type,
            category,
            bucket_yyyymm,
            len(msg_ids),
            json.dumps(msg_ids, ensure_ascii=False),
            total_chars,
            1 if has_msg_id else 0,
        ),
    )


# ---------------------------------------------------------------------------
# 上传后 mark (upload_to_ima.py 调用)
# ---------------------------------------------------------------------------
def mark_ima_posted(
    con: sqlite3.Connection,
    txt_filename: str,
    media_id: str,
    kb_id: str,
) -> None:
    """上传 IMA 成功后更新 txt_bucket.media_id 和 posted_at."""
    with con:
        con.execute(
            "UPDATE txt_bucket SET media_id=?, kb_id=?, "
            "posted_at=strftime('%Y-%m-%d %H:%M:%S+00:00', 'now') "
            "WHERE txt_filename=?",
            (media_id, kb_id, txt_filename),
        )


def get_unuploaded_txt_files(con: sqlite3.Connection) -> list[dict]:
    """所有 posted_at IS NULL 的 TXT (待上传)."""
    return [dict(r) for r in con.execute(
        "SELECT txt_filename, doc_count, msg_ids_json FROM txt_bucket "
        "WHERE posted_at IS NULL OR posted_at = '' "
        "ORDER BY txt_filename ASC"
    )]


def get_ima_posted_msg_ids(con: sqlite3.Connection) -> set[int]:
    """返回所有已 POST 到 IMA 的 msg_id (从 posted_at IS NOT NULL 的 TXT msg_ids_json 派生)."""
    msg_ids = set()
    for r in con.execute(
        "SELECT msg_ids_json FROM txt_bucket "
        "WHERE posted_at IS NOT NULL AND posted_at != ''"
    ):
        msg_ids.update(json.loads(r[0]))
    return msg_ids


def get_msg_ids_in_txt(con: sqlite3.Connection, txt_filename: str) -> list[int]:
    """拿某 TXT 里的所有 msg_id."""
    row = con.execute(
        "SELECT msg_ids_json FROM txt_bucket WHERE txt_filename=?",
        (txt_filename,),
    ).fetchone()
    if not row:
        return []
    return json.loads(row[0])


def heartbeat(con: sqlite3.Connection, status: str, note: str = "") -> None:
    """更新 heartbeat 表."""
    with con:
        con.execute(
            "UPDATE heartbeat SET status=?, note=?, "
            "last_run_at=strftime('%Y-%m-%d %H:%M:%S+00:00', 'now') "
            "WHERE id=1",
            (status, note),
        )