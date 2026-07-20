"""
SQLite Trigger-Based Audit System

字段级审计日志：记录每个事务内哪些字段从什么值变成了什么值。
通过 operation_context 永久表传递 event_id，触发器自动写入 audit_log。
operation_context 使用全局单行（conn_id='default'），所有连接共享。
"""
import json
import logging
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import text

logger = logging.getLogger(__name__)

_thread_local_audit = threading.local()


# =============================================================================
# DDL
# =============================================================================

AUDIT_LOG_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER,
    user_id VARCHAR(100),
    action_name VARCHAR(100),
    started_at DATETIME,
    table_name VARCHAR(50) NOT NULL,
    event_type VARCHAR(10) NOT NULL,
    row_id INTEGER NOT NULL,
    old_values JSON,
    new_values JSON,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

AUDIT_LOG_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_audit_event ON audit_log(event_id)",
    "CREATE INDEX IF NOT EXISTS ix_audit_table_row ON audit_log(table_name, row_id)",
    "CREATE INDEX IF NOT EXISTS ix_audit_recorded ON audit_log(recorded_at)",
]

# 永久表，全局单行，所有连接共享
OPERATION_CONTEXT_DDL = """
CREATE TABLE IF NOT EXISTS operation_context (
    conn_id VARCHAR(100) PRIMARY KEY,
    event_id INTEGER,
    user_id VARCHAR(100),
    action_name VARCHAR(100),
    started_at DATETIME,
    in_context INTEGER DEFAULT 0
)
"""


# =============================================================================
# Trigger builders
# SQLite 触发器不能使用 bind 参数，改为硬编码 conn_id='default'
# =============================================================================

def _trigger_ai(table: str, cols: list) -> str:
    """AFTER INSERT - INSERT..WHERE in_context=1"""
    cols_str = ", ".join([f"'{c}', NEW.{c}" for c in cols])
    return f"""CREATE TRIGGER IF NOT EXISTS {table}_ai AFTER INSERT ON {table}
BEGIN
    INSERT INTO audit_log (event_id, user_id, action_name, started_at, table_name, event_type, row_id, old_values, new_values)
    SELECT
        (SELECT event_id FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        (SELECT user_id FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        (SELECT action_name FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        (SELECT started_at FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        '{table}', 'INSERT', NEW.id, NULL,
        json_object({cols_str})
    WHERE (SELECT COUNT(*) FROM operation_context WHERE conn_id = 'default' AND in_context = 1) > 0;
END"""


def _trigger_au(table: str, cols: list) -> str:
    """AFTER UPDATE - INSERT..WHERE in_context=1 AND 列有变化"""
    cond = " OR ".join([f"OLD.{c} != NEW.{c}" for c in cols])
    cols_str = ", ".join([f"'{c}', OLD.{c}" for c in cols])
    new_cols_str = ", ".join([f"'{c}', NEW.{c}" for c in cols])
    return f"""CREATE TRIGGER IF NOT EXISTS {table}_au AFTER UPDATE ON {table}
BEGIN
    INSERT INTO audit_log (event_id, user_id, action_name, started_at, table_name, event_type, row_id, old_values, new_values)
    SELECT
        (SELECT event_id FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        (SELECT user_id FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        (SELECT action_name FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        (SELECT started_at FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        '{table}', 'UPDATE', NEW.id,
        json_object({cols_str}),
        json_object({new_cols_str})
    WHERE (SELECT COUNT(*) FROM operation_context WHERE conn_id = 'default' AND in_context = 1) > 0
      AND ({cond});
END"""


def _trigger_ad(table: str, cols: list) -> str:
    """AFTER DELETE - INSERT..WHERE in_context=1"""
    cols_str = ", ".join([f"'{c}', OLD.{c}" for c in cols])
    return f"""CREATE TRIGGER IF NOT EXISTS {table}_ad AFTER DELETE ON {table}
BEGIN
    INSERT INTO audit_log (event_id, user_id, action_name, started_at, table_name, event_type, row_id, old_values, new_values)
    SELECT
        (SELECT event_id FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        (SELECT user_id FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        (SELECT action_name FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        (SELECT started_at FROM operation_context WHERE conn_id = 'default' AND in_context = 1),
        '{table}', 'DELETE', OLD.id,
        json_object({cols_str}), NULL
    WHERE (SELECT COUNT(*) FROM operation_context WHERE conn_id = 'default' AND in_context = 1) > 0;
END"""


# =============================================================================
# Trigger DDL Map — 10 tables × 3 events = 30 triggers
# =============================================================================

