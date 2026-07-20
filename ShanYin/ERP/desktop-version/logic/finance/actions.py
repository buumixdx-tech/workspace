from sqlalchemy.orm import Session
from sqlalchemy import func
from models import CashFlow, VirtualContract
from logic.state_machine import virtual_contract_state_machine
from .engine import finance_module
from logic.offset_manager import check_and_split_excess
from logic.events.dispatcher import emit_event
from .schemas import CreateCashFlowSchema, InternalTransferSchema, ExternalFundSchema, CreateBankAccountSchema, UpdateBankAccountSchema
from logic.base import ActionResult
from logic.constants import SystemEventType, SystemAggregateType, VCStatus, CashFlowType

VALID_CASH_FLOW_TYPES = [
    CashFlowType.PREPAYMENT, CashFlowType.FULFILLMENT,
    CashFlowType.DEPOSIT, CashFlowType.RETURN_DEPOSIT,
    CashFlowType.REFUND, CashFlowType.OFFSET_PAY,
    CashFlowType.OFFSET_IN, CashFlowType.DEPOSIT_OFFSET_IN,
    CashFlowType.PENALTY,
]

VC_STATUS_BLOCKED_FOR_CASHFLOW = [VCStatus.TERMINATED, VCStatus.CANCELLED]

def create_cash_flow_action(session: Session, payload: CreateCashFlowSchema) -> ActionResult:
    """录入资金流水 Action（支持回滚）"""
    import os
    import json as _json
    from models import BankAccount, FinancialJournal
    from logic.constants import CashStatus
    from logic.finance.engine import VOUCHER_DIR
    from logic.transactions import serialize_model, serialize_objs
    try:
        vc = session.query(VirtualContract).get(payload.vc_id)
        if not vc: return ActionResult(success=False, error="未找到关联虚拟合同")
        if vc.status in VC_STATUS_BLOCKED_FOR_CASHFLOW:
            return ActionResult(success=False, error=f"该合同状态为【{vc.status}】，不允许操作")
        if vc.cash_status == CashStatus.FINISH:
            return ActionResult(success=False, error="该合同资金状态已完成，无法再录入流水")
        if payload.type not in VALID_CASH_FLOW_TYPES:
            return ActionResult(success=False, error=f"无效的资金类型: {payload.type}")

        if payload.payer_id and not session.query(BankAccount).get(payload.payer_id):
            return ActionResult(success=False, error=f"付款账号 不存在")
        if payload.payee_id and not session.query(BankAccount).get(payload.payee_id):
            return ActionResult(success=False, error=f"收款账号 不存在")

        # ============ snapshot_before：查询可能被修改的现有记录 ============
        snapshot_before = {"records": []}
        # VirtualContract 旧值
        snapshot_before["records"].append({"class": "VirtualContract", "id": vc.id, "data": serialize_model(vc)})

        # EquipmentInventory 押金重算旧值（DEPOSIT / RETURN_DEPOSIT 时）
        if payload.type in [CashFlowType.DEPOSIT, CashFlowType.RETURN_DEPOSIT]:
            from models import EquipmentInventory
            eq_list = session.query(EquipmentInventory).filter(EquipmentInventory.virtual_contract_id == payload.vc_id).all()
            for eq in eq_list:
                snapshot_before["records"].append({"class": "EquipmentInventory", "id": eq.id, "data": serialize_model(eq)})

        session.begin_nested()

        new_cf = CashFlow(
            virtual_contract_id=payload.vc_id, type=payload.type,
            amount=payload.amount, payer_account_id=payload.payer_id,
            payee_account_id=payload.payee_id, description=payload.description,
            transaction_date=payload.transaction_date
        )
        session.add(new_cf)
        session.flush()

        check_and_split_excess(session, new_cf)
        virtual_contract_state_machine(payload.vc_id, 'cash_flow', new_cf.id, session=session)
        finance_module(cash_flow_id=new_cf.id, session=session)

        # 记录当前最大 event id（用于捕获 emit_event 创建的 SystemEvent）
        from models import SystemEvent
        max_event_id_before = session.query(func.max(SystemEvent.id)).scalar() or 0

        emit_event(session, SystemEventType.CASH_FLOW_RECORDED, SystemAggregateType.CASH_FLOW, new_cf.id, {
            "vc_id": payload.vc_id, "type": payload.type, "amount": payload.amount
        })
        session.flush()

        # ============ snapshot_after：重新查询所有被修改的记录 ============
        # 刷新 VirtualContract 状态
        vc_ref = session.query(VirtualContract).get(vc.id)
        cf_ref = session.query(CashFlow).get(new_cf.id)

        snapshot_after_records = [
            {"class": "CashFlow", "id": cf_ref.id, "data": serialize_model(cf_ref)},
            {"class": "VirtualContract", "id": vc_ref.id, "data": serialize_model(vc_ref)},
        ]

        # EquipmentInventory 押金更新后
        if payload.type in [CashFlowType.DEPOSIT, CashFlowType.RETURN_DEPOSIT]:
            eq_list_after = session.query(EquipmentInventory).filter(EquipmentInventory.virtual_contract_id == vc.id).all()
            for eq in eq_list_after:
                snapshot_after_records.append({"class": "EquipmentInventory", "id": eq.id, "data": serialize_model(eq)})

        # FinancialJournal + CashFlowLedger（finance_module 创建）
        fj_list = session.query(FinancialJournal).filter(
            FinancialJournal.ref_type == "CashFlow",
            FinancialJournal.ref_id == new_cf.id
        ).all()
        for fj in fj_list:
            snapshot_after_records.append({"class": "FinancialJournal", "id": fj.id, "data": serialize_model(fj)})
            if fj.cash_flow_record:
                snapshot_after_records.append({"class": "CashFlowLedger", "id": fj.cash_flow_record.id, "data": serialize_model(fj.cash_flow_record)})

        # SystemEvent
        new_events = session.query(SystemEvent).filter(SystemEvent.id > max_event_id_before).all()
        for ev in new_events:
            snapshot_after_records.append({"class": "SystemEvent", "id": ev.id, "data": serialize_model(ev)})

        # JSON 文件
        snapshot_files = []
        voucher_path = os.path.join(VOUCHER_DIR, f"CashFlow_{new_cf.id}.json")
        if os.path.exists(voucher_path):
            with open(voucher_path, "r", encoding="utf-8") as f:
                snapshot_files.append({"path": voucher_path, "content": _json.load(f)})

        snapshot_after = {"records": snapshot_after_records, "files": snapshot_files}

        from logic.transactions import create_operation_record
        involved_ids = [vc.id, cf_ref.id]
        if payload.type in [CashFlowType.DEPOSIT, CashFlowType.RETURN_DEPOSIT]:
            involved_ids += [eq.id for eq in eq_list_after]

        tx_id = create_operation_record(
            session,
            action_name="create_cash_flow_action",
            ref_type="CashFlow",
            ref_id=new_cf.id,
            ref_vc_id=vc.id,
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            involved_ids=involved_ids,
        )

        session.commit()
        return ActionResult(success=True, data={"cf_id": new_cf.id}, message="财务流水已记录")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def internal_transfer_action(session: Session, payload: InternalTransferSchema) -> ActionResult:
    """内部划拔 Action（支持回滚）"""
    import uuid
    import os
    import json as _json
    from models import BankAccount, SystemEvent
    from logic.constants import FinanceConstants
    from logic.finance.engine import record_entries, VOUCHER_DIR
    from logic.transactions import serialize_model, serialize_objs
    try:
        if not session.query(BankAccount).get(payload.from_acc_id):
            return ActionResult(success=False, error="源账号不存在")
        if not session.query(BankAccount).get(payload.to_acc_id):
            return ActionResult(success=False, error="目标账号不存在")

        v_no = f"{FinanceConstants.VOUCHER_PREFIX_TRANSFER}{uuid.uuid4().hex[:6].upper()}"
        entries = [
            {"level1": FinanceConstants.CASH_ACCOUNT, "cp_type": "BankAccount", "cp_id": payload.to_acc_id, "debit": payload.amount, "summary": f"内转: {payload.description or '资金调拨'}"},
            {"level1": FinanceConstants.CASH_ACCOUNT, "cp_type": "BankAccount", "cp_id": payload.from_acc_id, "credit": payload.amount, "summary": f"内转: {payload.description or '资金调拨'}"}
        ]

        # record_entries 内部 flush，所有新记录已在 session.new 中且 ID 已分配
        record_entries(session, v_no, None, "InternalTransfer", 0, entries, payload.transaction_date)
        new_records_ids = [o.id for o in session.new]
        actual_ref_id = new_records_ids[0] if new_records_ids else 0

        # emit_event 之前：序列化 FinancialJournal + CashFlowLedger，并读取已保存的 JSON 文件
        snapshot_records = serialize_objs(list(session.new))
        voucher_path = os.path.join(VOUCHER_DIR, f"InternalTransfer_{actual_ref_id}.json")
        voucher_content = None
        if os.path.exists(voucher_path):
            with open(voucher_path, "r", encoding="utf-8") as f:
                voucher_content = _json.load(f)

        system_event = emit_event(session, SystemEventType.INTERNAL_TRANSFER, SystemAggregateType.FINANCIAL_JOURNAL, 0, {
            "from_acc_id": payload.from_acc_id, "to_acc_id": payload.to_acc_id, "amount": payload.amount, "voucher_no": v_no
        })
        session.flush()

        # SystemEvent 后创建，加入 snapshot_after
        snapshot_records.append({"class": "SystemEvent", "id": system_event.id, "data": serialize_model(system_event)})
        snapshot_after = {"records": snapshot_records}
        if voucher_content:
            snapshot_after["files"] = [{"path": voucher_path, "content": voucher_content}]

        from logic.transactions import create_operation_record
        tx_id = create_operation_record(
            session,
            action_name="internal_transfer_action",
            ref_type="FinancialJournal",
            ref_id=new_records_ids[0] if new_records_ids else 0,
            snapshot_before={},
            involved_ids=new_records_ids,
        )

        session.commit()
        return ActionResult(success=True, message=f"已生成划拨凭证: {v_no}")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def external_fund_action(session: Session, payload: ExternalFundSchema) -> ActionResult:
    """外部出入金 Action（支持回滚）"""
    import uuid
    import os
    import json as _json
    from models import BankAccount
    from logic.constants import FinanceConstants
    from logic.finance.engine import record_entries, VOUCHER_DIR
    from logic.transactions import serialize_model, serialize_objs
    try:
        prefix = FinanceConstants.VOUCHER_PREFIX_EXT_IN if payload.is_inbound else FinanceConstants.VOUCHER_PREFIX_EXT_OUT
        v_no = f"{prefix}{uuid.uuid4().hex[:6].upper()}"
        lv1 = payload.fund_type.split(" (")[0]
        if payload.is_inbound:
            entries = [
                {"level1": FinanceConstants.CASH_ACCOUNT, "cp_type": "BankAccount", "cp_id": payload.account_id, "debit": payload.amount, "summary": f"外部入金({lv1}): {payload.external_entity}"},
                {"level1": lv1, "credit": payload.amount, "summary": f"资金注入: {payload.description or payload.external_entity}"}
            ]
        else:
            entries = [
                {"level1": lv1, "debit": payload.amount, "summary": f"非运营支出({lv1}): {payload.external_entity}"},
                {"level1": FinanceConstants.CASH_ACCOUNT, "cp_type": "BankAccount", "cp_id": payload.account_id, "credit": payload.amount, "summary": f"外部出金: {payload.description or payload.external_entity}"}
            ]
        # record_entries 内部 flush，所有新记录已在 session.new 中且 ID 已分配
        record_entries(session, v_no, None, "ExternalTransfer", 0, entries, payload.transaction_date)
        new_records_ids = [o.id for o in session.new]
        actual_ref_id = new_records_ids[0] if new_records_ids else 0

        # emit_event 之前：序列化记录，并读取已保存的 JSON 文件
        snapshot_records = serialize_objs(list(session.new))
        voucher_path = os.path.join(VOUCHER_DIR, f"ExternalTransfer_{actual_ref_id}.json")
        voucher_content = None
        if os.path.exists(voucher_path):
            with open(voucher_path, "r", encoding="utf-8") as f:
                voucher_content = _json.load(f)

        system_event = emit_event(session, SystemEventType.EXTERNAL_FUND_FLOW, SystemAggregateType.FINANCIAL_JOURNAL, 0, {
            "account_id": payload.account_id, "amount": payload.amount, "is_inbound": payload.is_inbound, "entity": payload.external_entity, "voucher_no": v_no
        })
        session.flush()

        snapshot_records.append({"class": "SystemEvent", "id": system_event.id, "data": serialize_model(system_event)})
        snapshot_after = {"records": snapshot_records}
        if voucher_content:
            snapshot_after["files"] = [{"path": voucher_path, "content": voucher_content}]

        from logic.transactions import create_operation_record
        tx_id = create_operation_record(
            session,
            action_name="external_fund_action",
            ref_type="FinancialJournal",
            ref_id=new_records_ids[0] if new_records_ids else 0,
            snapshot_before={},
            involved_ids=new_records_ids,
        )

        session.commit()
        return ActionResult(success=True, message=f"已生成收支凭证: {v_no}")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def create_bank_account_action(session: Session, payload: CreateBankAccountSchema) -> ActionResult:
    from models import BankAccount
    try:
        if payload.is_default:
            _clear_default_bank_account(session, payload.owner_type, payload.owner_id)
        new_obj = BankAccount(
            owner_type=payload.owner_type, owner_id=payload.owner_id,
            account_info=payload.account_info, is_default=payload.is_default
        )
        session.add(new_obj)
        session.commit()
        return ActionResult(success=True, message="银行账户创建成功")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def update_bank_accounts_action(session: Session, payloads: list) -> ActionResult:
    from models import BankAccount
    try:
        updated_count = 0
        for p in payloads:
            obj = session.query(BankAccount).get(p.id)
            if obj:
                if p.is_default and not obj.is_default:
                   _clear_default_bank_account(session, p.owner_type, p.owner_id)
                obj.owner_type = p.owner_type
                obj.owner_id = p.owner_id
                obj.account_info = p.account_info
                obj.is_default = p.is_default
                updated_count += 1
        session.commit()
        return ActionResult(success=True, message=f"成功更新 {updated_count} 个账户")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def _clear_default_bank_account(session: Session, owner_type: str, owner_id: int):
    from models import BankAccount
    q = session.query(BankAccount).filter(BankAccount.owner_type == owner_type)
    if owner_id:
        q = q.filter(BankAccount.owner_id == owner_id)
    else:
        q = q.filter(BankAccount.owner_id.is_(None))
    for acc in q.all():
        acc.is_default = False

def delete_bank_accounts_action(session: Session, payloads: list) -> ActionResult:
    from models import BankAccount
    try:
        deleted_count = 0
        for p in payloads:
            obj = session.query(BankAccount).get(p.id)
            if obj:
                session.delete(obj)
                deleted_count += 1
        session.commit()
        return ActionResult(success=True, message=f"成功删除 {deleted_count} 个账户")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))
