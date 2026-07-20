#!/usr/bin/env python3
"""检查 eltdx codes.list 的 5,208 只 a_share 中,有多少是停牌股.

判定逻辑:
  1. 拉 eltdx 5,208 只的最近 1 根 K
  2. volume=0 的 = 当日停牌
  3. 完全没有 K 线 = 长期停牌或协议问题
  4. 抽样测试(全量太慢,先 100 只)
"""

import io
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from eltdx import TdxClient


def fetch_one(code):
    """拉一只的最近 1 根 K"""
    client = TdxClient(timeout=5, pool_size=1)
    try:
        series = client.bars.get(code, period="day", count=1, adjust="none")
        if not series.bars:
            return code, "NO_BARS", None
        b = series.bars[0]
        return code, "OK", {
            "date": b.time.date().isoformat(),
            "close": b.close,
            "volume": b.volume_lots,
        }
    except Exception as e:
        return code, f"ERR: {type(e).__name__}", None
    finally:
        client.close()


def main():
    # 1. 拉 eltdx 5,208 只
    print("[1] 拉 eltdx a_share 代码列表 ...")
    eltdx_codes = []
    with TdxClient(timeout=15) as c:
        for exch in ("SH", "SZ"):
            for s in range(0, 25000, 1600):
                chunk = c.codes.list(exch, start=s, limit=1600)
                if not chunk:
                    break
                for x in chunk:
                    if x.category == "a_share":
                        eltdx_codes.append(f"{x.exchange}{x.code}")
                if len(chunk) < 1600:
                    break
    print(f"    eltdx a_share: {len(eltdx_codes)} 只")

    # 2. 抽样测试 200 只(全量太慢)
    import random
    random.seed(42)
    sample = random.sample(eltdx_codes, 200)

    # 3. 并发拉取
    print(f"\n[2] 抽样 {len(sample)} 只, 并发拉最近 1 根 K ...")
    suspended_today = []  # 今日停牌
    no_bars = []  # 长期停牌/协议问题
    normal = []
    errors = []

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(fetch_one, c): c for c in sample}
        for i, fut in enumerate(as_completed(futures), 1):
            code, status, info = fut.result()
            if status == "NO_BARS":
                no_bars.append(code)
            elif status.startswith("ERR"):
                errors.append((code, status))
            elif info and info["volume"] == 0:
                suspended_today.append((code, info))
            else:
                normal.append((code, info))
            if i % 50 == 0:
                print(f"    进度: {i}/{len(sample)}")

    # 4. 统计
    print()
    print("=" * 70)
    print(f" 抽样 {len(sample)} 只的结果")
    print("=" * 70)
    print(f"  正常 (有 K + volume>0):    {len(normal):>3}")
    print(f"  今日停牌 (有 K + volume=0): {len(suspended_today):>3}")
    print(f"  长期停牌/拉不到 (NO_BARS):  {len(no_bars):>3}")
    print(f"  错误 (ERR):                {len(errors):>3}")

    if suspended_today:
        print()
        print(f"今日停牌的样例(前 10):")
        for code, info in suspended_today[:10]:
            print(f"  {code}  {info['date']}  close={info['close']}  vol={info['volume']}")

    if no_bars:
        print()
        print(f"长期停牌/拉不到的样例(前 10):")
        for code in no_bars[:10]:
            print(f"  {code}")

    if errors:
        print()
        print(f"错误样例(前 5):")
        for code, err in errors[:5]:
            print(f"  {code}  {err}")

    # 5. 推算到全量
    if len(sample) > 0:
        susp_rate = len(suspended_today) / len(sample)
        no_bars_rate = len(no_bars) / len(sample)
        print()
        print(f"=== 推算到全 5,208 只 ===")
        print(f"  估计今日停牌:        {int(len(eltdx_codes) * susp_rate):>4,} 只 ({susp_rate*100:.1f}%)")
        print(f"  估计长期停牌/拉不到:  {int(len(eltdx_codes) * no_bars_rate):>4,} 只 ({no_bars_rate*100:.1f}%)")


if __name__ == "__main__":
    main()