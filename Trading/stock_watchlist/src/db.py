"""SQLite 数据库层：建表 + 所有 CRUD 操作。"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import sqlite3

from src.config_loader import SERVER_HOST, SERVER_PORT


# —— 数据库路径 ————————————————————————————————————————

def _db_path() -> Path:
    p = Path(__file__).resolve().parent.parent / "data" / "watchlist.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# —— 连接管理（线程安全） ————————————————————————————————

_local = threading.local()


def get_db() -> sqlite3.Connection:
    """获取线程局部的数据库连接。"""
    if not hasattr(_local, "conn"):
        conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


# —— 建表 ————————————————————————————————————————

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS stocks (
    code        TEXT PRIMARY KEY,
    exchange    TEXT NOT NULL,
    name        TEXT NOT NULL,
    board       TEXT,
    board_name  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code  TEXT NOT NULL REFERENCES stocks(code) ON DELETE CASCADE,
    title       TEXT NOT NULL DEFAULT '',
    body        TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sectors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    parent_id   INTEGER REFERENCES sectors(id) ON DELETE SET NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    color       TEXT NOT NULL DEFAULT '#6b7280',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (parent_id, name)
);

CREATE TABLE IF NOT EXISTS sector_stocks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sector_id   INTEGER NOT NULL REFERENCES sectors(id) ON DELETE CASCADE,
    stock_code  TEXT NOT NULL REFERENCES stocks(code) ON DELETE CASCADE,
    label       TEXT NOT NULL DEFAULT 'observation',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (sector_id, stock_code)
);

CREATE INDEX IF NOT EXISTS idx_notes_stock    ON notes(stock_code);
CREATE INDEX IF NOT EXISTS idx_sectors_parent ON sectors(parent_id);
CREATE INDEX IF NOT EXISTS idx_ss_sector     ON sector_stocks(sector_id);
CREATE INDEX IF NOT EXISTS idx_ss_stock      ON sector_stocks(stock_code);

CREATE TABLE IF NOT EXISTS sector_relations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_sector_id  INTEGER REFERENCES sectors(id) ON DELETE CASCADE,
    to_sector_id    INTEGER REFERENCES sectors(id) ON DELETE CASCADE,
    relation_type   TEXT NOT NULL DEFAULT 'parent',
    created_at      TEXT NOT NULL,
    UNIQUE(from_sector_id, to_sector_id, relation_type)
);
CREATE INDEX IF NOT EXISTS idx_rel_from ON sector_relations(from_sector_id);
CREATE INDEX IF NOT EXISTS idx_rel_to   ON sector_relations(to_sector_id);
"""


def init_db() -> None:
    """确保所有表存在。"""
    conn = get_db()
    conn.executescript(_INIT_SQL)
    conn.commit()
    print(f"[db] SQLite 就绪: {_db_path()}", file=sys.stderr)


# —— 辅助 ————————————————————————————————————————

def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# =============================================================================
# stocks
# =============================================================================

def upsert_stock(data: dict) -> dict:
    """插入或更新股票。data 需含 code/name/exchange。"""
    conn = get_db()
    conn.execute(
        """INSERT INTO stocks (code, exchange, name, board, board_name, updated_at)
           VALUES (:code, :exchange, :name, :board, :board_name, :updated_at)
           ON CONFLICT(code) DO UPDATE SET
               name=excluded.name, board=excluded.board,
               board_name=excluded.board_name, updated_at=excluded.updated_at""",
        {**data, "updated_at": _now()},
    )
    conn.commit()
    return get_stock(data["code"])


def get_stock(code: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM stocks WHERE code=?", (code,)).fetchone()
    return _row_to_dict(row) if row else None


def get_all_stocks() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM stocks ORDER BY code"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_watchlist_yf_codes() -> list[str]:
    """返回 watchlist 中所有 HK/US 股票 code（去重）。

    YfCache 拉取范围：sector_stocks 出现过的 HK/US 股票。
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT DISTINCT s.code
           FROM stocks s
           JOIN sector_stocks ss ON ss.stock_code = s.code
           WHERE s.exchange IN ('HK', 'US')
           ORDER BY s.code"""
    ).fetchall()
    return [r["code"] for r in rows]


def get_watchlist_a_codes() -> list[str]:
    """返回 watchlist 中所有 A 股 code（去重，CK 标准格式如 sh.600000）。

    QuoteCache 拉取范围：sector_stocks 出现过的 sh/sz/bj 股票。
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT DISTINCT s.code
           FROM stocks s
           JOIN sector_stocks ss ON ss.stock_code = s.code
           WHERE s.exchange IN ('sh', 'sz', 'bj')
           ORDER BY s.code"""
    ).fetchall()
    return [r["code"] for r in rows]