TRIGGER_DDL_MAP = {

    "business": {
        "ai": _trigger_ai("business", ["customer_id", "status", "timestamp", "details"]),
        "au": _trigger_au("business", ["customer_id", "status", "timestamp", "details"]),
        "ad": _trigger_ad("business", ["customer_id", "status", "timestamp", "details"]),
    },

    "virtual_contracts": {
        "ai": _trigger_ai("virtual_contracts", [
            "description", "business_id", "supply_chain_id", "related_vc_id", "type", "summary",
            "elements", "return_direction", "deposit_info", "status",
            "subject_status", "cash_status", "status_timestamp",
            "subject_status_timestamp", "cash_status_timestamp"
        ]),
        "au": _trigger_au("virtual_contracts", [
            "description", "business_id", "supply_chain_id", "related_vc_id", "type", "summary",
            "elements", "return_direction", "deposit_info", "status",
            "subject_status", "cash_status", "status_timestamp",
            "subject_status_timestamp", "cash_status_timestamp"
        ]),
        "ad": _trigger_ad("virtual_contracts", [
            "description", "business_id", "supply_chain_id", "related_vc_id", "type", "summary",
            "elements", "return_direction", "deposit_info", "status",
            "subject_status", "cash_status", "status_timestamp",
            "subject_status_timestamp", "cash_status_timestamp"
        ]),
    },

    "logistics": {
        "ai": _trigger_ai("logistics", ["virtual_contract_id", "finance_triggered", "status", "timestamp"]),
        "au": _trigger_au("logistics", ["virtual_contract_id", "finance_triggered", "status", "timestamp"]),
        "ad": _trigger_ad("logistics", ["virtual_contract_id", "finance_triggered", "status", "timestamp"]),
    },

    "express_orders": {
        "ai": _trigger_ai("express_orders", ["logistics_id", "tracking_number", "items", "address_info", "status", "timestamp"]),
        "au": _trigger_au("express_orders", ["logistics_id", "tracking_number", "items", "address_info", "status", "timestamp"]),
        "ad": _trigger_ad("express_orders", ["logistics_id", "tracking_number", "items", "address_info", "status", "timestamp"]),
    },

    "cash_flows": {
        "ai": _trigger_ai("cash_flows", [
            "virtual_contract_id", "type", "amount", "payer_account_id", "payee_account_id",
            "finance_triggered", "payment_info", "voucher_path", "description", "transaction_date", "timestamp"
        ]),
        "au": _trigger_au("cash_flows", [
            "virtual_contract_id", "type", "amount", "payer_account_id", "payee_account_id",
            "finance_triggered", "payment_info", "voucher_path", "description", "transaction_date", "timestamp"
        ]),
        "ad": _trigger_ad("cash_flows", [
            "virtual_contract_id", "type", "amount", "payer_account_id", "payee_account_id",
            "finance_triggered", "payment_info", "voucher_path", "description", "transaction_date", "timestamp"
        ]),
    },

    "cash_flow_ledger": {
        "ai": _trigger_ai("cash_flow_ledger", ["journal_id", "main_category", "direction", "amount"]),
        "au": _trigger_au("cash_flow_ledger", ["journal_id", "main_category", "direction", "amount"]),
        "ad": _trigger_ad("cash_flow_ledger", ["journal_id", "main_category", "direction", "amount"]),
    },

    "supply_chains": {
        "ai": _trigger_ai("supply_chains", ["supplier_id", "type", "contract_id", "payment_terms"]),
        "au": _trigger_au("supply_chains", ["supplier_id", "type", "contract_id", "payment_terms"]),
        "ad": _trigger_ad("supply_chains", ["supplier_id", "type", "contract_id", "payment_terms"]),
    },

    "supply_chain_items": {
        "ai": _trigger_ai("supply_chain_items", ["supply_chain_id", "sku_id", "price", "is_floating"]),
        "au": _trigger_au("supply_chain_items", ["supply_chain_id", "sku_id", "price", "is_floating"]),
        "ad": _trigger_ad("supply_chain_items", ["supply_chain_id", "sku_id", "price", "is_floating"]),
    },

    "equipment_inventory": {
        "ai": _trigger_ai("equipment_inventory", [
            "sku_id", "sn", "operational_status", "device_status", "virtual_contract_id",
            "point_id", "deposit_amount", "deposit_timestamp"
        ]),
        "au": _trigger_au("equipment_inventory", [
            "sku_id", "sn", "operational_status", "device_status", "virtual_contract_id",
            "point_id", "deposit_amount", "deposit_timestamp"
        ]),
        "ad": _trigger_ad("equipment_inventory", [
            "sku_id", "sn", "operational_status", "device_status", "virtual_contract_id",
            "point_id", "deposit_amount", "deposit_timestamp"
        ]),
    },

    "material_inventory": {
        "ai": _trigger_ai("material_inventory", [
            "sku_id", "batch_no", "latest_purchase_vc_id", "point_id", "qty",
            "certificate_file", "production_date", "expiration_date", "status"
        ]),
        "au": _trigger_au("material_inventory", [
            "sku_id", "batch_no", "latest_purchase_vc_id", "point_id", "qty",
            "certificate_file", "production_date", "expiration_date", "status"
        ]),
        "ad": _trigger_ad("material_inventory", [
            "sku_id", "batch_no", "latest_purchase_vc_id", "point_id", "qty",
            "certificate_file", "production_date", "expiration_date", "status"
        ]),
    },
}


