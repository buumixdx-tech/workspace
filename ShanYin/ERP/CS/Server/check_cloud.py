import sqlite3
conn = sqlite3.connect('/opt/shanyin-erp/data/business_system.db')
cur = conn.cursor()
cur.execute("SELECT id, type, transaction_date FROM virtual_contracts LIMIT 5")
print("VCs:")
for row in cur.fetchall():
    print(f"  {row}")

cur.execute("SELECT COUNT(*) FROM virtual_contracts WHERE elements LIKE '%batch_no%'")
print(f"\nWith batch_no: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM virtual_contracts WHERE elements LIKE '%\"batch_no\": \"20260317%'")
print(f"batch_no starting 20260317: {cur.fetchone()[0]}")

conn.close()