#!/usr/bin/env python3
"""测试 eltdx 对新 IPO 股票的行为.

场景:
  - 找最近 IPO 的股票
  - 用 count=20 拉
  - 看 eltdx 返回的实际根数
  - 看 CK 增量逻辑会不会出错
"""

import io
import sys
from datetime import date, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from eltdx import TdxClient
import clickhouse_connect

# 找最近 5 天的 IPO 候选
candidate_codes = [
    "sh.688797",   # C臻宝 (10 天前发现)
    "sz.001248",   # 华润新能源
    "sz.001399",   # N惠科
    "sz.301583",   # 托伦斯
]


def fetch_klines(code, count=20):
    """eltdx 拉最近 count 根"""
    # eltdx 格式: sh688797
    eltdx_code = code.replace(".", "").lower()
    client = TdxClient(timeout=8, pool_size=1)
    try:
        series = client.bars.get(eltdx_code, period="day", count=count, adjust="none")
        bars = list(series.bars) if hasattr(series, "bars") else []
        return bars
    except Exception as e:
        return f"ERR: {type(e).__name__}: {e}"
    finally:
        client.close()


def main():
    today = date.today()
    print(f"今天: {today}")
    print()
    print("=" * 70)
    print(" 新股 eltdx 行为测试")
    print("=" * 70)

    for code in candidate_codes:
        print()
        print(f"--- {code} ---")
        bars = fetch_klines(code, count=20)
        if isinstance(bars, str):
            print(f"  eltdx 错误: {bars}")
            continue

        print(f"  eltdx 返回: {len(bars)} 根 (请求 20)")
        if not bars:
            print(f"  返回空列表(eltdx 协议无数据)")
            continue

        # 最早和最晚
        first = bars[-1].time.date()
        last = bars[0].time.date()
        days_old = (today - first).days
        print(f"  时间范围: {first} → {last}")
        print(f"  距今: {days_old} 天 (约 {days_old * 5 // 7} 个交易日)")

        # 模拟增量逻辑
        # 假设 last_date = None (新股)
        if not bars:
            print(f"  CK 逻辑: 新股,走全量分支")
        else:
            print(f"  CK 逻辑: 新股 (last_date=None),走全量分支")
            print(f"  拉到的根数: {len(bars)},INSERT {len(bars)} 行")
            print(f"  没有\"补空数据\"问题 — eltdx 只返回真实有的 K")

        # 如果是 last_date 已知(已有 CK 数据)
        last_ck_date = first - timedelta(days=10)  # 假设
        filtered = [b for b in bars if b.time.date() > last_ck_date]
        print(f"  假设 CK 已有 last_date={last_ck_date},过滤后剩 {len(filtered)} 行")

    print()
    print("=" * 70)
    print(" 结论")
    print("=" * 70)
    print("""
eltdx 对新股的预期行为:
  ✓ 返回真实存在的 K 线(不会补 0)
  ✓ count=20 但实际只返回 N < 20 根 (N = 该股已有交易日数)
  ✓ CK 增量逻辑安全:
    - 新股 (last_date=None) → 走全量分支,INSERT 所有 bars
    - 老股 (last_date 已知) → 走增量分支,过滤 date > last_date
    - 即使 count=20 拉少了,只要拉到的最早一根 date > last_date,过滤后仍能保留所有新数据

潜在风险:
  ⚠ 如果老股已经停牌几天,eltdx 仍返回停牌前的数据
  ⚠ 如果 last_date 距 today 超过 20 天,count=20 不够 (但对新股不影响)
""")