"""SQLite 封装：建表、CRUD、增量迁移。"""
import sqlite3, os, time, threading

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ytlocal.db")
_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source              TEXT NOT NULL,
    source_id           TEXT NOT NULL,
    url                 TEXT NOT NULL,
    title               TEXT NOT NULL,
    channel             TEXT,
    duration_sec        INTEGER,
    thumb_path          TEXT,
    file_path           TEXT,
    size_bytes          INTEGER,
    has_zh_sub          INTEGER DEFAULT 0,
    has_en_sub          INTEGER DEFAULT 0,
    status              TEXT DEFAULT 'ready',
    created_at          INTEGER NOT NULL,
    watched_at          INTEGER,
    last_position_sec   INTEGER DEFAULT 0,
    view_count          INTEGER DEFAULT 0,
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_videos_created ON videos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_source  ON videos(source);
CREATE INDEX IF NOT EXISTS idx_videos_title   ON videos(title);

CREATE TABLE IF NOT EXISTS tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT NOT NULL,
    quality         TEXT DEFAULT '720p',
    audio_only      INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'queued',   -- queued|downloading|postproc|done|failed|canceled
    progress_pct    INTEGER DEFAULT 0,
    error           TEXT,
    video_id        INTEGER,
    created_at      INTEGER NOT NULL,
    finished_at     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tasks_status  ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);
"""


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init():
    """幂等建表 + 增量迁移。"""
    with _LOCK, _conn() as c:
        c.executescript(SCHEMA)
        # 增量字段 (对老库)
        cols = {row["name"] for row in c.execute("PRAGMA table_info(videos)").fetchall()}
        if "last_position_sec" not in cols:
            c.execute("ALTER TABLE videos ADD COLUMN last_position_sec INTEGER DEFAULT 0")
        if "view_count" not in cols:
            c.execute("ALTER TABLE videos ADD COLUMN view_count INTEGER DEFAULT 0")


# ---- videos CRUD ----
def find_by_source(source: str, source_id: str):
    with _LOCK, _conn() as c:
        row = c.execute(
            "SELECT * FROM videos WHERE source=? AND source_id=?", (source, source_id)
        ).fetchone()
        return dict(row) if row else None


def insert_video(**kw):
    kw.setdefault("created_at", int(time.time()))
    with _LOCK, _conn() as c:
        cur = c.execute(
            """INSERT INTO videos
            (source, source_id, url, title, channel, duration_sec,
             thumb_path, file_path, size_bytes, has_zh_sub, has_en_sub, status, created_at)
            VALUES (:source,:source_id,:url,:title,:channel,:duration_sec,
                    :thumb_path,:file_path,:size_bytes,:has_zh_sub,:has_en_sub,:status,:created_at)""",
            kw,
        )
        return cur.lastrowid


def update_video(vid: int, **kw):
    if not kw:
        return
    sets = ", ".join(f"{k}=:{k}" for k in kw)
    kw["id"] = vid
    with _LOCK, _conn() as c:
        c.execute(f"UPDATE videos SET {sets} WHERE id=:id", kw)


def delete_video(vid: int):
    with _LOCK, _conn() as c:
        c.execute("DELETE FROM videos WHERE id=?", (vid,))


def get_video(vid: int):
    with _LOCK, _conn() as c:
        row = c.execute("SELECT * FROM videos WHERE id=?", (vid,)).fetchone()
        return dict(row) if row else None


def list_videos(source: str = None, q: str = None, limit: int = 100, offset: int = 0):
    where, params = [], []
    if source:
        where.append("source=?"); params.append(source)
    if q:
        where.append("(title LIKE ? OR channel LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"SELECT * FROM videos {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with _LOCK, _conn() as c:
        rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def continue_watching():
    sql = """SELECT * FROM videos
             WHERE last_position_sec > 30
               AND duration_sec IS NOT NULL
               AND (duration_sec - last_position_sec) > 30
             ORDER BY watched_at DESC LIMIT 20"""
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(sql).fetchall()]


def recent_sections(per_source: int = 12):
    """每个来源最近 N 条。返回 {source: [videos]}。"""
    with _LOCK, _conn() as c:
        sources = [r["source"] for r in c.execute(
            "SELECT source FROM videos WHERE status='ready' GROUP BY source"
        ).fetchall()]
        out = {}
        for s in sources:
            rows = c.execute(
                "SELECT * FROM videos WHERE source=? ORDER BY created_at DESC LIMIT ?",
                (s, per_source),
            ).fetchall()
            if rows:
                out[s] = [dict(r) for r in rows]
        return out


def history_videos(limit: int = 200):
    sql = """SELECT * FROM videos WHERE watched_at IS NOT NULL
             ORDER BY watched_at DESC LIMIT ?"""
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(sql, (limit,)).fetchall()]


def mark_watched(vid: int, position_sec: int = 0):
    with _LOCK, _conn() as c:
        c.execute(
            """UPDATE videos SET watched_at=?, last_position_sec=?, view_count=view_count+1
               WHERE id=?""",
            (int(time.time()), int(position_sec), vid),
        )


def clear_history():
    with _LOCK, _conn() as c:
        c.execute("UPDATE videos SET watched_at=NULL, last_position_sec=0")


# ---- tasks CRUD ----
def enqueue_task(url: str, quality: str, audio_only: bool) -> int:
    with _LOCK, _conn() as c:
        cur = c.execute(
            "INSERT INTO tasks (url, quality, audio_only, created_at) VALUES (?,?,?,?)",
            (url, quality, 1 if audio_only else 0, int(time.time())),
        )
        return cur.lastrowid


def next_queued_task():
    with _LOCK, _conn() as c:
        row = c.execute(
            "SELECT * FROM tasks WHERE status='queued' ORDER BY id ASC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def update_task(tid: int, **kw):
    if not kw:
        return
    sets = ", ".join(f"{k}=:{k}" for k in kw)
    kw["id"] = tid
    with _LOCK, _conn() as c:
        c.execute(f"UPDATE tasks SET {sets} WHERE id=:id", kw)


def list_tasks(active_only: bool = False, limit: int = 50):
    sql = "SELECT * FROM tasks"
    if active_only:
        sql += " WHERE status IN ('queued','downloading','postproc')"
    sql += " ORDER BY id DESC LIMIT ?"
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(sql, (limit,)).fetchall()]


def get_task(tid: int):
    with _LOCK, _conn() as c:
        row = c.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        return dict(row) if row else None


# ---- stats ----
def stats():
    with _LOCK, _conn() as c:
        v_count = c.execute("SELECT COUNT(*) AS n FROM videos WHERE status='ready'").fetchone()["n"]
        total_size = c.execute(
            "SELECT COALESCE(SUM(size_bytes),0) AS s FROM videos WHERE status='ready'"
        ).fetchone()["s"]
        active = c.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE status IN ('queued','downloading','postproc')"
        ).fetchone()["n"]
        return {
            "video_count": v_count,
            "total_bytes": total_size,
            "active_tasks": active,
        }