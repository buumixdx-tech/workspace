"""feishu_ext 定时任务 wrapper — 按时间段控制执行频率。

调度策略:
  Mon-Fri 08:00-19:00:  5 分钟粒度  → Task Scheduler Feishu_ext_5m 驱动
  Mon-Fri 19:00-08:00:  60 分钟粒度 → Task Scheduler Feishu_ext_60m 驱动
  Sat-Sun 全天:         60 分钟粒度 → Task Scheduler Feishu_ext_60m 驱动

原理:
  两个 Task Scheduler 任务共用同一个 wrapper，
  wrapper 根据当前时间判断是否真正执行，跳过时直接返回 0（无声退出）。

无窗口: pythonw 运行，输出重定向到 NUL（Task Scheduler Action 已配置）。
"""
from __future__ import annotations

import os
import sys
import json
import time
import sqlite3
import datetime
import urllib.request
import base64
from pathlib import Path

# ------------------------------------------------------------------ #
# 路径定义                                                            #
# ------------------------------------------------------------------ #

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
DB = DATA_DIR / "preprocess.db"
IMA_DB = HERE.parent / "feishu_ima" / "data" / "feishu_to_ima.db"
STATE_FILE = DATA_DIR / "last_run.json"
LOG_DIR = HERE.parent / "logs"
LOG_FILE = LOG_DIR / "feishu_ext_wrapper.log"

# env defaults: Task Scheduler 以 SYSTEM 运行时读不到用户环境变量，
# 在这里 setdefault 确保 pipeline 能拿到 key
os.environ.setdefault("DASHSCOPE_API_KEY", "sk-c5a451bf49e14da4929a0fc722242e13")
os.environ.setdefault("REMOTE_FEISHU_MESSAGES_URL", "https://buumicloud.com.cn/rag-messages-api")
os.environ.setdefault("REMOTE_FEISHU_MESSAGES_USER", "buumi")
os.environ.setdefault("REMOTE_FEISHU_MESSAGES_PASS", "xdxis1234")

# ------------------------------------------------------------------ #
# 时间 / 日程判断                                                     #
# ------------------------------------------------------------------ #

TZ_OFFSET = datetime.timezone(datetime.timedelta(hours=8))


def _now() -> datetime.datetime:
    return datetime.datetime.now(TZ_OFFSET)


def _weekday() -> int:
    """0=Mon, 6=Sun"""
    return _now().weekday()


def _is_weekday() -> bool:
    return _weekday() < 5


def _is_in_business_hours() -> bool:
    """Mon-Fri 08:00-19:00"""
    if not _is_weekday():
        return False
    h = _now().hour
    return 8 <= h < 19


def _should_run() -> bool:
    """判断本次是否真正执行主管道。"""
    state = _load_state()
    last_run_ts: float | None = state.get("last_run_ts")

    if _is_in_business_hours():
        # 工作日业务时段：每 5 分钟一次（Task Scheduler 5m 任务驱动）
        return True

    # 晚间 / 周末：每小时最多一次
    if last_run_ts is None:
        return True
    elapsed = time.time() - last_run_ts
    if elapsed >= 3600:
        return True
    _log(f"skip: in night/weekend mode, last run {elapsed:.0f}s ago (< 3600s)")
    return False


def _mark_run(success: bool) -> None:
    state = _load_state()
    state["last_run_ts"] = time.time()
    state["last_run_success"] = success
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


# ------------------------------------------------------------------ #
# 日志                                                               #
# ------------------------------------------------------------------ #

def _log(msg: str) -> None:
    ts = _now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ------------------------------------------------------------------ #
# 锁文件防重入                                                        #
# ------------------------------------------------------------------ #

LOCK_FILE = HERE / ".locks" / "feishu_preprocess.lock"
_lock_fd: int | None = None  # held lock fd, must be kept open until pipeline finishes


def _acquire_lock() -> bool:
    """Acquire an exclusive blocking file lock.

    On Windows: uses msvcrt.locking() with LK_LOCK (blocks until lock held or error).
    On POSIX:   uses fcntl.flock() with LOCK_EX (blocks, not LOCK_NB).
    If the lock cannot be acquired (e.g. already held by a dead process that didn't
    clean up), returns False and the wrapper exits silently (skip this run).

    The previous stateless write-then-check was racy: two processes could both pass
    the try block before either acquired the lock, resulting in concurrent pipeline
    runs. This version is correct because the OS guarantees only one process can
    hold an exclusive lock on a file at a time.

    CRITICAL: the returned fd must be kept open for the entire duration of the
    pipeline. On Windows the lock is released when the fd is closed; on POSIX
    flock() is advisory but same rule applies. The fd is closed in _release_lock().
    """
    global _lock_fd
    import os
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = str(LOCK_FILE)

    try:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError:
        return False

    try:
        if os.name == "nt":
            import msvcrt
            # LK_LOCK blocks until the lock is acquired.
            # msvcrt.locking() returns None on success, raises OSError on failure.
            # Catch it the same way we do for fcntl.flock() below.
            try:
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            except OSError:
                os.close(fd)
                return False
        else:
            import fcntl
            # LOCK_EX = exclusive lock, no LOCK_NB → blocking.
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
            except OSError:
                os.close(fd)
                return False
        _lock_fd = fd
        return True
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        return False


def _release_lock() -> None:
    """Release the lock by closing the held file descriptor."""
    global _lock_fd
    if _lock_fd is not None:
        try:
            os.close(_lock_fd)
        except Exception:
            pass
        _lock_fd = None


# ------------------------------------------------------------------ #
# Dashboard push (jcloud rag_dashboard)                               #
# ------------------------------------------------------------------ #

