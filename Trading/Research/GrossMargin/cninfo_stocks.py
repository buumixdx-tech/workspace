"""
cninfo_stocks.py
从巨潮获取全市场 A 股股票列表
数据源: http://www.cninfo.com.cn/new/data/szse_stock.json  (含沪深北全量)

巨潮 szse_stock.json 的 stockList 包含所有 A 股（沪市6开头、深市0/3开头都在里面），
字段: code, pinyin, category, orgId, zwjc(中文简称)
"""

import requests
import time
import random

UA = "Mozilla/5.0"

_CNINFO_STOCK_MAP = {}   # code -> {orgId, name, market}


def fetch_cninfo_stock_list() -> dict[str, dict]:
    """
    获取全市场 A 股股票列表。
    返回: {code: {orgId, name, market}}
    """
    global _CNINFO_STOCK_MAP
    if _CNINFO_STOCK_MAP:
        return _CNINFO_STOCK_MAP

    stocks = {}
    try:
        r = requests.get(
            "http://www.cninfo.com.cn/new/data/szse_stock.json",
            headers={"User-Agent": UA}, timeout=30
        )
        r.raise_for_status()
        data = r.json()
        for s in data.get("stockList", []):
            code = s.get("code", "")
            category = s.get("category", "")

            # 只保留 A 股（排除 B 股/CDR/优先股）
            if category != "A股":
                continue
            # 排除北交所(8/4开头)
            if code.startswith(("8", "4")):
                continue

            market = "SH" if code.startswith(("6", "9")) else "SZ"
            stocks[code] = {
                "orgId":  s.get("orgId", ""),
                "name":   s.get("zwjc", ""),
                "market": market,
            }
        print(f"  巨潮股票列表: {len(stocks)} 只 A 股")
    except Exception as e:
        print(f"  [WARN] 巨潮股票列表获取失败: {e}")

    _CNINFO_STOCK_MAP = stocks
    return stocks


if __name__ == "__main__":
    print("获取全市场股票列表...")
    st = fetch_cninfo_stock_list()
    sh = sum(1 for v in st.values() if v["market"] == "SH")
    sz = sum(1 for v in st.values() if v["market"] == "SZ")
    print(f"沪市: {sh}  深市: {sz}")
    for code, info in list(st.items())[:5]:
        print(f"  {code} {info['name']} | {info['market']}")
