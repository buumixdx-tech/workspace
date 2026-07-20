"""
run_parallel.py — 并行全量运行
用法: python run_parallel.py [worker数 默认6]

性能预估:
  5053 只股票
  每只 ≈ 3 个并行接口 + 1 个 THS 串行锁
  6 worker: 约 25-35 分钟
  10 worker: 约 15-20 分钟（THS 串行锁成为瓶颈）
  12+ worker: 收益递减，由 THS 串行上限决定
"""

import csv
import json
import os
import sys
import time
import random
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(__file__))
from cninfo_stocks   import fetch_cninfo_stock_list
from tencent_filter import filter_active_stocks
from workers         import fetch_stock_data

# ── 配置 ──────────────────────────────────────────────────────────────────
OUT_DIR      = os.path.dirname(__file__) or "."
CSV_PATH     = os.path.join(OUT_DIR, "gross_margin.csv")
CKPT_PATH    = os.path.join(OUT_DIR, "checkpoint.json")
LOG_PATH     = os.path.join(OUT_DIR, "run.log")
OUT_ENCODING = "utf-8-sig"

WORKER_COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 6

HEADER = [
    "code", "name", "market", "industry_em",
    "营收_2026Q1", "归母净利润_2026Q1", "扣非归母_2026Q1", "毛利率_2026Q1",
    "营收_2025A",  "归母净利润_2025A",  "扣非归母_2025A",  "毛利率_2025A",
    "营收_2024A",  "归母净利润_2024A",  "扣非归母_2024A",  "毛利率_2024A",
]

# 全局写入锁（CSV 写入必须线程安全）
_csv_lock = threading.Lock()
_ckpt_lock = threading.Lock()


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        pass
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _load_ckpt() -> tuple[set, list]:
    if os.path.exists(CKPT_PATH):
        try:
            with open(CKPT_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            return set(d.get("done", [])), d.get("errors", [])
        except Exception:
            pass
    return set(), []


def _save_ckpt(done: set, errors: list):
    with _ckpt_lock:
        with open(CKPT_PATH, "w", encoding="utf-8") as f:
            json.dump({"done": sorted(done), "errors": errors[-200:]}, f, ensure_ascii=False)


def _write_row(row: dict, csv_f):
    with _csv_lock:
        writer = csv.DictWriter(csv_f, fieldnames=HEADER, extrasaction="ignore")
        writer.writerow(row)
        csv_f.flush()


def run():
    t0 = time.time()

    # 初始化日志
    for p in (CSV_PATH, CKPT_PATH, LOG_PATH):
        pass  # 日志 always append

    log("========== 并行全量运行 ==========")
    log(f"Worker 数量: {WORKER_COUNT}")

    # ── Step 1+2: 股票列表 ──────────────────────────────────────────────
    done_codes, prev_errors = _load_ckpt()
    log(f"[Checkpoint] 已完成: {len(done_codes)} 只")

    log("[Step1] 获取股票列表...")
    all_stocks = fetch_cninfo_stock_list()
    candidates = [
        code for code, info in all_stocks.items()
        if info.get("name")
        and "ST" not in info.get("name", "")
        and "退" not in info.get("name", "")
        and not code.startswith(("8", "4"))
    ]
    log(f"  候选股票: {len(candidates)} 只")

    log("[Step2] 腾讯接口过滤...")
    active = filter_active_stocks(candidates)
    log(f"  活跃股票: {len(active)} 只 (SH={sum(1 for v in active.values() if v['market']=='SH')} SZ={sum(1 for v in active.values() if v['market']=='SZ')})")

    # ── 本次待处理 ────────────────────────────────────────────────────
    to_process = [(c, active[c]) for c in active if c not in done_codes]
    log(f"  本次待处理: {len(to_process)} 只")

    if not to_process:
        log("  所有股票已处理完毕。")
        return

    # ── CSV 初始化 ───────────────────────────────────────────────────
    file_exists = os.path.exists(CSV_PATH)
    csv_f = open(CSV_PATH, "a", newline="", encoding=OUT_ENCODING)
    if not file_exists:
        # 先写表头（加锁）
        with _csv_lock:
            w = csv.DictWriter(csv_f, fieldnames=HEADER)
            w.writeheader()
            csv_f.flush()

    # ── 并行执行 ─────────────────────────────────────────────────────
    errors = list(prev_errors)
    done_set = set(done_codes)
    n_total = len(to_process)
    completed = [0]

    def on_done(future):
        nonlocal completed
        try:
            result = future.result()
        except Exception as e:
            result = None
            errors.append(f"Worker exception: {e}")

        completed[0] += 1
        elapsed = time.time() - t0
        progress = completed[0]
        eta = (elapsed / max(progress, 1)) * (n_total - progress) if progress > 0 else 0

        if result is not None:
            code = result["code"]
            with _csv_lock:
                w = csv.DictWriter(csv_f, fieldnames=HEADER, extrasaction="ignore")
                w.writerow(result)
                csv_f.flush()
            done_set.add(code)
            log(f"  [{progress}/{n_total}] {code} {result.get('name',''):<8}"
                f" | {elapsed/60:.1f}min 剩余 {eta/60:.1f}min")
        else:
            log(f"  [{progress}/{n_total}] [ERR]"
                f" | {elapsed/60:.1f}min 剩余 {eta/60:.1f}min")

        # 每 50 只保存 checkpoint
        if completed[0] % 50 == 0:
            _save_ckpt(done_set, errors)

    log(f"[Step3] 启动 {WORKER_COUNT} 个 worker 并行拉取...")

    with ThreadPoolExecutor(max_workers=WORKER_COUNT) as executor:
        futures = {
            executor.submit(fetch_stock_data, code, info): code
            for code, info in to_process
        }
        for future in as_completed(futures):
            on_done(future)

    # ── 完成 ──────────────────────────────────────────────────────────
    csv_f.close()
    _save_ckpt(done_set, errors)
    elapsed = time.time() - t0

    log(f"\n[DONE] 处理 {len(done_set)} 只，耗时 {elapsed/60:.1f} min")
    log(f"   Worker数: {WORKER_COUNT} | CSV: {CSV_PATH}")

    # 摘要
    try:
        with open(CSV_PATH, encoding=OUT_ENCODING) as f:
            rows = list(csv.DictReader(f))
        total = len(rows)
        log(f"\n========== 数据覆盖 ==========")
        for suffix in ("2026Q1", "2025A", "2024A"):
            n_gm = sum(1 for r in rows if r.get(f"毛利率_{suffix}", "").strip() not in ("", "None"))
            n_rev = sum(1 for r in rows if r.get(f"营收_{suffix}", "").strip())
            log(f"  {suffix}: 营收{n_rev}/{total} 毛利率{n_gm}/{total}")
        log(f"  错误: {len(errors)} 条")
    except Exception as e:
        log(f"  摘要失败: {e}")


if __name__ == "__main__":
    run()