DASHBOARD_URL = os.environ.get(
    "FEISHU_EXT_DASHBOARD_URL",
    "https://buumicloud.com.cn/state/push",
)
DASHBOARD_USER = os.environ.get("FEISHU_EXT_DASHBOARD_USER", "buumi")
DASHBOARD_PASS = os.environ.get("FEISHU_EXT_DASHBOARD_PASS", "xdxis1234")


def _fetch_jcloud_sync_status() -> dict:
    """从 jcloud messages_proxy /sync/status 拉取 feishu_sync 状态。"""
    try:
        url = os.environ.get(
            "FEISHU_SYNC_STATUS_URL",
            "https://buumicloud.com.cn/rag-messages-api/sync/status",
        )
        user = os.environ.get("REMOTE_FEISHU_MESSAGES_USER", "buumi")
        pw = os.environ.get("REMOTE_FEISHU_MESSAGES_PASS", "xdxis1234")
        import base64
        creds = base64.b64encode(f"{user}:{pw}".encode()).decode()
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Basic {creds}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        _log(f"jcloud sync status fetch failed: {e}")
        return {"error": str(e)}


def _push_state_to_dashboard(heartbeat: dict | None, db_stats: dict) -> None:
    """POST 当前状态到 jcloud rag_dashboard.

    payload 结构:
      feishu       - 本地 feishu_ext (db + heartbeat)
      feishu_ima   - 本地 feishu_to_ima (从 feishu_ima.db 读)
      jcloud_sync  - jcloud feishu_sync 状态 (从 /sync/status 接口拉)
    """
    ts = _now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    ima_stats = _get_ima_stats()
    jcloud_sync = _fetch_jcloud_sync_status()
    payload = {
        "ts": ts,
        "feishu": {
            "db": db_stats,
            "heartbeat": heartbeat or {},
        },
        "feishu_ima": ima_stats,
        "jcloud_sync": jcloud_sync,
    }
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        creds = base64.b64encode(f"{DASHBOARD_USER}:{DASHBOARD_PASS}".encode()).decode()
        req = urllib.request.Request(
            DASHBOARD_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {creds}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            _log(f"dashboard push: ok={result.get('ok')}, ts={result.get('ts')}")
    except Exception as e:
        _log(f"dashboard push FAILED: {e}")


def _get_db_stats() -> dict:
    """从 preprocess.db 拿统计数字。"""
    try:
        con = sqlite3.connect(str(DB))
        messages = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        texts = con.execute("SELECT COUNT(*) FROM messages WHERE kind = 't'").fetchone()[0]
        images = con.execute("SELECT COUNT(*) FROM messages WHERE kind = 'i'").fetchone()[0]
        extracted = con.execute("SELECT COUNT(*) FROM extracted").fetchone()[0]
        stocks = con.execute("SELECT COUNT(*) FROM extracted_stocks").fetchone()[0]
        terms = con.execute("SELECT COUNT(*) FROM extracted_terms").fetchone()[0]
        last_extracted_at = con.execute(
            "SELECT created_at FROM extracted ORDER BY rowid DESC LIMIT 1"
        ).fetchone()[0]
        con.close()
        return {
            "messages": messages,
            "texts": texts,
            "images": images,
            "extracted": extracted,
            "stocks": stocks,
            "terms": terms,
            "last_extracted_at": last_extracted_at,
        }
    except Exception as e:
        _log(f"db stats error: {e}")
        return {}


def _get_ima_stats() -> dict:
    """从 feishu_ima.db 拿统计数字，供 dashboard 展示。"""
    try:
        if not IMA_DB.exists():
            return {"error": "db not found"}
        con = sqlite3.connect(str(IMA_DB))
        hb = con.execute("SELECT last_run_at, status, note FROM heartbeat WHERE id=1").fetchone()
        bs = con.execute("SELECT last_ts, last_msg_id, bucket_seq, last_post_track FROM bucket_state WHERE id=1").fetchone()
        txt_count = con.execute("SELECT COUNT(*) FROM txt_bucket").fetchone()[0]
        con.close()
        return {
            "last_run_at": hb[0] if hb else None,
            "status": hb[1] if hb else None,
            "note": hb[2] if hb else None,
            "last_ts": bs[0] if bs else None,
            "last_msg_id": bs[1] if bs else None,
            "bucket_seq": bs[2] if bs else None,
            "last_post_track": bs[3] if bs else None,
            "txt_bucket_count": txt_count,
        }
    except Exception as e:
        _log(f"ima stats error: {e}")
        return {}


def _read_heartbeat() -> dict | None:
    hb_path = DATA_DIR / "heartbeat.json"
    if hb_path.exists():
        try:
            return json.loads(hb_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


# ------------------------------------------------------------------ #
# 主 pipeline 调用                                                    #
# ------------------------------------------------------------------ #

def main() -> int:
    _log("wrapper start")

    if not _should_run():
        _log("skip: outside schedule")
        return 0

    if not _acquire_lock():
        _log("skip: lock held by another process")
        return 0

    try:
        try:
            from feishu_preprocess import main as pipeline_main
            ret = pipeline_main()
            _mark_run(success=(ret == 0))
            _log(f"pipeline returned {ret}")
        finally:
            _release_lock()
    except Exception as e:
        _log(f"ERROR: {e}")
        _mark_run(success=False)
        raise
    finally:
        # 不管成功失败都推送状态到 dashboard
        try:
            hb = _read_heartbeat()
            db_stats = _get_db_stats()
            _push_state_to_dashboard(hb, db_stats)
        except Exception as e2:
            _log(f"dashboard push error: {e2}")


if __name__ == "__main__":
    sys.exit(main())
