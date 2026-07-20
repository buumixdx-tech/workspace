"""
Migration 001: Add transaction_date to virtual_contracts table

1. ALTER TABLE virtual_contracts ADD COLUMN transaction_date DATE
2. Backfill: for each VC without transaction_date,
   extract transaction_date from its VC_CREATED SystemEvent payload
"""
import sys
sys.path.insert(0, ".")

from models import init_db
from sqlalchemy import text


def run():
    from datetime import datetime as dt

    init_db("sqlite:///data/business_system.db")
    # Import after init_db to avoid SessionLocal=None at import time
    from models import SessionLocal, VirtualContract, SystemEvent
    session = SessionLocal()

    # 1. Add column if not exists (SQLite supports IF NOT EXISTS from 3.35+)
    try:
        session.execute(text("ALTER TABLE virtual_contracts ADD COLUMN transaction_date DATE"))
        session.commit()
        print("[Migration] Column transaction_date added.")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            print("[Migration] Column transaction_date already exists, skipping.")
        else:
            session.rollback()
            print(f"[Migration] ALTER TABLE failed (may already exist): {e}")

    # 2. Backfill: extract transaction_date from VC_CREATED SystemEvent payload
    vcs = session.query(VirtualContract).filter(
        VirtualContract.transaction_date == None
    ).all()
    print(f"[Migration] {len(vcs)} VCs need backfill.")

    for vc in vcs:
        event = session.query(SystemEvent).filter(
            SystemEvent.aggregate_id == vc.id,
            SystemEvent.aggregate_type == "VirtualContract",
            SystemEvent.event_type == "VC_CREATED"
        ).order_by(SystemEvent.created_at.asc()).first()

        if event and event.payload:
            tx_date_str = event.payload.get("transaction_date") if isinstance(event.payload, dict) else None
            if tx_date_str:
                # Parse "2026-04-13" string into Python date object
                vc.transaction_date = dt.strptime(tx_date_str, "%Y-%m-%d").date()

    session.commit()
    filled = len(vcs)
    print(f"[Migration] Backfilled {filled} VCs with transaction_date.")

    # Verify
    total = session.query(VirtualContract).count()
    with_date = session.query(VirtualContract).filter(
        VirtualContract.transaction_date != None
    ).count()
    print(f"[Migration] Total VCs: {total}, with transaction_date: {with_date}, without: {total - with_date}")
    session.close()


if __name__ == "__main__":
    run()
