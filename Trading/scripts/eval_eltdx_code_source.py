#!/usr/bin/env python3
"""评估 eltdx codes.list 单独作为每日代码源."""

import io
import sys
from datetime import date

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def to_ck_code(raw):
    s = str(raw)
    if len(s) != 6 or not s.isdigit():
        return s.lower()
    if s[0] in ("6", "9", "5", "7"):
        return f"sh.{s}"
    return f"sz.{s}"


from eltdx import TdxClient
import clickhouse_connect

# 1. eltdx codes.list
eltdx_codes = {}
with TdxClient(timeout=20) as c:
    for exch, start, end in [("SH", 0, 25000), ("SZ", 0, 25000)]:
        for s in range(start, end, 1600):
            chunk = c.codes.list(exch, start=s, limit=1600)
            if not chunk:
                break
            for x in chunk:
                if x.category == "a_share":
                    code = to_ck_code(x.code)  # '600000' -> 'sh.600000'
                    eltdx_codes[code] = {
                        "name": x.name,
                        "board": x.board,
                    }
            if len(chunk) < 1600:
                break

# 2. CK 当前
ck = clickhouse_connect.get_client(
    host="127.0.0.1", port=8123, username="admin", password="admin_password", database="stock_data"
)
ck_df = ck.query_df("SELECT code, symbol, out_date FROM stock_data.securities_info")
ck_df["out_date_py"] = ck_df["out_date"].apply(
    lambda x: x.date() if hasattr(x, "date") else x
)
ck_dict = {row["code"]: row.to_dict() for _, row in ck_df.iterrows()}
today = date.today()
ck_active = {c for c, r in ck_dict.items() if r["out_date_py"] > today}
ck_set = set(ck_dict.keys())

eltdx_set = set(eltdx_codes.keys())

# 3. 对比
in_both = eltdx_set & ck_set
in_eltdx_only = eltdx_set - ck_set
in_ck_only = ck_set - eltdx_set
eltdx_active = eltdx_set
ck_active_set = ck_active

# 在交集里,两边都认为活跃的
in_both_active = eltdx_active & ck_active_set
# 交集但 eltdx 活跃, CK 已标退市
eltdx_active_ck_delisted = eltdx_active & (ck_set - ck_active_set)
# 交集但 eltdx 没, CK 仍标活跃
ck_active_eltdx_missing = ck_active_set - eltdx_active

print("=" * 70)
print(" eltdx codes.list 作为每日代码源评估")
print("=" * 70)
print()
print(f"eltdx a_share 总数: {len(eltdx_set):>6,}")
print(f"CK 当前(全部):     {len(ck_set):>6,}")
print(f"CK 活跃(out>today): {len(ck_active_set):>6,}")
print()
print("=" * 70)
print(" 交集分析")
print("=" * 70)
print(f"两边都有:                       {len(in_both):>6,}")
print(f"  - 都标活跃(双向确认):          {len(in_both_active):>6,}")
print(f"  - eltdx 活跃, CK 已退市:       {len(eltdx_active_ck_delisted):>6,}")
print()
print(f"eltdx 有, CK 无 (=新股候选):   {len(in_eltdx_only):>6,}")
if in_eltdx_only:
    for c in sorted(in_eltdx_only)[:10]:
        print(f"  {c}  {eltdx_codes[c]['name']}")
print()
print(f"CK 有, eltdx 无 (=退市候选):   {len(in_ck_only):>6,}")
in_ck_only_active = sum(1 for c in in_ck_only if c in ck_active_set)
in_ck_only_delisted = len(in_ck_only) - in_ck_only_active
print(f"  其中: CK 标活跃={in_ck_only_active}, 标退市={in_ck_only_delisted}")
if in_ck_only and len(in_ck_only) < 20:
    for c in sorted(in_ck_only)[:5]:
        sym = ck_dict[c].get("symbol", "?")
        out = ck_dict[c].get("out_date_py", "?")
        print(f"  {c}  {sym}  out={out}")
print()
print("=" * 70)
print(" 关键发现")
print("=" * 70)
print()
print(f"1. eltdx 标活跃 + CK 也标活跃: {len(in_both_active):,} (双向一致)")
print(f"2. eltdx 漏掉的活跃股票:        {len(ck_active_eltdx_missing):,} (可能新股)")
print(f"3. eltdx 标活跃但 CK 已退市:   {len(eltdx_active_ck_delisted):,} (CK 数据滞后)")
print()
print("=" * 70)
print(" 结论: eltdx 单独作为代码源?")
print("=" * 70)
print()
if len(ck_active_eltdx_missing) > 0:
    print(f"✗ 不能完全替代 — eltdx 漏了 {len(ck_active_eltdx_missing)} 只活跃股")
    print(f"  (可能包括最近 IPO 的新股,eltdx 还没在 codes.list 反映)")
if len(eltdx_active_ck_delisted) > 0:
    print(f"✗ eltdx 还包含 {len(eltdx_active_ck_delisted)} 只 CK 已退市的")
    print(f"  (eltdx 滞后于 CK 的退市记录)")
print()
print("→ 推荐: 仍以 CK 为准, eltdx 作为备份+验证")