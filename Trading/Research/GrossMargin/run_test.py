"""
run_test.py — 试跑脚本（100只）
清理旧数据后，用腾讯接口过滤出活跃股票，取前100只跑完整流程，
验证 CSV 输出无误后再跑全量。
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

TEST_COUNT   = 100          # 试跑数量
TARGET_PERIODS = ["2026-03-31", "2025-12-31", "2024-12-31"]
TARGET_YEARS   = {"2026-03-31": "2026Q1", "2025-12-31": "2025A", "2024-12-31": "2024A"}

# ── 工具 ───────────────────────────────────────────────────────────────────
def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except UnicodeEncodeError:
        # Windows GBK 终端无法打印 Unicode 字符，只写文件
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

# ── 主流程 ─────────────────────────────────────────────────────────────────
def run():
    t0 = time.time()

    # 清理旧文件
    for p in (CSV_PATH, CKPT_PATH, LOG_PATH):
        if os.path.exists(p):
            os.remove(p)
    open(LOG_PATH, "w", encoding="utf-8").close()

    log("========== 试跑（100只）==========")

    # Step 1: 股票列表
    log("[Step1] 获取股票列表...")
    all_stocks = fetch_cninfo_stock_list()

    # 排除 ST/退市/北交所
    candidates = [
        code for code, info in all_stocks.items()
        if info.get("name")
        and "ST" not in info.get("name", "")
        and "退" not in info.get("name", "")
        and not code.startswith(("8", "4"))
    ]
    log(f"  候选股票: {len(candidates)} 只")

    # Step 2: 腾讯过滤
    log("[Step2] 腾讯接口过滤（只保留可交易）...")
    active = filter_active_stocks(candidates)
    log(f"  活跃股票: {len(active)} 只")

    # 取前 TEST_COUNT 只（已按代码排序）
    test_codes = list(active.keys())[:TEST_COUNT]
    log(f"  试跑样本: {len(test_codes)} 只")
    for c in test_codes[:5]:
        log(f"    {c} {active[c]['name']}")

    # CSV 表头
    header = [
        "code", "name", "market", "industry_em",
        "营收_2026Q1", "归母净利润_2026Q1", "扣非归母_2026Q1", "毛利率_2026Q1",
        "营收_2025A",  "归母净利润_2025A",  "扣非归母_2025A",  "毛利率_2025A",
        "营收_2024A",  "归母净利润_2024A",  "扣非归母_2024A",  "毛利率_2024A",
        "eps_2026", "eps_2027", "eps_2028", "analyst_count",
    ]

    csv_f = open(CSV_PATH, "w", newline="", encoding=OUT_ENCODING)
    writer = csv.DictWriter(csv_f, fieldnames=header, extrasaction="ignore")
    writer.writeheader()

    # Step 3: 逐股拉取
    errors = []
    for i, code in enumerate(test_codes):
        info = active[code]
        elapsed = time.time() - t0
        eta = (elapsed / max(i, 1)) * (len(test_codes) - i) if i > 0 else 0

        log(f"  [{i+1}/{len(test_codes)}] {code} {info['name'][:8]:<8}"
            f" | {elapsed/60:.1f}min 剩余 {eta/60:.1f}min")

        row_out = {
            "code":   code,
            "name":   info["name"],
            "market": info["market"],
        }

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
        time.sleep(random.uniform(0.05, 0.2))

    csv_f.close()
    elapsed = time.time() - t0

    log(f"\n[OK] 试跑完成！{len(test_codes)} 只，耗时 {elapsed/60:.1f} min")
    log(f"   CSV: {CSV_PATH}")

    # 摘要
    log("\n========== 数据覆盖摘要 ==========")
    with open(CSV_PATH, encoding=OUT_ENCODING) as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    log(f"  总行数: {total}")
    for suffix in ("2026Q1", "2025A", "2024A"):
        gm_key = f"毛利率_{suffix}"
        n_gm = sum(1 for r in rows if r.get(gm_key, "").strip() not in ("", "None"))
        n_rev = sum(1 for r in rows if r.get(f"营收_{suffix}", "").strip())
        n_net = sum(1 for r in rows if r.get(f"归母净利润_{suffix}", "").strip())
        log(f"  {suffix}: 营收{n_rev}/{total} 归母净利{n_net}/{total} 毛利率{n_gm}/{total}")

    n_eps = sum(1 for r in rows if r.get("eps_2026", "").strip())
    log(f"  一致预期EPS(2026): {n_eps}/{total}")

    log(f"\n  错误: {len(errors)} 条")
    if errors:
        for e in errors[:5]:
            log(f"    {e}")

    # 打印前5行
    log("\n========== CSV 前5行 ==========")
    with open(CSV_PATH, encoding=OUT_ENCODING) as f:
        lines = f.readlines()
    for line in lines[:6]:
        print(line.rstrip())


if __name__ == "__main__":
    run()
