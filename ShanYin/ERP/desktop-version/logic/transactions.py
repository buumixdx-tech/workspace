"""
操作回滚事务管理模块

提供快照序列化、事务记录、回滚/撤销回滚能力。
"""
import os
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from models import (
    Base, OperationTransaction,
    VirtualContract, Logistics, ExpressOrder, CashFlow,
    FinancialJournal, CashFlowLedger, TimeRule, SystemEvent,
    EquipmentInventory, MaterialInventory,
    ChannelCustomer, Supplier, SKU, Business, Point,
    FinanceAccount, BankAccount,
)

logger = logging.getLogger(__name__)

# ============ Model Class 映射 ============

_MODEL_CLASSES = {
    "VirtualContract": VirtualContract,
    "Logistics": Logistics,
    "ExpressOrder": ExpressOrder,
    "CashFlow": CashFlow,
    "FinancialJournal": FinancialJournal,
    "CashFlowLedger": CashFlowLedger,
    "TimeRule": TimeRule,
    "SystemEvent": SystemEvent,
    "EquipmentInventory": EquipmentInventory,
    "MaterialInventory": MaterialInventory,
    "ChannelCustomer": ChannelCustomer,
    "Supplier": Supplier,
    "SKU": SKU,
    "Business": Business,
    "Point": Point,
    "FinanceAccount": FinanceAccount,
    "BankAccount": BankAccount,
}


def get_model(class_name: str):
    """将类名字符串转换为实际的 SQLAlchemy 模型类"""
    return _MODEL_CLASSES.get(class_name)


# ============ 序列化工具 ============

def serialize_model(model) -> Dict[str, Any]:
    """
    将 SQLAlchemy 模型序列化为 JSON-safe dict。
    排除 _ 开头字段和 SQLAlchemy 内部字段。
    """
    result = {}
    for key, value in model.__dict__.items():
        if key.startswith("_"):
            continue
        if key in ("metadata", "registry"):
            continue
        if hasattr(value, "__dict__"):  # SQLAlchemy relationship objects
            continue
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


def serialize_session_new_records(session: Session) -> List[Dict[str, Any]]:
    """
    序列化 session.new 中所有新记录。
    用于纯新建 Action 的 snapshot_after。

    注意：flush() 会清空 session.new，请在 flush 之前调用。
    """
    records = []
    for obj in session.new:
        records.append({
            "class": obj.__class__.__name__,
            "id": obj.id,
            "data": serialize_model(obj),
        })
    return records


def serialize_objs(objs: List[Any]) -> List[Dict[str, Any]]:
    """
    直接序列化对象列表（不依赖 session.new）。
    在 flush 之前调用，传入所有新创建的对象。
    """
    records = []
    for obj in objs:
        records.append({
            "class": obj.__class__.__name__,
            "id": obj.id,
            "data": serialize_model(obj),
        })
    return records


def serialize_dirty_records(session: Session) -> List[Dict[str, Any]]:
    """
    序列化 session.dirty 中所有记录的 committed_state（旧值）和当前值。
    用于修改/删除 Action 的 snapshot_before。
    """
    records = []
    for obj in session.dirty:
        committed = dict(obj._sa_instance_state.committed_state) if hasattr(obj, "_sa_instance_state") else {}
        records.append({
            "class": obj.__class__.__name__,
            "id": obj.id,
            "before": committed,
            "after": serialize_model(obj),
        })
    return records


def serialize_snapshot_before(session: Session, target_objs: List[Any]) -> Dict[str, Any]:
    """
    序列化指定的现有记录作为 snapshot_before。
    用于混合 Action（如 confirm_inbound），需要明确查询哪些现有记录被修改。
    """
    records = []
    for obj in target_objs:
        records.append({
            "class": obj.__class__.__name__,
            "id": obj.id,
            "data": serialize_model(obj),
        })
    return {"records": records}


# ============ 事务记录操作 ============

def create_operation_record(
    session: Session,
    action_name: str,
    ref_type: str,
    ref_id: int,
    ref_vc_id: Optional[int] = None,
    snapshot_before: Optional[Dict] = None,
    snapshot_after: Optional[Dict] = None,
    involved_ids: Optional[List[int]] = None,
) -> int:
    """
    在所有 DB 改动完成后调用，创建事务记录。

    Returns:
        transaction id
    """
    tx = OperationTransaction(
        action_name=action_name,
        ref_type=ref_type,
        ref_id=ref_id,
        ref_vc_id=ref_vc_id,
        snapshot_before=snapshot_before or {},
        snapshot_after=snapshot_after or {},
        involved_ids=involved_ids or [],
        status="committed",
    )
    session.add(tx)
    session.flush()
    return tx.id