def get_sector_stocks_map() -> dict[int, list[str]]:
    """返回 {sector_id: [stock_code, ...]} 映射，包含所有有股票的板块（含子板块）。

    SectorAggregator 计算时使用, 一次性读全表避免 N+1。
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT sector_id, stock_code
           FROM sector_stocks
           ORDER BY sector_id, sort_order, stock_code"""
    ).fetchall()
    out: dict[int, list[str]] = {}
    for r in rows:
        out.setdefault(r["sector_id"], []).append(r["stock_code"])
    return out


def get_sector_stocks_map_with_labels() -> dict[int, list[tuple[str, str]]]:
    """返回 {sector_id: [(stock_code, label), ...]} 映射（带 label）。

    用于按 label 过滤的聚合指标计算。
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT sector_id, stock_code, label
           FROM sector_stocks
           ORDER BY sector_id, sort_order, stock_code"""
    ).fetchall()
    out: dict[int, list[tuple[str, str]]] = {}
    for r in rows:
        out.setdefault(r["sector_id"], []).append((r["stock_code"], r["label"]))
    return out


def get_stock_names() -> dict[str, str]:
    """返回 {code: name} 映射, 全表扫一次.

    SectorAggregator 计算时用于 top_gainers/top_losers/contributors 显示简称.
    """
    conn = get_db()
    rows = conn.execute("SELECT code, name FROM stocks").fetchall()
    return {r["code"]: r["name"] for r in rows if r["code"]}


# =============================================================================
# sectors
# =============================================================================

def create_sector(data: dict) -> dict:
    """创建板块。data: name/parent_id(s nullable)/color/sort_order"""
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO sectors (name, parent_id, sort_order, color)
           VALUES (:name, :parent_id, :sort_order, :color)""",
        {
            "name": data["name"],
            "parent_id": data.get("parent_id"),
            "sort_order": data.get("sort_order", 0),
            "color": data.get("color", "#6b7280"),
        },
    )
    sector_id = cursor.lastrowid
    # 同步写 sector_relations
    parent_id = data.get("parent_id")
    if parent_id is not None:
        conn.execute(
            """INSERT OR IGNORE INTO sector_relations
               (from_sector_id, to_sector_id, relation_type)
               VALUES (:from_id, :to_id, 'parent')""",
            {"from_id": parent_id, "to_id": sector_id},
        )
    conn.commit()
    return get_sector(sector_id)


def get_sector(sector_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM sectors WHERE id=?", (sector_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def get_child_sectors(sector_id: int) -> list[dict]:
    """返回某板块的直接子板块（按 sort_order 排序）。"""
    conn = get_db()
    rows = conn.execute(
        """SELECT s.* FROM sectors s
           JOIN sector_relations sr ON s.id = sr.to_sector_id
           WHERE sr.from_sector_id=? AND sr.relation_type='parent'
           ORDER BY s.sort_order, s.id""",
        (sector_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]



def update_sector(sector_id: int, data: dict) -> dict | None:
    """更新板块字段。data 的 key 即字段名。"""
    allowed = {"name", "parent_id", "sort_order", "color"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return get_sector(sector_id)
    fields["id"] = sector_id
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=:{k}" for k in fields)
    conn = get_db()
    # 同步更新 sector_relations（仅处理 parent_id 变化）
    if "parent_id" in fields:
        old_parent = conn.execute(
            "SELECT parent_id FROM sectors WHERE id=?", (sector_id,)
        ).fetchone()
        old_parent_id = old_parent["parent_id"] if old_parent else None
        new_parent_id = fields["parent_id"]
        # UPDATE 板块表
        conn.execute(f"UPDATE sectors SET {set_clause} WHERE id=:id", fields)
        # 同步 sector_relations：无论是否"变化"，先把该 child 的所有旧 parent 关系删干净，再插入新关系
        conn.execute(
            "DELETE FROM sector_relations WHERE to_sector_id=? AND relation_type='parent'",
            (sector_id,),
        )
        if new_parent_id is not None:
            conn.execute(
                """INSERT INTO sector_relations
                   (from_sector_id, to_sector_id, relation_type)
                   VALUES (?, ?, 'parent')""",
                (new_parent_id, sector_id),
            )
    else:
        conn.execute(f"UPDATE sectors SET {set_clause} WHERE id=:id", fields)
    conn.commit()
    return get_sector(sector_id)


def delete_sector(sector_id: int) -> bool:
    """删除板块（含级联删除子板块），不删股票。"""
    conn = get_db()
    # 递归获取所有子孙 id（基于 sector_relations）
    descendants = conn.execute(
        """WITH RECURSIVE desc_ids AS (
            SELECT id FROM sectors WHERE id=?
            UNION ALL
            SELECT sr.to_sector_id FROM sector_relations sr
            INNER JOIN desc_ids d ON sr.from_sector_id=d.id
            WHERE sr.relation_type='parent'
        )
        SELECT id FROM desc_ids""",
        (sector_id,),
    ).fetchall()
    ids = [r["id"] for r in descendants]
    if not ids:
        return False
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM sector_stocks WHERE sector_id IN ({placeholders})", ids)
    conn.execute(f"DELETE FROM sector_relations WHERE from_sector_id IN ({placeholders}) OR to_sector_id IN ({placeholders})", ids)
    conn.execute(f"DELETE FROM sectors WHERE id IN ({placeholders})", ids)
    conn.commit()
    return True


def build_sectors_tree() -> list[dict]:
    """构建完整板块树（不含股票），返回嵌套 children 列表。"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM sectors ORDER BY sort_order, id"
    ).fetchall()
    items = [_row_to_dict(r) for r in rows]
    return _nest_sectors(items, conn)