# =============================================================================
# Core Functions
# =============================================================================

def init_audit_system(engine):
    """初始化审计系统：在数据库创建时调用一次"""
    with engine.connect() as conn:
        conn.execute(text(AUDIT_LOG_TABLE_DDL))
        for idx_ddl in AUDIT_LOG_INDEXES:
            conn.execute(text(idx_ddl))
        conn.execute(text(OPERATION_CONTEXT_DDL))
        for table_name, triggers in TRIGGER_DDL_MAP.items():
            for trigger_type, ddl in triggers.items():
                try:
                    conn.execute(text(ddl))
                except Exception as e:
                    logger.warning(f"Trigger creation warning for {table_name}_{trigger_type}: {e}")
        conn.commit()
    logger.info("Audit system initialized: audit_log + operation_context + 30 triggers created")


def set_audit_event_id(event_id: int):
    """在 audit_context 上下文中设置 event_id。写入 operation_context，后续所有触发器都能读到。"""
    from models import _thread_local_session
    session = getattr(_thread_local_session, 'current', None)
    if session is None:
        return
    try:
        session.execute(
            text("UPDATE operation_context SET event_id = :eid WHERE conn_id = 'default'"),
            {"eid": event_id}
        )
    except Exception:
        pass


@contextmanager
def audit_context(action_name: str, user_id: str = None):
    """
    上下文管理器。在 operation_context 表中写入一行，触发器通过该表读取 event_id。

    注意：调用 get_session() 后，session 存储在 thread-local，audit_context 自动使用该 session
    的底层连接，确保触发器能看见上下文。
    用法：
        with audit_context("create_procurement_vc_action"):
            session.add(vc)
            evt = emit_event(...)
            set_audit_event_id(evt.id)
            session.commit()
    """
    from models import _thread_local_session, engine
    session = getattr(_thread_local_session, 'current', None)
    if session is None:
        yield
        return

    started_at = datetime.now().isoformat()

    with session.begin():
        session.execute(text("DELETE FROM operation_context WHERE conn_id = 'default'"))
        session.execute(
            text("INSERT INTO operation_context (conn_id, event_id, user_id, action_name, started_at, in_context) VALUES ('default', NULL, :uid, :aname, :started, 1)"),
            {"uid": user_id, "aname": action_name, "started": started_at}
        )

    try:
        yield
    finally:
        try:
            with engine.connect() as conn:
                conn.execute(text("DELETE FROM operation_context WHERE conn_id = 'default'"))
                conn.commit()
        except Exception:
            pass


def get_audit_log(event_id: int) -> List[Dict[str, Any]]:
    """查询某次业务事件的所有 audit_log 条目"""
    from models import engine
    with engine.connect() as conn:
        result = conn.execute(
            text("""SELECT id, event_id, user_id, action_name, started_at,
                           table_name, event_type, row_id, old_values, new_values, recorded_at
                    FROM audit_log WHERE event_id = :eid ORDER BY id"""),
            {"eid": event_id}
        )
        rows = []
        for row in result:
            rows.append({
                'id': row[0],
                'event_id': row[1],
                'user_id': row[2],
                'action_name': row[3],
                'started_at': row[4],
                'table_name': row[5],
                'event_type': row[6],
                'row_id': row[7],
                'old_values': json.loads(row[8]) if row[8] else None,
                'new_values': json.loads(row[9]) if row[9] else None,
                'recorded_at': row[10],
            })
        return rows


def get_table_history(table_name: str, row_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """查询某张表某行的完整变更历史"""
    from models import engine
    with engine.connect() as conn:
        result = conn.execute(
            text("""SELECT id, event_id, user_id, action_name, started_at,
                           table_name, event_type, row_id, old_values, new_values, recorded_at
                    FROM audit_log
                    WHERE table_name = :tname AND row_id = :rid
                    ORDER BY id DESC LIMIT :lim"""),
            {"tname": table_name, "rid": row_id, "lim": limit}
        )
        rows = []
        for row in result:
            rows.append({
                'id': row[0],
                'event_id': row[1],
                'user_id': row[2],
                'action_name': row[3],
                'started_at': row[4],
                'table_name': row[5],
                'event_type': row[6],
                'row_id': row[7],
                'old_values': json.loads(row[8]) if row[8] else None,
                'new_values': json.loads(row[9]) if row[9] else None,
                'recorded_at': row[10],
            })
        return rows
