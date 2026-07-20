"""
eastmoney_industry.py
东财 push2 接口获取个股行业分类
f127 = 东财行业名称（如"白酒Ⅱ"）
东财行业分类可作为行业标签使用（不同于申万，但覆盖全面）

使用 em_get() 节流入口避免风控。
"""

import requests
import time
import random

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
PUSH2_URL = "https://push2.eastmoney.com/api/qt/stock/get"

EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
_EM_LAST_CALL = [0.0]
_EM_MIN_INTERVAL = 0.5   # push2 查询速度快，设短一些


def em_get(url: str, params: dict, timeout: int = 15, **kwargs) -> requests.Response:
    wait = _EM_MIN_INTERVAL - (time.time() - _EM_LAST_CALL[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.05, 0.2))
    try:
        return EM_SESSION.get(url, params=params, timeout=timeout, **kwargs)
    finally:
        _EM_LAST_CALL[0] = time.time()


def fetch_industry_em(code: str) -> str:
    """
    获取个股东财行业分类（f127）。
    返回: 行业名称字符串，如 "白酒Ⅱ"，空字符串表示无数据
    """
    market_code = 1 if code.startswith(("6", "9")) else 0
    params = {
        "fltt": "2", "invt": "2",
        "fields": "f57,f58,f127",
        "secid": f"{market_code}.{code}",
    }
    try:
        r = em_get(PUSH2_URL, params=params, timeout=10)
        d = r.json()
        return d.get("data", {}).get("f127", "") or ""
    except Exception:
        return ""


if __name__ == "__main__":
    # 测试
    for code in ["600519", "000001", "300750"]:
        ind = fetch_industry_em(code)
        print(f"{code}: {ind}")
