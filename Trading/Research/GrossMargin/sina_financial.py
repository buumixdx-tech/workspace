"""
sina_financial.py
新浪财报三表：营收、归母净利润、扣非归母、毛利率

关键字段名（实测茅台 600519，2026Q1 报告期）:
  营业收入       → "营业收入"
  营业成本       → "营业成本"
  归母净利润     → "归属于母公司所有者的净利润"
  扣非归母净利润 → 新浪利润表无此字段，用"持续经营净利润"或"净利润"近似代替

毛利率 = (营业收入 - 营业成本) / 营业收入 * 100
"""

import requests
import time
import random

UA = "Mozilla/5.0"

_SINA_SESSION = requests.Session()
_SINA_SESSION.headers.update({"User-Agent": UA})
_EM_LAST_CALL = [0.0]
_EM_MIN_INTERVAL = 0.8

SINA_URL = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"


def _sina_get(url: str, params: dict, timeout: int = 20) -> dict:
    wait = _EM_MIN_INTERVAL - (time.time() - _EM_LAST_CALL[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.05, 0.2))
    try:
        r = _SINA_SESSION.get(url, params=params, timeout=timeout)
        r.encoding = "gbk"
        return r.json()
    finally:
        _EM_LAST_CALL[0] = time.time()


def sina_financial_report(code: str, report_type: str = "lrb", num: int = 12) -> list[dict]:
    """
    新浪财报三表。
    返回: [{"报告期": "2026-03-31", "<科目>": "<值>", ...}, ...]
    """
    prefix = "sh" if code.startswith("6") else "sz"
    params = {
        "paperCode": f"{prefix}{code}",
        "source": report_type,
        "type": "0",
        "page": "1",
        "num": str(num),
    }
    d = _sina_get(SINA_URL, params=params)
    report_list = d.get("result", {}).get("data", {}).get("report_list", {}) or {}

    rows = []
    for period in sorted(report_list.keys(), reverse=True)[:num]:
        obj = report_list[period]
        rec = {"报告期": f"{period[:4]}-{period[4:6]}-{period[6:8]}"}
        for it in obj.get("data", []) or []:
            title = it.get("item_title", "")
            if not title or it.get("item_value") is None:
                continue
            rec[title] = it.get("item_value")
        rows.append(rec)
    return rows


def fetch_financial_metrics(code: str) -> list[dict]:
    """
    获取个股财务指标（最近 num 期）。
    返回: [{"报告期": ..., "营收": ..., "归母净利润": ..., "扣非归母净利润": ..., "毛利率": ...}, ...]
    """
    lrb = sina_financial_report(code, "lrb", num=12)

    results = []
    for row in lrb:
        period = row.get("报告期", "")

        # 营收
        revenue = row.get("营业收入") or row.get("营业总收入")

        # 营业成本
        cost = row.get("营业成本")

        # 毛利率
        gross_margin = ""
        if revenue and cost:
            try:
                rev_f = float(revenue)
                cost_f = float(cost)
                if rev_f > 0:
                    gm = (rev_f - cost_f) / rev_f * 100
                    gross_margin = round(gm, 2)
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        # 归母净利润（持续经营净利润作为近似）
        net_parent = row.get("归属于母公司所有者的净利润") or row.get("净利润")

        # 扣非归母（新浪利润表无此字段，用持续经营净利润代替）
        net_ex = row.get("持续经营净利润") or row.get("净利润")

        results.append({
            "code": code,
            "报告期": period,
            "营收": revenue,
            "归母净利润": net_parent,
            "扣非归母净利润": net_ex,
            "毛利率": gross_margin,
        })

    return results


if __name__ == "__main__":
    print("测试新浪财报（600519 茅台）...")
    rows = fetch_financial_metrics("600519")
    for r in rows[:3]:
        print(f"  {r['报告期']} 营收={r['营收']} 归母={r['归母净利润']} 毛利率={r['毛利率']}%")
