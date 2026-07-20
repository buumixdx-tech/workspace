"""mycloud_ima 定时任务 wrapper — 按时间段控制执行频率 + 推送 dashboard 状态。

调度策略 (跟 feishu_ext 完全一致):
  Mon-Fri 08:00-19:00:  5 分钟粒度
  Mon-Fri 19:00-08:00:  60 分钟粒度
  Sat-Sun 全天:         60 分钟粒度

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
DB = DATA_DIR / "mycloud_preprocess.db"
STATE_FILE = DATA_DIR / "last_run.json"
LOG_DIR = HERE.parent / "logs"
LOG_FILE = LOG_DIR / "mycloud_ima_wrapper.log"

# ------------------------------------------------------------------ #
# 时间 / 日程判断                                                     #
# ------------------------------------------------------------------ #

TZ_OFFSET = datetime.timezone(datetime.timedelta(hours=8))


def _now() -> datetime.datetime:
    return datetime.datetime.now(TZ_OFFSET)


def _weekday() -> int:
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
    state = _load_state()
    last_run_ts: float | None = state.get("last_run_ts")

    if _is_in_business_hours():
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

LOCK_FILE = HERE / ".locks" / "mycloud_preprocess.lock"


def _acquire_lock() -> bool:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    try:
        LOCK_FILE.write_text(json.dumps({"pid": pid, "ts": time.time()}), encoding="utf-8")
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ #
# Dashboard push (jcloud rag_dashboard)                               #
# ------------------------------------------------------------------ #

DASHBOARD_URL = os.environ.get(
    "MYCLOUD_IMA_DASHBOARD_URL",
    "https://buumicloud.com.cn/state/push",
)
DASHBOARD_USER = os.environ.get("MYCLOUD_IMA_DASHBOARD_USER", "buumi")
DASHBOARD_PASS = os.environ.get("MYCLOUD_IMA_DASHBOARD_PASS", "xdxis1234")


def _push_state_to_dashboard(heartbeat: dict | None, db_stats: dict) -> None:
    ts = _now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    payload = {
        "ts": ts,
        "mycloud": {
            "db": db_stats,
            "heartbeat": heartbeat or {},
        },
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
        from mycloud_preprocess import main as pipeline_main
        ret = pipeline_main()
        _mark_run(success=(ret == 0))
        _log(f"pipeline returned {ret}")
    except Exception as e:
        _log(f"ERROR: {e}")
        _mark_run(success=False)
        raise
    finally:
        try:
            hb = _read_heartbeat()
            db_stats = _get_db_stats()
            _push_state_to_dashboard(hb, db_stats)
        except Exception as e2:
            _log(f"dashboard push error: {e2}")


if __name__ == "__main__":
    sys.exit(main())
