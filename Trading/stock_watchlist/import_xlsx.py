#!/usr/bin/env python3
"""
东方财富自选股 xlsx 批量导入工具。
A 股存储为 CK 标准格式（sz.000001），港股为 Yahoo Finance 格式（0700.HK），美股为（AAPL）。
用法: python import_xlsx.py [xlsx_dir]
"""
import sys, os, glob
sys.path.insert(0, '.')

import openpyxl

from src.db import init_db, upsert_stock, get_db, add_stock_to_sector
from src.core import normalize_code, normalize_code_ck
from src.yf import get_quote


def normalize(code_str: str) -> tuple[str, str] | None:
    """
    将东方财富格式代码转为 (storage_code, market) 元组。
    A 股：sz.000001 / sh.600000
    港股：0700.HK（Yahoo Finance 格式）
    美股：AAPL（Yahoo Finance 格式）
    """
    code = str(code_str).strip()
    if not code:
        return None

    # 已经是 CK 标准
    if code.startswith(('sz.', 'sh.', 'bj.')):
        return code, 'A'
    # 已经是 YF 格式
    if code.endswith('.HK'):
        return code, 'HK'
    if code[0].isupper() and code.isalnum():
        return code, 'US'

    # 港股：5位数字
    if len(code) == 5 and code.isdigit():
        yf_code = str(int(code)).zfill(4) + '.HK'  # 0700.HK
        return yf_code, 'HK'

    # 美股：字母开头
    if code[0].isalpha():
        return code.upper(), 'US'

    # A 股：6位数字
    if code.isdigit():
        digits = code.zfill(6)
        return normalize_code_ck(digits), 'A'

    return None


def import_xlsx(filepath: str) -> list[str]:
    """导入单个 xlsx，返回日志列表。"""
    basename = os.path.basename(filepath)
    sector_name = os.path.splitext(basename)[0]
    conn = get_db()

    # 建板块
    conn.execute("INSERT INTO sectors (name, color) VALUES (?, ?)", (sector_name, "#6b7280"))
    conn.commit()
    sector_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()['id']

    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active

    stock_count = 0
    errors = []

    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        code_val = row[1] if len(row) > 1 else None
        if not code_val:
            continue

        result = normalize(str(code_val))
        if not result:
            errors.append(f"row {i}: cannot normalize '{code_val}'")
            continue

        storage_code, market = result

        # upsert 本地缓存
        if market == 'A':
            try:
                from src import stocks as stocks_mod
                stocks_mod.add_stock(storage_code)
            except Exception as e:
                errors.append(f"row {i}: A-share eltdx failed {storage_code}: {e}")
                continue
        else:
            # 港美股：直接从 YF 获取 name
            yf_data = get_quote(storage_code)
            name = yf_data.get('long_name', storage_code) if yf_data else storage_code
            upsert_stock({
                "code": storage_code,
                "exchange": market,
                "name": name,
                "board": market,
                "board_name": market,
            })

        # 关联到板块
        try:
            add_stock_to_sector(sector_id, storage_code, "core")
            stock_count += 1
        except Exception as e:
            errors.append(f"row {i}: link failed {storage_code}: {e}")

    wb.close()
    return [f"[{sector_name}] imported {stock_count} stocks, {len(errors)} errors"] + errors


def main():
    xlsx_dir = sys.argv[1] if len(sys.argv) > 1 else "data/lists"
    files = glob.glob(os.path.join(xlsx_dir, "*.xlsx"))
    if not files:
        print(f"No xlsx found in {xlsx_dir}")
        return
    print(f"Found {len(files)} xlsx files")
    for fp in sorted(files):
        print(f"Processing: {os.path.basename(fp)} ...", flush=True)
        for line in import_xlsx(fp):
            print(f"  {line}")
    # I11: 灌库完成,通知 daemon 重算 — 否则前端 metrics 要等 30s TTL 过期
    _notify_daemon_if_running()
    print("\nDone.")


def _notify_daemon_if_running():
    """尝试 POST /api/admin/recompute。如果 daemon 没跑,失败也无所谓。"""
    import socket
    import urllib.request
    from src.config_loader import SERVER_HOST, SERVER_PORT
    # 探测端口,daemon 不在就别浪费时间
    try:
        with socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=1):
            pass
    except (OSError, socket.timeout):
        print("(daemon 不在,跳过重算通知 — 下次启动会自动加载新数据)")
        return
    try:
        url = f"http://{SERVER_HOST}:{SERVER_PORT}/api/admin/recompute"
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"[notify] daemon 重算触发: HTTP {resp.status}")
    except Exception as e:
        print(f"[notify] daemon 通知失败(不影响导入): {e}")


if __name__ == "__main__":
    init_db()
    main()
