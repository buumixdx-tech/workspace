"""
tencent_filter.py
腾讯财经批量行情接口过滤——只保留当前真实可交易的股票。
原理：无效/退市/停牌股票在腾讯接口中直接不返回或返回空price。
"""

import requests
import time
import random
from typing import List

UA = "Mozilla/5.0"
_TENCENT_URL = "https://qt.gtimg.cn/q="

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": UA})
_LAST_CALL = [0.0]
_MIN_INTERVAL = 0.3   # 腾讯不封IP，间隔可设短

BATCH_SIZE = 50       # 腾讯建议每次最多50只


def _tencent_get(prefixed_codes: List[str]) -> dict:
    """返回 {code: {name, price}}，无效代码不返回"""
    url = _TENCENT_URL + ",".join(prefixed_codes)
    wait = _MIN_INTERVAL - (time.time() - _LAST_CALL[0])
    if wait > 0:
        time.sleep(wait)
    try:
        r = _SESSION.get(url, timeout=10)
        r.encoding = "gbk"
        result = {}
        for line in r.text.strip().split(";"):
            if not line.strip() or "=" not in line or '"' not in line:
                continue
            key = line.split("=")[0].split("_")[-1]  # e.g. "sh600519" -> "600519"
            vals = line.split('"')[1].split("~")
            if len(vals) < 10:
                continue
            code = key[2:]  # 去掉 "sh" / "sz" 前缀
            result[code] = {
                "name":  vals[1],
                "price": vals[3] if vals[3] else "",
            }
        return result
    finally:
        _LAST_CALL[0] = time.time()


def filter_active_stocks(codes: List[str]) -> dict:
    """
    从候选股票代码列表中，用腾讯接口过滤出当前真实可交易的股票。
    返回: {code: {name, market}}
    market: "SH" 或 "SZ"
    """
    active = {}
    n = len(codes)
    for i in range(0, n, BATCH_SIZE):
        batch = codes[i:i + BATCH_SIZE]
        prefixed = [
            ("sh" + c) if c.startswith(("6", "9")) else ("sz" + c)
            for c in batch
        ]
        result = _tencent_get(prefixed)
        for code, info in result.items():
            market = "SH" if code.startswith(("6", "9")) else "SZ"
            active[code] = {
                "name":   info["name"],
                "market": market,
            }
        # 进度
        done = min(i + BATCH_SIZE, n)
        print(f"\r  腾讯过滤: {done}/{n}", end="", flush=True)

    print()  # 换行
    return active


def get_active_stock_count() -> int:
    """快速检查当前全市场活跃A股数量（不保存详情，只计数）"""
    # 预估候选池：沪市 600000-602000 + 深市 000000-001000 + 300000-304000
    candidates = []
    candidates += [f"{i:06d}" for i in range(600000, 602000)]   # 沪市
    candidates += [f"{i:06d}" for i in range(0, 1000)]           # 深市主板
    candidates += [f"{i:06d}" for i in range(300000, 304000)]   # 创业板

    active = filter_active_stocks(candidates)
    return len(active)


if __name__ == "__main__":
    # 简单测试
    test = ["600519", "000001", "300750", "999999", "888888"]
    result = _tencent_get(["sh600519", "sz000001", "sz300750", "sh999999", "sz888888"])
    print(f"有效股票: {list(result.keys())}")