def complete_operation_record(tx_id: int, snapshot_after: Dict[str, Any], session: Session = None):
    """更新事务记录，写入 snapshot_after"""
    # 注意：session 可能从 context 中获取，此处支持传参
    if session is None:
        from models import engine
        from sqlalchemy.orm import Session as SASession
        with SASession(bind=engine) as s:
            tx = s.query(OperationTransaction).get(tx_id)
            if tx:
                tx.snapshot_after = snapshot_after
                s.flush()
    else:
        tx = session.query(OperationTransaction).get(tx_id)
        if tx:
            tx.snapshot_after = snapshot_after
            session.flush()


def update_transaction_status(tx_id: int, status: str, reason: Optional[str] = None, session: Session = None):
    """更新事务状态（用于标记失败）"""
    if session is None:
        from models import engine
        from sqlalchemy.orm import Session as SASession
        with SASession(bind=engine) as s:
            tx = s.query(OperationTransaction).get(tx_id)
            if tx:
                tx.status = status
                if reason:
                    tx.reason = reason
                s.flush()
    else:
        tx = session.query(OperationTransaction).get(tx_id)
        if tx:
            tx.status = status
            if reason:
                tx.reason = reason
            session.flush()


# ============ 回滚核心逻辑 ============

def _delete_json_files(files: List[Dict[str, str]]):
    """删除快照中记录的 JSON 文件"""
    for file in files:
        path = file.get("path") or file.get("filename")
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                logger.warning(f"Failed to delete file {path}: {e}")


def rollback_operation(session: Session, tx_id: int, reason: str = None) -> "ActionResult":
    """
    执行回滚：用 snapshot_before 物理恢复所有表。
    """
    from logic.base import ActionResult

    tx = session.query(OperationTransaction).get(tx_id)
    if tx is None:
        return ActionResult(success=False, error=f"事务记录 {tx_id} 不存在")

    if tx.status == "rolled_back":
        return ActionResult(success=False, error="该操作已被回滚，不允许重复回滚")

    if tx.status == "failed":
        return ActionResult(success=False, error="该操作执行失败，无需回滚")

    # FINISH 状态 VC 禁止回滚
    if tx.ref_type == "VirtualContract":
        vc = session.query(VirtualContract).filter(VirtualContract.id == tx.ref_id).with_for_update().first()
        if vc and vc.status == "完成":
            return ActionResult(success=False, error="已完成合同不允许回滚")

    try:
        # 1. DELETE 新记录（snapshot_after 中所有 records）
        for record in reversed(tx.snapshot_after.get("records", [])):
            model_class = get_model(record["class"])
            if model_class is None:
                logger.warning(f"Unknown model class: {record['class']}")
                continue
            obj = session.query(model_class).get(record["id"])
            if obj:
                session.delete(obj)

        # 2. UPDATE 回旧值（snapshot_before 中所有 records）
        for record in tx.snapshot_before.get("records", []):
            model_class = get_model(record["class"])
            if model_class is None:
                continue
            obj = session.query(model_class).get(record["id"])
            if obj:
                for attr, old_val in record["data"].items():
                    setattr(obj, attr, old_val)

        # 3. 删除 JSON 文件
        _delete_json_files(tx.snapshot_after.get("files", []))

        # 4. void_report 清理 report.json
        for record in tx.snapshot_after.get("records", []):
            if record["class"] == "FinancialJournal":
                data = record.get("data", {})
                ts = data.get("transaction_date")
                if ts:
                    dt = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
                    void_report(data.get("ref_type"), data.get("ref_id"), dt)

        # 5. 更新事务状态
        tx.status = "rolled_back"
        tx.reason = reason
        tx.rolled_back_at = datetime.now()
        session.flush()

        return ActionResult(success=True)

    except Exception as e:
        logger.error(f"Rollback failed for tx {tx_id}: {e}", exc_info=True)
        return ActionResult(success=False, error=f"回滚执行失败: {e}")


