"""
main.py — 全量运行脚本
用法: python main.py
断点续传: 如中断，重新运行会自动从 checkpoint 继续
"""

import csv
import json
import os
import sys
import time
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from cninfo_stocks   import fetch_cninfo_stock_list
from tencent_filter import filter_active_stocks
from sina_financial import fetch_financial_metrics
from ths_forecast   import fetch_eps_forecast
from get_industry   import fetch_industry_em

# ── 配置 ──────────────────────────────────────────────────────────────────
OUT_DIR      = os.path.dirname(__file__) or "."
CSV_PATH      = os.path.join(OUT_DIR, "gross_margin.csv")
CKPT_PATH    = os.path.join(OUT_DIR, "checkpoint.json")
LOG_PATH     = os.path.join(OUT_DIR, "run.log")
OUT_ENCODING = "utf-8-sig"

TARGET_YEARS = {"2026-03-31": "2026Q1", "2025-12-31": "2025A", "2024-12-31": "2024A"}

HEADER = [
    "code", "name", "market", "industry_em",
    "营收_2026Q1", "归母净利润_2026Q1", "扣非归母_2026Q1", "毛利率_2026Q1",
    "营收_2025A",  "归母净利润_2025A",  "扣非归母_2025A",  "毛利率_2025A",
    "营收_2024A",  "归母净利润_2024A",  "扣非归母_2024A",  "毛利率_2024A",
]


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        pass
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _find_period(rows, target):
    for r in rows:
        if r.get("报告期", "") == target:
            return r
    return {}


def _num(v):
    if v is None or v == "":
        return ""
    try:
        f = float(v)
        if abs(f) >= 1e8:
            return f"{f/1e8:.2f}"
        elif abs(f) >= 1e4:
            return f"{f/1e4:.2f}"
        else:
            return f"{f:.4f}"
    except (ValueError, TypeError):
        return str(v)


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
    with open(CKPT_PATH, "w", encoding="utf-8") as f:
        json.dump({"done": sorted(done), "errors": errors[-200:]}, f, ensure_ascii=False)


def run():
    t0 = time.time()

    # ── 初始化日志 ────────────────────────────────────────────────────────
    log("========== 全市场 A 股毛利率研究 ==========")

    # ── Step 1+2: 股票列表 + 腾讯过滤 ────────────────────────────────────
    done_codes, prev_errors = _load_ckpt()

    # 判断是否需要重新过滤股票池（每次全新启动都重新过滤，支持增量）
    # 如果已有 checkpoint 且超过 4000 只认为已完整，直接用 done_codes 断点续传
    if len(done_codes) >= 4000:
        log(f"[Checkpoint] 已完成 {len(done_codes)} 只，断点续传模式")
        active = {}  # 断点模式不重新获取活跃列表
    else:
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

        log("[Step2] 腾讯接口过滤（只保留可交易）...")
        active = filter_active_stocks(candidates)
        log(f"  活跃股票: {len(active)} 只 (SH={sum(1 for v in active.values() if v['market']=='SH')} SZ={sum(1 for v in active.values() if v['market']=='SZ')})")

    # ── 本次待处理 ──────────────────────────────────────────────────────
    to_process = [c for c in active.keys() if c not in done_codes] if active else []
    if not to_process and not active:
        # 断点模式：重新从巨潮+腾讯构建
        log("[WARN] 断点模式但无active，重新获取股票列表...")
        all_stocks = fetch_cninfo_stock_list()
        candidates = [code for code, info in all_stocks.items()
                      if info.get("name") and "ST" not in info.get("name", "")
                      and "退" not in info.get("name", "") and not code.startswith(("8", "4"))]
        active = filter_active_stocks(candidates)
        to_process = [c for c in active.keys() if c not in done_codes]

    log(f"  待处理: {len(to_process)} 只 / 已完成: {len(done_codes)} 只")

    if not to_process:
        log("  所有股票已处理完毕，直接生成摘要。")
        to_process = list(active.keys()) if active else []
        if not to_process:
            log("  无股票可处理，退出。")
            return

    # ── CSV ─────────────────────────────────────────────────────────────
    file_exists = os.path.exists(CSV_PATH)
    csv_f = open(CSV_PATH, "a", newline="", encoding=OUT_ENCODING)
    writer = csv.DictWriter(csv_f, fieldnames=HEADER, extrasaction="ignore")
    if not file_exists:
        writer.writeheader()

    # ── 逐股拉取 ────────────────────────────────────────────────────────
    errors = prev_errors
    n = len(to_process)
    for i, code in enumerate(to_process):
        info = active.get(code, {"name": code, "market": "SH"})
        elapsed = time.time() - t0
        eta = (elapsed / max(i, 1)) * (n - i) if i > 0 else 0

        log(f"  [{i+1}/{n}] {code} {info['name'][:8]:<8}"
            f" | {elapsed/60:.1f}min 剩余 {eta/60:.1f}min")

        row_out = {"code": code, "name": info["name"], "market": info["market"]}

        try:
            row_out["industry_em"] = fetch_industry_em(code)

            fin_rows = fetch_financial_metrics(code)
            for period, suffix in TARGET_YEARS.items():
                r = _find_period(fin_rows, period)
                row_out[f"营收_{suffix}"]         = _num(r.get("营收"))
                row_out[f"归母净利润_{suffix}"]   = _num(r.get("归母净利润"))
                row_out[f"扣非归母_{suffix}"]     = _num(r.get("扣非归母净利润"))
                gm = r.get("毛利率", "")
                row_out[f"毛利率_{suffix}"]        = f"{gm}%" if gm != "" else ""

            fc = fetch_eps_forecast(code)
            for yr in (2026, 2027, 2028):
                v = fc.get(f"eps_{yr}")
                row_out[f"eps_{yr}"] = f"{v:.2f}" if v is not None else ""
            row_out["analyst_count"] = fc.get("analyst_count", "")

        except Exception as e:
            errors.append(f"{code}: {e}")
            log(f"    [ERR] {e}")

        writer.writerow(row_out)
        csv_f.flush()
        done_codes.add(code)

        # 每 100 只保存 checkpoint
        if len(done_codes) % 100 == 0:
            _save_ckpt(done_codes, errors)

        time.sleep(random.uniform(0.05, 0.2))

    # ── 完成 ──────────────────────────────────────────────────────────────
    csv_f.close()
    _save_ckpt(done_codes, errors)
    elapsed = time.time() - t0

    log(f"\n[DONE] 处理 {len(done_codes)} 只，耗时 {elapsed/60:.1f} min")
    log(f"   CSV: {CSV_PATH}")

    # 摘要
    try:
        with open(CSV_PATH, encoding=OUT_ENCODING) as f:
            rows = list(csv.DictReader(f))
        total = len(rows)
        log(f"\n========== 数据覆盖 ==========")
        for suffix in ("2026Q1", "2025A", "2024A"):
            gm_key = f"毛利率_{suffix}"
            n_gm = sum(1 for r in rows if r.get(gm_key, "").strip() not in ("", "None"))
            n_rev = sum(1 for r in rows if r.get(f"营收_{suffix}", "").strip())
            log(f"  {suffix}: 营收{n_rev}/{total} 毛利率{n_gm}/{total}")
        log(f"  错误: {len(errors)} 条")
    except Exception as e:
        log(f"  摘要生成失败: {e}")


if __name__ == "__main__":
    run()