def _nest_sectors(rows: list[dict], conn) -> list[dict]:
    """将 sector rows 按 sector_relations 嵌套成树（sector_relations 是唯一真数据源）。"""
    # 初始化 children
    for row in rows:
        row["children"] = []
    lookup = {row["id"]: row for row in rows}

    # 按 sector_relations 构建父子关系
    rels = conn.execute(
        "SELECT from_sector_id, to_sector_id FROM sector_relations WHERE relation_type='parent'"
    ).fetchall()
    for rel in rels:
        parent = lookup.get(rel["from_sector_id"])
        child = lookup.get(rel["to_sector_id"])
        if parent and child:
            parent["children"].append(child)

    # 根节点：从未出现在 to_sector_id 的板块
    child_ids = {rel["to_sector_id"] for rel in rels}
    roots = [row for row in rows if row["id"] not in child_ids]
    roots.sort(key=lambda r: (r["sort_order"], r["id"]))

    def sort_children(nodes):
        nodes.sort(key=lambda n: (n["sort_order"], n["id"]))
        for node in nodes:
            if node["children"]:
                sort_children(node["children"])

    sort_children(roots)
    return roots


def get_sector_stocks(sector_id: int) -> list[dict]:
    """返回某板块直接关联的股票（含 label）。"""
    conn = get_db()
    rows = conn.execute(
        """SELECT ss.*, s.name, s.exchange, s.board, s.board_name
           FROM sector_stocks ss
           JOIN stocks s ON s.code = ss.stock_code
           WHERE ss.sector_id=?
           ORDER BY ss.sort_order, ss.id""",
        (sector_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_descendant_sector_ids(sector_id: int) -> list[int]:
    """递归获取某板块的所有子孙 sector_id（含自身，基于 sector_relations）。"""
    conn = get_db()
    rows = conn.execute(
        """WITH RECURSIVE desc_ids AS (
            SELECT id FROM sectors WHERE id=?
            UNION ALL
            SELECT sr.to_sector_id FROM sector_relations sr
            INNER JOIN desc_ids d ON sr.from_sector_id=d.id
            WHERE sr.relation_type='parent'
        )
        SELECT id FROM desc_ids""",
        (sector_id,),
    ).fetchall()
    return [r["id"] for r in rows]


def get_aggregated_stocks(sector_id: int) -> list[dict]:
    """父板块展示时，递归聚合所有子孙层级的股票（仅 core/focus）。"""
    ids = get_descendant_sector_ids(sector_id)
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    conn = get_db()
    rows = conn.execute(
        f"""SELECT ss.*, s.name, s.exchange, s.board, s.board_name
            FROM sector_stocks ss
            JOIN stocks s ON s.code = ss.stock_code
            WHERE ss.sector_id IN ({placeholders})
              AND ss.label IN ('core', 'focus')
            ORDER BY ss.sort_order, ss.id""",
        ids,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


# =============================================================================
# sector_stocks
# =============================================================================

def add_stock_to_sector(sector_id: int, stock_code: str, label: str = "observation") -> dict:
    """将股票关联到板块。一只股可属于多个板块，直接追加。"""
    from src.core import normalize_code_ck
    stock_code = normalize_code_ck(stock_code)
    conn = get_db()
    conn.execute(
        """INSERT INTO sector_stocks (sector_id, stock_code, label, updated_at)
           VALUES (:sector_id, :stock_code, :label, :updated_at)
           ON CONFLICT(sector_id, stock_code) DO UPDATE SET label=excluded.label, updated_at=excluded.updated_at""",
        {"sector_id": sector_id, "stock_code": stock_code, "label": label, "updated_at": _now()},
    )
    conn.commit()
    row = conn.execute(
        """SELECT ss.*, s.name, s.exchange, s.board, s.board_name
           FROM sector_stocks ss
           JOIN stocks s ON s.code = ss.stock_code
           WHERE ss.sector_id=? AND ss.stock_code=?""",
        (sector_id, stock_code),
    ).fetchone()
    return _row_to_dict(row) if row else None


def update_sector_stock(sector_id: int, stock_code: str, data: dict) -> dict | None:
    """更新关联记录：label / sort_order。"""
    allowed = {"label", "sort_order"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return None
    fields["sector_id"] = sector_id
    fields["stock_code"] = stock_code
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=:{k}" for k in fields)
    conn = get_db()
    conn.execute(
        f"UPDATE sector_stocks SET {set_clause} "
        "WHERE sector_id=:sector_id AND stock_code=:stock_code",
        fields,
    )
    conn.commit()
    row = conn.execute(
        """SELECT ss.*, s.name, s.exchange, s.board, s.board_name
           FROM sector_stocks ss
           JOIN stocks s ON s.code = ss.stock_code
           WHERE ss.sector_id=? AND ss.stock_code=?""",
        (sector_id, stock_code),
    ).fetchone()
    return _row_to_dict(row) if row else None


def reorder_sector_stocks(sector_id: int, ordered_codes: list[str]) -> None:
    """批量更新同一板块内个股的 sort_order。

    ordered_codes 按期望顺序排列，前端传来拖动后的完整列表。
    sort_order 分配：0, 1024, 2048… 留足插入空间。
    """
    conn = get_db()
    for i, code in enumerate(ordered_codes):
        conn.execute(
            "UPDATE sector_stocks SET sort_order=?, updated_at=? WHERE sector_id=? AND stock_code=?",
            (i * 1024, _now(), sector_id, code),
        )
    conn.commit()


def remove_stock_from_sector(sector_id: int, stock_code: str) -> bool:
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM sector_stocks WHERE sector_id=? AND stock_code=?",
        (sector_id, stock_code),
    )
    conn.commit()
    return cursor.rowcount > 0


# =============================================================================
# notes
# =============================================================================

def create_note(stock_code: str, data: dict) -> dict:
    """创建笔记。data: title/body/tags(list)"""
    tags_json = json.dumps(data.get("tags", []), ensure_ascii=False)
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO notes (stock_code, title, body, tags)
           VALUES (:stock_code, :title, :body, :tags)""",
        {
            "stock_code": stock_code,
            "title": data.get("title", ""),
            "body": data.get("body", ""),
            "tags": tags_json,
        },
    )
    conn.commit()
    return get_note(cursor.lastrowid)


def get_note(note_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
    if not row:
        return None
    d = _row_to_dict(row)
    d["tags"] = json.loads(d.get("tags", "[]"))
    return d


def get_notes_for_stock(stock_code: str) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notes WHERE stock_code=? ORDER BY updated_at DESC",
        (stock_code,),
    ).fetchall()
    results = []
    for row in rows:
        d = _row_to_dict(row)
        d["tags"] = json.loads(d.get("tags", "[]"))
        results.append(d)
    return results


def get_notes_for_sector(sector_id: int) -> dict[str, list[dict]]:
    """返回某板块(含子板块)所有股票的笔记,按 stock_code 索引。

    用于前端切板块时一次性拉全 — 单条 SQL 走 idx_notes_stock 索引。
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT n.* FROM notes n
           WHERE n.stock_code IN (
             SELECT DISTINCT stock_code FROM sector_stocks
             WHERE sector_id IN (
               WITH RECURSIVE descendants(id) AS (
                 SELECT id FROM sectors WHERE id = ?
                 UNION
                 SELECT s.id FROM sectors s JOIN descendants d ON s.parent_id = d.id
               )
               SELECT id FROM descendants
             )
           )
           ORDER BY n.updated_at DESC""",
        (sector_id,),
    ).fetchall()
    out: dict[str, list[dict]] = {}
    for row in rows:
        d = _row_to_dict(row)
        d["tags"] = json.loads(d.get("tags", "[]"))
        out.setdefault(d["stock_code"], []).append(d)
    return out


def update_note(note_id: int, data: dict) -> dict | None:
    """更新笔记：title / body / tags(list)。"""
    fields = {}
    if "title" in data:
        fields["title"] = data["title"]
    if "body" in data:
        fields["body"] = data["body"]
    if "tags" in data:
        fields["tags"] = json.dumps(data["tags"], ensure_ascii=False)
    if not fields:
        return get_note(note_id)
    fields["id"] = note_id
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k}=:{k}" for k in fields)
    conn = get_db()
    conn.execute(f"UPDATE notes SET {set_clause} WHERE id=:id", fields)
    conn.commit()
    return get_note(note_id)


def delete_note(note_id: int) -> bool:
    conn = get_db()
    cursor = conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
    conn.commit()
    return cursor.rowcount > 0


# —— Extended queries ————————————————————————————————————

def get_stock_sectors(stock_code: str) -> list[dict]:
    """返回某股票所属的全部板块（含板块信息）。"""
    conn = get_db()
    rows = conn.execute(
        """SELECT s.* FROM sectors s
           JOIN sector_stocks ss ON s.id = ss.sector_id
           WHERE ss.stock_code = ?
           ORDER BY s.sort_order, s.id""",
        (stock_code,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def move_stock_sector(stock_code: str, from_sector_id: int, to_sector_id: int, label: str = "observation") -> dict | None:
    """将股票从源板块移到目标板块。

    如果 from_sector_id == to_sector_id，则无操作返回 None。
    目标板块中没有这只股票则添加（UPSERT），有则更新 label。
    返回目标板块中的关联记录。
    """
    if from_sector_id == to_sector_id:
        return update_sector_stock(to_sector_id, stock_code, {"label": label})
    conn = get_db()
    # 从源板块移除
    conn.execute(
        "DELETE FROM sector_stocks WHERE sector_id=? AND stock_code=?",
        (from_sector_id, stock_code),
    )
    # 到目标板块 UPSERT
    conn.execute(
        """INSERT INTO sector_stocks (sector_id, stock_code, label, updated_at)
           VALUES (:sector_id, :stock_code, :label, :updated_at)
           ON CONFLICT(sector_id, stock_code) DO UPDATE SET label=excluded.label, updated_at=excluded.updated_at""",
        {"sector_id": to_sector_id, "stock_code": stock_code, "label": label, "updated_at": _now()},
    )
    conn.commit()
    row = conn.execute(
        """SELECT ss.*, s.name, s.exchange, s.board, s.board_name
           FROM sector_stocks ss
           JOIN stocks s ON s.code = ss.stock_code
           WHERE ss.sector_id=? AND ss.stock_code=?""",
        (to_sector_id, stock_code),
    ).fetchone()
    return _row_to_dict(row) if row else None


def batch_add_stocks(sector_id: int, stocks: list[dict]) -> list[dict]:
    """批量添加多只股票到同一板块。stocks: [{stock_code, label}, ...]

    返回添加后该板块的全部关联记录。
    """
    from src.core import normalize_code_ck
    conn = get_db()
    now = _now()
    results = []
    for item in stocks:
        code = normalize_code_ck(str(item.get("stock_code", "")))
        label = item.get("label", "observation")
        if not code:
            continue
        conn.execute(
            """INSERT INTO sector_stocks (sector_id, stock_code, label, updated_at)
               VALUES (:sector_id, :stock_code, :label, :updated_at)
               ON CONFLICT(sector_id, stock_code) DO UPDATE SET label=excluded.label, updated_at=excluded.updated_at""",
            {"sector_id": sector_id, "stock_code": code, "label": label, "updated_at": now},
        )
    conn.commit()
    rows = conn.execute(
        """SELECT ss.*, s.name, s.exchange, s.board, s.board_name
           FROM sector_stocks ss
           JOIN stocks s ON s.code = ss.stock_code
           WHERE ss.sector_id=?
           ORDER BY ss.sort_order, ss.id""",
        (sector_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_notes_for_stock(stock_code: str) -> int:
    """删除某股票的全部笔记，返回删除数量。"""
    conn = get_db()
    cursor = conn.execute("DELETE FROM notes WHERE stock_code=?", (stock_code,))
    conn.commit()
    return cursor.rowcount


def move_note_to_stock(note_id: int, target_stock_code: str) -> dict | None:
    """将笔记移动到另一股票。stock 必须已存在。"""
    conn = get_db()
    row = conn.execute("SELECT stock_code FROM notes WHERE id=?", (note_id,)).fetchone()
    if not row:
        return None
    stock_code = row["stock_code"]
    conn.execute(
        "UPDATE notes SET stock_code=?, updated_at=? WHERE id=?",
        (target_stock_code, _now(), note_id),
    )
    conn.commit()
    return get_note(note_id)
