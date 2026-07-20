#!/usr/bin/env python3
"""对比 CK 与 akshare 主表,找出差异."""

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def to_ck_code(raw):
    s = str(raw)
    if len(s) != 6 or not s.isdigit():
        return s.lower()
    if s[0] in ("6", "9", "5", "7"):
        return f"sh.{s}"
    return f"sz.{s}"


import akshare as ak
import clickhouse_connect
from datetime import date

# akshare 主表
akshare_df = ak.stock_info_a_code_name()
akshare_df["ck_code"] = akshare_df["code"].apply(to_ck_code)
akshare_set = set(akshare_df["ck_code"].tolist())
akshare_dict = dict(zip(akshare_df["ck_code"], akshare_df["name"]))

# CK
ck = clickhouse_connect.get_client(
    host="127.0.0.1", port=8123, username="admin", password="admin_password", database="stock_data"
)
ck_df = ck.query_df("SELECT code, symbol, out_date FROM stock_data.securities_info")
ck_df["out_date_py"] = ck_df["out_date"].apply(lambda x: x.date() if hasattr(x, "date") else x)
ck_set = set(ck_df["code"].tolist())

today = date.today()
ck_active = ck_df[ck_df["out_date_py"] > today]
ck_delisted = ck_df[ck_df["out_date_py"] <= today]

# akshare 主表含退的
akshare_with_delist = akshare_df[akshare_df["name"].str.contains("退", na=False)]
akshare_pure_active = akshare_set - set(akshare_with_delist["ck_code"].tolist())

print("=" * 70)
print(" 5533 vs 5528 差异分析")
print("=" * 70)
print()
print(f"CK 总数:               {len(ck_set):>6,}")
print(f"  - 活跃 (out>today):  {len(ck_active):>6,}")
print(f"  - 退市 (out<=today): {len(ck_delisted):>6,}")
print()
print(f"akshare 主表总数:       {len(akshare_set):>6,}")
print(f"  - 含退字残留:        {len(akshare_with_delist):>6,}")
print(f"  - 纯活跃:            {len(akshare_pure_active):>6,}")
print()

# 4 个集合
in_both = ck_set & akshare_set
in_ck_only = ck_set - akshare_set
in_ak_only = akshare_set - ck_set

print(f"两边都有:               {len(in_both):>6,}")
print(f"CK 有, akshare 无:       {len(in_ck_only):>6,}  ← 新发现退市")
print(f"akshare 有, CK 无:       {len(in_ak_only):>6,}  ← 新股")
print()

if in_ck_only:
    print(f"--- CK 有但 akshare 无 ({len(in_ck_only)} 只,可能已退市) ---")
    in_ck_only_active = 0
    in_ck_only_delisted = 0
    for c in sorted(in_ck_only):
        is_active = (ck_df[ck_df['code']==c]['out_date_py'].iloc[0] > today)
        if is_active:
            in_ck_only_active += 1
        else:
            in_ck_only_delisted += 1
        # 打印细节
        out_d = ck_df[ck_df['code']==c]['out_date_py'].iloc[0]
        sym = ck_df[ck_df['code']==c]['symbol'].iloc[0]
        status = '活跃(out>today)' if out_d > today else f'退市(out={out_d})'
        print(f"  {c}  {sym:10s}  {status}")
    print()
    print(f"  其中: 活跃={in_ck_only_active}, 退市={in_ck_only_delisted}")

if in_ak_only:
    print()
    print(f"--- akshare 有但 CK 无 ({len(in_ak_only)} 只,新股候选) ---")
    for c in sorted(in_ak_only)[:15]:
        name = akshare_dict.get(c, "?")
        print(f"  {c}  {name}")
    if len(in_ak_only) > 15:
        print(f"  ... 还有 {len(in_ak_only)-15} 只")