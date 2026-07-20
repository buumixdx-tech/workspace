"""
ths_forecast.py
同花顺一致预期 EPS（2026 / 2027 / 2028）
实测：https://basic.10jqka.com.cn/new/600519/worth.html
- 表格0 = 一致预期每股收益（年度, 预测机构数, 最小值, 均值, 最大值, 行业平均数）
- 年度值为整数：2026 / 2027 / 2028（不是 2026E）
"""

import requests
import pandas as pd
from io import StringIO
import time
import random

UA = "Mozilla/5.0"
THS_URL = "https://basic.10jqka.com.cn/new/{code}/worth.html"

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": UA})
_LAST_CALL = [0.0]
_MIN_INTERVAL = 1.0


def _ths_get(url: str, timeout: int = 20) -> requests.Response:
    wait = _MIN_INTERVAL - (time.time() - _LAST_CALL[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.3))
    try:
        return _SESSION.get(url, timeout=timeout)
    finally:
        _LAST_CALL[0] = time.time()


def fetch_eps_forecast(code: str) -> dict:
    """
    获取个股 2026 / 2027 / 2028 一致预期 EPS。
    返回: {
        "eps_2026": float,    # 一致预期 EPS（元/股）
        "eps_2027": float,
        "eps_2028": float,
        "analyst_count": int, # 预测机构数
    }
    如果某年无数据则为 None
    """
    url = THS_URL.format(code=code)
    r = _ths_get(url)
    r.encoding = "gbk"
    try:
        dfs = pd.read_html(StringIO(r.text))
    except ValueError:
        # pd.read_html 解析失败（如页面无表格）时抛出 ValueError: "No tables found"
        dfs = []

    # 表格0 = 一致预期每股收益（年度, 预测机构数, 最小值, 均值, 最大值, 行业平均数）
    if not dfs:
        # THS 页面上没有 EPS 预测表（无券商覆盖）
        return {}
    try:
        eps_df = dfs[0]
    except Exception:
        return {}

    result = {}
    try:
        year_col = eps_df.columns[0]  # "年度"
        count_col = eps_df.columns[1]  # "预测机构数"
        mean_col = eps_df.columns[3]   # "均值"（一致预期EPS）

        for _, row in eps_df.iterrows():
            yr_val = row[year_col]
            # numpy int64 转 str 会变成 "2026.0"，要去掉 ".0" 后缀
            yr_raw = str(yr_val).strip()
            if yr_raw.endswith(".0"):
                yr_raw = yr_raw[:-2]
            try:
                yr = int(yr_raw)
            except (ValueError, TypeError):
                continue

            if yr not in (2026, 2027, 2028):
                continue

            # 分析师数（取第一行的值）
            if "analyst_count" not in result:
                try:
                    result["analyst_count"] = int(row[count_col]) if pd.notna(row[count_col]) else 0
                except (ValueError, TypeError):
                    result["analyst_count"] = 0

            try:
                result[f"eps_{yr}"] = float(row[mean_col]) if pd.notna(row[mean_col]) else None
            except (ValueError, TypeError):
                result[f"eps_{yr}"] = None

    except Exception as e:
        pass

    return result


if __name__ == "__main__":
    print("测试同花顺一致预期（600519 茅台）...")
    result = fetch_eps_forecast("600519")
    print(f"结果: {result}")
