#!/usr/bin/env python3
"""将数据库中的港美股代码统一为 Yahoo Finance 格式。"""
import sys
sys.path.insert(0, '.')

from src.db import get_db


def hk_to_yf(code: str) -> str:
    """hk00700 → 0700.HK"""
    if code.startswith('hk'):
        num = str(int(code[2:]))  # 去掉前导零
        return num.zfill(4) + '.HK'
    return code


def us_to_yf(code: str) -> str:
    """usAAPL → AAPL (大写)"""
    if code.startswith('us'):
        return code[2:].upper()
    return code


def yf_to_hk(code: str) -> str:
    """0700.HK → hk00700 (反向，用于检测)"""
    if code.endswith('.HK'):
        num = code[:-3]  # 去掉 .HK
        return 'hk' + num.zfill(6)
    return None


def yf_to_us(code: str) -> str:
    """AAPL → usAAPL (反向，用于检测)"""
    if not code.endswith('.HK') and not code.startswith(('sh', 'sz', 'bj', 'hk')) and code[0].isupper():
        return 'us' + code
    return None


def migrate_codes():
    conn = get_db()

    # 找出所有需要迁移的股票
    rows = conn.execute("SELECT code, name FROM stocks WHERE code LIKE 'hk%' OR code LIKE 'us%'").fetchall()
    print(f'Found {len(rows)} HK/US stocks to migrate')

    for r in rows:
        old_code = r['code']
        new_code = None
        if old_code.startswith('hk'):
            new_code = hk_to_yf(old_code)
        elif old_code.startswith('us'):
            new_code = us_to_yf(old_code)

        if new_code and new_code != old_code:
            # 更新 stocks 表
            conn.execute("UPDATE stocks SET code=? WHERE code=?", (new_code, old_code))
            # 更新 sector_stocks 表
            conn.execute("UPDATE sector_stocks SET stock_code=? WHERE stock_code=?", (new_code, old_code))
            print(f'  {old_code} → {new_code}')

    conn.commit()
    print('Migration done.')


if __name__ == '__main__':
    migrate_codes()
