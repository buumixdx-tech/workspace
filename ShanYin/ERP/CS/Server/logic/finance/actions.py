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
from logic.audit_engine import audit_context, set_audit_event_id

VALID_CASH_FLOW_TYPES = [
    CashFlowType.PREPAYMENT, CashFlowType.FULFILLMENT,
    CashFlowType.DEPOSIT, CashFlowType.RETURN_DEPOSIT,
    CashFlowType.REFUND, CashFlowType.OFFSET_PAY,
    CashFlowType.OFFSET_IN, CashFlowType.DEPOSIT_OFFSET_IN,
    CashFlowType.PENALTY,
]

VC_STATUS_BLOCKED_FOR_CASHFLOW = [VCStatus.TERMINATED, VCStatus.CANCELLED]

def create_cash_flow_action(session: Session, payload: CreateCashFlowSchema) -> ActionResult:
    """录入资金流水 Action"""
    import os
    import json as _json
    from models import BankAccount, FinancialJournal
    from logic.constants import CashStatus
    from logic.finance.engine import VOUCHER_DIR
    try:
        with audit_context("create_cash_flow_action"):
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

            session.begin_nested()

            new_cf = CashFlow(
                virtual_contract_id=payload.vc_id, type=payload.type,
                amount=payload.amount, payer_account_id=payload.payer_id,
                payee_account_id=payload.payee_id, description=payload.description,
                transaction_date=payload.transaction_date
            )
            session.add(new_cf)

            evt = emit_event(session, SystemEventType.CASH_FLOW_RECORDED, SystemAggregateType.CASH_FLOW, 0, {"placeholder": True})
            set_audit_event_id(evt.id)

            session.flush()

            check_and_split_excess(session, new_cf)
            tx_date = payload.transaction_date.date() if payload.transaction_date else None
            virtual_contract_state_machine(payload.vc_id, 'cash_flow', new_cf.id, session=session, tx_date=tx_date)
            finance_module(cash_flow_id=new_cf.id, session=session)

            evt.aggregate_id = new_cf.id
            evt.payload = {"vc_id": payload.vc_id, "type": payload.type, "amount": payload.amount}

            session.commit()
            return ActionResult(success=True, data={"cf_id": new_cf.id}, message="财务流水已记录")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def internal_transfer_action(session: Session, payload: InternalTransferSchema) -> ActionResult:
    """内部划拔 Action"""
    import uuid
    from models import BankAccount, SystemEvent
    from logic.constants import FinanceConstants
    from logic.finance.engine import record_entries
    try:
        with audit_context("internal_transfer_action"):
            if not session.query(BankAccount).get(payload.from_acc_id):
                return ActionResult(success=False, error="源账号不存在")
            if not session.query(BankAccount).get(payload.to_acc_id):
                return ActionResult(success=False, error="目标账号不存在")

            v_no = f"{FinanceConstants.VOUCHER_PREFIX_TRANSFER}{uuid.uuid4().hex[:6].upper()}"
            entries = [
                {"level1": FinanceConstants.CASH_ACCOUNT, "cp_type": "BankAccount", "cp_id": payload.to_acc_id, "debit": payload.amount, "summary": f"内转: {payload.description or '资金调拨'}"},
                {"level1": FinanceConstants.CASH_ACCOUNT, "cp_type": "BankAccount", "cp_id": payload.from_acc_id, "credit": payload.amount, "summary": f"内转: {payload.description or '资金调拨'}"}
            ]

            evt = emit_event(session, SystemEventType.INTERNAL_TRANSFER, SystemAggregateType.FINANCIAL_JOURNAL, 0, {"placeholder": True})
            set_audit_event_id(evt.id)

            record_entries(session, v_no, None, "InternalTransfer", 0, entries, payload.transaction_date)

            evt.payload = {"from_acc_id": payload.from_acc_id, "to_acc_id": payload.to_acc_id, "amount": payload.amount, "voucher_no": v_no}

            session.commit()
            return ActionResult(success=True, message=f"已生成划拨凭证: {v_no}")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def external_fund_action(session: Session, payload: ExternalFundSchema) -> ActionResult:
    """外部出入金 Action"""
    import uuid
    from models import BankAccount
    from logic.constants import FinanceConstants
    from logic.finance.engine import record_entries
    try:
        with audit_context("external_fund_action"):
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
            evt = emit_event(session, SystemEventType.EXTERNAL_FUND_FLOW, SystemAggregateType.FINANCIAL_JOURNAL, 0, {"placeholder": True})
            set_audit_event_id(evt.id)

            record_entries(session, v_no, None, "ExternalTransfer", 0, entries, payload.transaction_date)

            evt.payload = {"account_id": payload.account_id, "amount": payload.amount, "is_inbound": payload.is_inbound, "entity": payload.external_entity, "voucher_no": v_no}

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