def redo_operation(session: Session, tx_id: int) -> "ActionResult":
    """
    撤销回滚：用 snapshot_after 重新应用。
    """
    from logic.base import ActionResult

    tx = session.query(OperationTransaction).get(tx_id)
    if tx is None:
        return ActionResult(success=False, error=f"事务记录 {tx_id} 不存在")

    if tx.status != "rolled_back":
        return ActionResult(success=False, error="该操作未被回滚，无法撤销回滚")

    try:
        # 1. 从 snapshot_after 重建所有记录
        for record in tx.snapshot_after.get("records", []):
            model_class = get_model(record["class"])
            if model_class is None:
                logger.warning(f"Unknown model class: {record['class']}")
                continue
            # 检查记录是否已存在（可能被其他操作创建了）
            existing = session.query(model_class).get(record["id"])
            if existing:
                # 更新为快照中的值
                for attr, val in record["data"].items():
                    setattr(existing, attr, val)
            else:
                obj = model_class(**record["data"])
                session.add(obj)

        session.flush()

        # 2. 重建 JSON 文件（如果文件存在则跳过，幂等）
        for file in tx.snapshot_after.get("files", []):
            path = file.get("path") or file.get("filename")
            content = file.get("content")
            if path and content and not os.path.exists(path):
                try:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(content, f, ensure_ascii=False, indent=2)
                except OSError as e:
                    logger.warning(f"Failed to recreate file {path}: {e}")

        # 3. update_report 幂等追加
        for file in tx.snapshot_after.get("files", []):
            content = file.get("content")
            if content:
                # update_report 需要 voucher 数据
                try:
                    _update_report_unsafe(content)
                except Exception as e:
                    logger.warning(f"Failed to update report: {e}")

        # 4. 更新事务状态
        tx.status = "committed"
        tx.reason = None
        tx.rolled_back_at = None
        tx.rolled_back_by = None
        session.flush()

        return ActionResult(success=True)

    except Exception as e:
        logger.error(f"Redo failed for tx {tx_id}: {e}", exc_info=True)
        return ActionResult(success=False, error=f"撤销回滚执行失败: {e}")


# ============ report.json 操作 ============

def _get_report_path(report_dir: str = None) -> str:
    """获取 report.json 路径"""
    if report_dir:
        return os.path.join(report_dir, "report.json")
    from logic.finance.engine import REPORT_DIR
    return os.path.join(REPORT_DIR, "report.json")


def _load_report(report_path: str) -> Dict[str, Any]:
    """加载 report.json，文件不存在时返回空结构"""
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load report: {e}")
            return {}
    return {}


def _save_report(report_path: str, report: Dict[str, Any]):
    """保存 report.json"""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def _update_report_unsafe(voucher: Dict[str, Any], report_dir: str = None):
    """
    内部用：追加凭证到 report.json（幂等去重）。
    直接操作文件，不检查 session 状态。
    """
    report_path = _get_report_path(report_dir)
    report = _load_report(report_path)

    ts_str = voucher.get("timestamp")
    dt = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
    month = dt.strftime("%Y-%m")

    if month not in report:
        report[month] = {"vouchers": [], "summary": {}}

    # 幂等去重 by voucher_no
    voucher_no = voucher.get("voucher_no")
    existing_vnos = {v.get("voucher_no") for v in report[month].get("vouchers", [])}
    if voucher_no and voucher_no in existing_vnos:
        return  # 已存在，跳过

    report[month]["vouchers"].append(voucher)
    _recalculate_month_summary(report[month], report[month]["vouchers"])
    _save_report(report_path, report)


def update_report(voucher: Dict[str, Any], report_dir: str = None):
    """
    幂等追加凭证到 report.json。
    通过 voucher_no 去重，避免重复追加。
    """
    _update_report_unsafe(voucher, report_dir)


def void_report(ref_type: str, ref_id: Any, transaction_date: datetime, report_dir: str = None):
    """
    从 report.json 中移除指定凭证条目（幂等）。
    通过 ref_type + ref_id 匹配。
    """
    if ref_type is None or ref_id is None or transaction_date is None:
        return

    report_path = _get_report_path(report_dir)
    report = _load_report(report_path)
    if not report:
        return

    month = transaction_date.strftime("%Y-%m")
    if month not in report:
        return

    vouchers = report[month].get("vouchers", [])
    # 幂等移除：只保留不匹配的
    original_len = len(vouchers)
    vouchers[:] = [
        v for v in vouchers
        if not (v.get("ref_type") == ref_type and str(v.get("ref_id")) == str(ref_id))
    ]

    if len(vouchers) < original_len:
        # 有实际移除，重新计算 summary
        _recalculate_month_summary(report[month], vouchers)
        _save_report(report_path, report)


def _recalculate_month_summary(month_data: Dict[str, Any], vouchers: List[Dict[str, Any]]):
    """
    根据凭证列表重新计算月度 summary。
    这是一个近似实现：仅计算总计，不重新走完整的 ACCOUNT_CONFIG 逻辑。
    （完整重算依赖 entries 结构，rollback 场景下 vouchers 可能已被删除）
    """
    summary = month_data.get("summary", {})
    total_debit = sum(float(v.get("debit", 0)) for v in vouchers)
    total_credit = sum(float(v.get("credit", 0)) for v in vouchers)
    summary["total_debit"] = total_debit
    summary["total_credit"] = total_credit
    month_data["summary"] = summary
