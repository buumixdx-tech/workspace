#!/usr/bin/env python3
"""stock_watchlist CLI"""
import sys, argparse
sys.path.insert(0, '.')

from src.db import init_db, get_db, add_stock_to_sector, remove_stock_from_sector
from src import stocks as stocks_mod
from src.core import normalize_code


def list_sectors():
    conn = get_db()
    rows = conn.execute("SELECT id, name, parent_id, color FROM sectors ORDER BY sort_order").fetchall()
    if not rows:
        print("[no sectors]")
        return
    for r in rows:
        indent = "  " if r["parent_id"] else ""
        print(f"{indent}[{r['id']}] {r['name']}  {'#' + r['color'] if r['color'] else ''}")


def list_stocks(sector_id=None):
    conn = get_db()
    if sector_id:
        rows = conn.execute("""
            SELECT ss.stock_code, ss.label, s.name, s.board_name
            FROM sector_stocks ss
            JOIN stocks s ON s.code = ss.stock_code
            WHERE ss.sector_id = ?
            ORDER BY ss.sort_order
        """, (sector_id,)).fetchall()
    else:
        rows = conn.execute("SELECT code, name, board_name FROM stocks ORDER BY name").fetchall()
    if not rows:
        print("[no stocks]")
        return
    for r in rows:
        if sector_id:
            tag = "[core]" if r["label"] == "core" else "[obs]"
            print(f"  {tag} {r['stock_code']} {r['name']} ({r['board_name'] or ''})")
        else:
            print(f"  {r['code']} {r['name']} ({r['board_name'] or ''})")


def add_stock_to_sector_cli(code, sector_id, label="core"):
    normalized = normalize_code(code)
    stocks_mod.add_stock(normalized)
    add_stock_to_sector(sector_id, normalized, label)
    print(f"[+] {normalized} -> sector {sector_id} as {label}")


def remove_stock_from_sector_cli(code, sector_id):
    normalized = normalize_code(code)
    remove_stock_from_sector(sector_id, normalized)
    print(f"[-] {normalized} removed from sector {sector_id}")


def create_sector_cli(name, parent_id=None, color="#6b7280"):
    conn = get_db()
    conn.execute(
        "INSERT INTO sectors (name, parent_id, color) VALUES (?, ?, ?)",
        (name, parent_id, color)
    )
    conn.commit()
    row = conn.execute("SELECT last_insert_rowid() as id").fetchone()
    print(f"[+] sector '{name}' created (ID: {row['id']})")


def delete_sector_cli(sector_id):
    conn = get_db()
    conn.execute("DELETE FROM sectors WHERE id = ?", (sector_id,))
    conn.commit()
    print(f"[-] sector {sector_id} deleted")


def update_label_cli(code, sector_id, label):
    conn = get_db()
    conn.execute(
        "UPDATE sector_stocks SET label = ? WHERE sector_id = ? AND stock_code = ?",
        (label, sector_id, code)
    )
    conn.commit()
    print(f"[*] {code} label -> {label}")


def search_stocks_cli(q):
    cache = stocks_mod.get_all()
    q = q.upper()
    results = [s for s in cache if q in s["code"].upper() or q in s["name"].upper()]
    for s in results[:20]:
        print(f"  {s['code']} {s['name']} ({s.get('board_name', '')})")


def main():
    parser = argparse.ArgumentParser(description="stock_watchlist CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("sectors", help="list sectors")
    sub.add_parser("stocks", help="list stocks").add_argument("--sector", "-s", type=int, help="sector ID")
    p_add = sub.add_parser("add", help="add stock to sector")
    p_add.add_argument("code", help="stock code")
    p_add.add_argument("sector", type=int, help="sector ID")
    p_add.add_argument("--label", "-l", default="core", choices=["core", "observation"])
    p_remove = sub.add_parser("remove", help="remove stock from sector")
    p_remove.add_argument("code", help="stock code")
    p_remove.add_argument("sector", type=int, help="sector ID")
    p_setlabel = sub.add_parser("setlabel", help="update label")
    p_setlabel.add_argument("code", help="stock code")
    p_setlabel.add_argument("sector", type=int, help="sector ID")
    p_setlabel.add_argument("label", choices=["core", "observation"])
    p_create = sub.add_parser("create-sector", help="create sector")
    p_create.add_argument("name", help="sector name")
    p_create.add_argument("--parent", "-p", type=int)
    p_create.add_argument("--color", "-c", default="#6b7280")
    p_delete = sub.add_parser("delete-sector", help="delete sector")
    p_delete.add_argument("sector", type=int)
    sub.add_parser("search", help="search stocks").add_argument("q", help="query")

    args = parser.parse_args()

    if args.cmd == "sectors":
        list_sectors()
    elif args.cmd == "stocks":
        list_stocks(args.sector)
    elif args.cmd == "add":
        add_stock_to_sector_cli(args.code, args.sector, args.label)
    elif args.cmd == "remove":
        remove_stock_from_sector_cli(args.code, args.sector)
    elif args.cmd == "setlabel":
        update_label_cli(args.code, args.sector, args.label)
    elif args.cmd == "create-sector":
        create_sector_cli(args.name, args.parent, args.color)
    elif args.cmd == "delete-sector":
        delete_sector_cli(args.sector)
    elif args.cmd == "search":
        search_stocks_cli(args.q)
    else:
        parser.print_help()


if __name__ == "__main__":
    init_db()
    main()
