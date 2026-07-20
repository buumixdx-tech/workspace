"""
workers.py — 并行 worker 池
===========================
并行策略：
  - 东财行业 push2：可并行
  - 新浪财报：可并行
  - 腾讯过滤：主进程完成，worker 不涉及
"""

import threading


# ── 并行拉取任务 ────────────────────────────────────────────────────────────

def fetch_stock_data(code: str, info: dict) -> dict:
    """
    在 worker 线程中执行：拉取单只股票的全部数据。
    返回 dict，直接写入 CSV。
    """
    row = {"code": code, "name": info["name"], "market": info["market"]}

    results = {}

    def run(fn, key):
        try:
            results[key] = fn()
        except Exception:
            results[key] = None

    # 两线程并行：东财行业 + 新浪财报
    t1 = threading.Thread(target=run, args=(lambda: _fetch_industry(code), "industry_em"))
    t2 = threading.Thread(target=run, args=(lambda: _fetch_financial(code), "fin_rows"))
    t1.start(); t2.start()
    t1.join(); t2.join()

    TARGET_YEARS = {"2026-03-31": "2026Q1", "2025-12-31": "2025A", "2024-12-31": "2024A"}

    def find_period(rows, target):
        for r in rows:
            if r.get("报告期", "") == target:
                return r
        return {}

    def num(v):
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

    row["industry_em"] = results.get("industry_em", "") or ""

    fin_rows = results.get("fin_rows") or []
    for period, suffix in TARGET_YEARS.items():
        r = find_period(fin_rows, period)
        row[f"营收_{suffix}"]         = num(r.get("营收"))
        row[f"归母净利润_{suffix}"]   = num(r.get("归母净利润"))
        row[f"扣非归母_{suffix}"]     = num(r.get("扣非归母净利润"))
        gm = r.get("毛利率", "")
        row[f"毛利率_{suffix}"]        = f"{gm}%" if gm != "" else ""

    return row


def _fetch_industry(code: str):
    from get_industry import fetch_industry_em
    return fetch_industry_em(code)


def _fetch_financial(code: str):
    from sina_financial import fetch_financial_metrics
    return fetch_financial_metrics(code)
