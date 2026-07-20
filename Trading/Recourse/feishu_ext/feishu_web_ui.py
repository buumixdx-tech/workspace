#!/usr/bin/env python3
"""feishu_preprocess API 后端 — stdlib only, port 8080.

只提供 API; HTML 由 nginx 静态服务.

端点 (路径不带 /api/ 前缀 — 由 nginx location 决定):
  GET  /status       {running, pid, history, log_lines}
  GET  /extracted    preprocess.extracted 统计 + recent 20
  POST /run          启动 run.sh (单实例, 防重入)
"""
import http.server
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

# 2026-06-23: info_type 从中文改成 INTEGER code, web_ui 显示时反查 label
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from prompts.schemas import CODE_TO_LABELS, SKIP_TYPE_CODES  # noqa: E402


def _info_type_display(code) -> str:
    """渲染 info_type 给 web_ui: '个股点评(1)' 形式."""
    try:
        return f"{CODE_TO_LABELS[int(code)]}({int(code)})"
    except (ValueError, KeyError):
        return str(code)

# ---------- config ----------
WEBUI_PORT = int(os.environ.get("WEBUI_PORT", "8080"))
PRE_DIR    = Path("/root/rag_preprocess")
PRE_DB     = PRE_DIR / "data" / "preprocess.db"
LOG_FILE   = Path("/var/log/rag_preprocess.log")
RUN_SH     = PRE_DIR / "run.sh"

# ---------- state ----------
_lock         = threading.Lock()
_cur_pid      = None   # 进程 PID
_cur_pid_st   = None   # 启动时的 start time (jiffies since boot) — 防 PID 复用
_history      = []


def _pid_stat(pid: int):
    """读 /proc/<pid>/stat, 返回 (state, starttime) 或 None.
    state 字段: R/S/D/Z/T/X 等. Z=zombie — 进程已死但 parent 未 reap.
    """
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            data = f.read().decode("utf-8", errors="replace")
        # 格式: pid (comm) state ppid ... field[21]=starttime
        # comm 可能含空格/括号, 从最后一个 ')' 切
        r = data.rfind(")")
        if r < 0: return None
        fields = data[r+1:].split()
        # fields[0]=state, [1]=ppid, ..., [19]=starttime (相对 boot 的 jiffies)
        return fields[0], int(fields[19])
    except (OSError, ValueError, IndexError):
        return None


def _alive(pid: int, st: int) -> bool:
    """PID 存在 + 同一进程 (starttime 未变) + 非 zombie.
    顺便 waitpid(WNOHANG) reap 已退子进程, 防止 zombie 堆积.
    """
    if pid is None:
        return False
    # 1) 尝试 reap — 已退出会被 reap, 活进程返回 (0, 0) 不阻塞
    try:
        reaped, _ = os.waitpid(pid, os.WNOHANG)
        if reaped != 0:
            return False  # 已 reap, 进程退出
    except ChildProcessError:
        return False  # 不是 webui 的子进程 (被 init reap 了)
    # 2) 还活着 — 校验 state != Z + starttime 没变
    info = _pid_stat(pid)
    if info is None:
        return False
    state, cur_st = info
    if state == "Z":  # zombie: 进程已死, 没人 reap
        return False
    return cur_st == st


def start_run() -> dict:
    global _cur_pid, _cur_pid_st
    with _lock:
        if _cur_pid is not None and _alive(_cur_pid, _cur_pid_st):
            return {"ok": False, "error": f"already running (pid {_cur_pid})"}
        proc = subprocess.Popen(
            ["bash", str(RUN_SH)],
            cwd=str(PRE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        # 等一小会, 让内核把 /proc/<pid>/stat 准备好
        time.sleep(0.05)
        info = _pid_stat(proc.pid)
        st = info[1] if info else None
        _cur_pid    = proc.pid
        _cur_pid_st = st
        _history.append({"start": time.time(), "pid": proc.pid, "status": "running"})
        return {"ok": True, "pid": proc.pid}


def _reap() -> None:
    global _cur_pid, _cur_pid_st
    with _lock:
        if _cur_pid is not None and not _alive(_cur_pid, _cur_pid_st):
            for h in _history:
                if h.get("status") == "running" and h.get("pid") == _cur_pid:
                    h["end"]    = time.time()
                    h["status"] = "finished"
            _cur_pid    = None
            _cur_pid_st = None


def _reaper_loop() -> None:
    while True:
        _reap()
        time.sleep(1)


# ---------- data sources ----------
def get_extracted() -> dict:
    con = sqlite3.connect(str(PRE_DB))
    try:
        total  = con.execute("SELECT COUNT(*) FROM extracted").fetchone()[0]
        # 水位: 已处理消息里最新的 ts (ms epoch). 落后 messages 表越远, 越需要跑 preprocess
        watermark_ts = con.execute("SELECT MAX(ts) FROM extracted").fetchone()[0]
        rows   = con.execute("""
            SELECT msg_id, ts, info_type, category
            FROM extracted ORDER BY msg_id DESC LIMIT 20
        """).fetchall()
        return {
            "total":        total,
            "watermark_ts": watermark_ts,
            "recent": [
                {"msg_id": r[0], "ts": r[1],
                 "info_type_code": int(r[2]) if r[2] is not None else None,
                 "info_type_label": _info_type_display(r[2]),
                 "is_skip_type": int(r[2]) in SKIP_TYPE_CODES if r[2] is not None else False,
                 "category": r[3]}
                for r in rows
            ],
        }
    finally:
        con.close()


def get_log_tail(n: int = 200) -> list:
    try:
        with open(LOG_FILE, "rb") as f:
            f.seek(0, 2)
            sz = f.tell()
            f.seek(max(0, sz - n * 200), 0)
            data = f.read().decode("utf-8", errors="replace")
        return data.splitlines()[-n:]
    except FileNotFoundError:
        return []


# ---------- HTTP ----------
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a, **kw): pass

    def _send(self, code: int, body, ctype: str):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/status", "/api/status"):
            _reap()
            self._send(200, {
                "running":   _cur_pid is not None and _alive(_cur_pid, _cur_pid_st),
                "pid":       _cur_pid,
                "history":   _history[-10:],
                "log_lines": get_log_tail(200),
            }, "application/json; charset=utf-8")
        elif path in ("/extracted", "/api/extracted"):
            self._send(200, get_extracted(), "application/json; charset=utf-8")
        else:
            self._send(404, {"error": "not found", "path": path}, "application/json")

    def do_POST(self):
        path = self.path.split("?")[0]
        if path in ("/run", "/api/run"):
            self._send(200, start_run(), "application/json; charset=utf-8")
        else:
            self._send(404, {"error": "not found"}, "application/json")


if __name__ == "__main__":
    threading.Thread(target=_reaper_loop, daemon=True).start()
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", WEBUI_PORT), Handler)
    print(f"webui api listening on http://0.0.0.0:{WEBUI_PORT}")
    srv.serve_forever()
