"""无窗口后台调度器，替代 Windows Task Scheduler。
每 5 分钟执行一次 run_wrapper，在 wrapper 内部按时间段判断是否真正运行。
"""
import sys, os, time, subprocess, threading
from pathlib import Path

WRAPPER = Path(__file__).parent / "run_wrapper.py"
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "feishu_scheduler.log"


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run_wrapper():
    """在新进程中执行 wrapper，捕获输出到日志。"""
    t = time.strftime("%Y-%m-%d %H:%M:%S")
    log(f"spawning wrapper at {t}")
    try:
        proc = subprocess.Popen(
            [sys.executable, str(WRAPPER)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        out, _ = proc.communicate(timeout=120)
        if out:
            for line in out.decode("utf-8", errors="replace").splitlines():
                if line.strip():
                    log(f"  {line}")
        log(f"wrapper exited with {proc.returncode}")
    except subprocess.TimeoutExpired:
        proc.kill()
        log("wrapper timed out (>120s), killed")
    except Exception as e:
        log(f"ERROR spawning wrapper: {e}")


def schedule_next(delay_seconds, callback):
    """在 delay 秒后执行 callback，并重新调度自己。"""
    def wrapper():
        callback()
        schedule_next(delay_seconds, callback)  # 重新调度
    t = threading.Timer(delay_seconds, wrapper)
    t.daemon = True
    t.start()


if __name__ == "__main__":
    log("scheduler start, pid=%d" % os.getpid())
    INTERVAL = 5 * 60  # 5 分钟
    run_wrapper()       # 立即执行一次
    schedule_next(INTERVAL, run_wrapper)  # 之后每 5 分钟

    # 保持主线程存活
    while True:
        time.sleep(3600)
