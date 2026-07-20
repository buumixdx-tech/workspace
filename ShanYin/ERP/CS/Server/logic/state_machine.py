from models import get_session, Logistics, ExpressOrder, VirtualContract, CashFlow, SystemEvent
from logic.constants import VCType, VCStatus, SubjectStatus, CashStatus, ReturnDirection, CashFlowType, LogisticsStatus, OperationalStatus, DeviceStatus, SystemEventType, SystemAggregateType, EPSILON
from logic.events.dispatcher import emit_event
from datetime import date
import logging

logger = logging.getLogger(__name__)

def _emit_event_if_not_exists(session, event_type, aggregate_id, payload):
    """防重检查 + 事件发送"""
    exists = session.query(SystemEvent).filter(
        SystemEvent.event_type == event_type,
        SystemEvent.aggregate_id == aggregate_id
    ).first()
    if not exists:
        emit_event(session, event_type, SystemAggregateType.VIRTUAL_CONTRACT, aggregate_id, payload)

def logistics_state_machine(logistics_id, express_order_id=None, session=None, tx_date=None):
    """物流单状态机：根据快递单状态更新物流单状态，并触发 VC 状态更新"""
    ext_session = session is not None
    if not ext_session:
        session = get_session()
    try:
        logistics = session.query(Logistics).get(logistics_id)
        if not logistics: return

        # 如果物流单已经是 FINISH（手动办理入库后），不再覆盖状态
        old_status = logistics.status
        if logistics.status != LogisticsStatus.FINISH:
            all_express = session.query(ExpressOrder).filter(ExpressOrder.logistics_id == logistics_id).all()
            if all_express:
                if all(e.status == LogisticsStatus.SIGNED for e in all_express):
                    logistics.status = LogisticsStatus.SIGNED
                elif all(e.status in [LogisticsStatus.TRANSIT, LogisticsStatus.SIGNED] for e in all_express):
                    logistics.status = LogisticsStatus.TRANSIT
                else:
                    logistics.status = LogisticsStatus.PENDING

        if old_status != logistics.status:
            emit_event(session, SystemEventType.LOGISTICS_STATUS_CHANGED, SystemAggregateType.LOGISTICS, logistics.id, {
                "from": old_status,
                "to": logistics.status,
                "transaction_date": str(tx_date) if tx_date else None
            })

        # 触发关联 VC 的状态更新
        virtual_contract_state_machine(logistics.virtual_contract_id, 'logistics', logistics_id, session=session, tx_date=tx_date)

        if not ext_session: session.commit()
    finally:
        if not ext_session: session.close()

def virtual_contract_state_machine(vc_id, ref_type, ref_id, session=None, tx_date=None):
    """VC 状态机：综合物流与资金进度，驱动标的状态、资金状态及总体状态"""
    ext_session = session is not None
    if not ext_session:
        session = get_session()
    try:
        vc = session.query(VirtualContract).get(vc_id)
        if not vc: return

        # 1. 处理标的状态 (Subject Status)
        # 业务规则：一个 VC 对应且仅对应一个物流主单
        if ref_type == 'logistics' or ref_id is None:
            logistics = session.query(Logistics).filter(Logistics.virtual_contract_id == vc_id).first()
            if logistics:
                new_subject_status = None
                if logistics.status == LogisticsStatus.FINISH:
                    new_subject_status = SubjectStatus.FINISH
                elif logistics.status == LogisticsStatus.SIGNED:
                    new_subject_status = SubjectStatus.SIGNED
                elif logistics.status == LogisticsStatus.TRANSIT:
                    new_subject_status = SubjectStatus.SHIPPED
                else:
                    new_subject_status = SubjectStatus.EXE

                # 只有状态真正改变时才更新（避免重复日志）
                if new_subject_status and vc.subject_status != new_subject_status:
                    vc.update_subject_status(new_subject_status, transaction_date=tx_date)

                    # --- 核心：退货完结触发押金重算与自动完结核对 ---
                    if vc.type == VCType.RETURN and new_subject_status == SubjectStatus.FINISH and vc.related_vc_id:
                        from logic.deposit import deposit_module
                        deposit_module(vc_id=vc.related_vc_id, session=session)

        # 2. 处理资金状态 (Cash Status)
        if ref_type == 'cash_flow':
            # 优先用传入的 tx_date，否则从 cashflow 查
            if tx_date is None and ref_id:
                cf = session.query(CashFlow).get(ref_id)
                if cf and cf.transaction_date:
                    tx_date = cf.transaction_date.date() if hasattr(cf.transaction_date, 'date') else cf.transaction_date

            all_cash = session.query(CashFlow).filter(CashFlow.virtual_contract_id == vc_id).all()

            # 考虑退货单对原合同押金的影响
            related_return_vcs = session.query(VirtualContract).filter(
                VirtualContract.related_vc_id == vc_id,
                VirtualContract.type == VCType.RETURN
            ).all()
            related_return_cf = []
            for ret_vc in related_return_vcs:
                ret_cfs = session.query(CashFlow).filter(
                    CashFlow.virtual_contract_id == ret_vc.id,
                    CashFlow.type == CashFlowType.RETURN_DEPOSIT
                ).all()
                related_return_cf.extend(ret_cfs)

            paid_goods = sum(cf.amount for cf in all_cash if cf.type in [CashFlowType.PREPAYMENT, CashFlowType.FULFILLMENT, CashFlowType.REFUND, CashFlowType.OFFSET_PAY])
            paid_deposit = sum(cf.amount for cf in all_cash if cf.type == CashFlowType.DEPOSIT)
            paid_return_deposit = sum(cf.amount for cf in all_cash if cf.type == CashFlowType.RETURN_DEPOSIT) + sum(cf.amount for cf in related_return_cf)

            total_due = vc.elements.get('total_amount', 0)
            dep_due = (vc.deposit_info or {}).get('should_receive', 0)

            # 押金关联逻辑
            current_cf = session.query(CashFlow).get(ref_id)
            if current_cf and current_cf.type in [CashFlowType.DEPOSIT, CashFlowType.RETURN_DEPOSIT]:
                from logic.deposit import deposit_module
                deposit_module(cf_id=ref_id, session=session)

            # 判定资金状态
            is_goods_cleared = (paid_goods >= (total_due - EPSILON))
            is_deposit_cleared = (dep_due is not None and dep_due <= EPSILON) or ((paid_deposit - paid_return_deposit) >= (dep_due - EPSILON) if dep_due is not None and dep_due > EPSILON else False)

            # --- 关键：发送原子子事件 (货款结清/押金结清) ---
            if is_goods_cleared:
                _emit_event_if_not_exists(session, SystemEventType.VC_GOODS_CLEARED, vc.id, {
                    "amount": paid_goods,
                    "type": "refund" if vc.type == VCType.RETURN else "income",
                    "transaction_date": str(tx_date) if tx_date else None
                })

            if is_deposit_cleared and dep_due > EPSILON:
                _emit_event_if_not_exists(session, SystemEventType.VC_DEPOSIT_CLEARED, vc.id, {
                    "amount": (paid_deposit - paid_return_deposit),
                    "type": "return" if vc.type == VCType.RETURN else "receive",
                    "transaction_date": str(tx_date) if tx_date else None
                })

            if is_goods_cleared and is_deposit_cleared:
                if vc.cash_status != CashStatus.FINISH:
                    vc.update_cash_status(CashStatus.FINISH, transaction_date=tx_date)
            else:
                # 检查预付
                payment_terms = (vc.elements or {}).get('payment_terms')
                ratio = payment_terms.get('prepayment_ratio', 0) if payment_terms else 0
                if ratio > 0 and vc.cash_status == CashStatus.EXE:
                    if paid_goods >= (total_due * ratio - EPSILON):
                        vc.update_cash_status(CashStatus.PREPAID, transaction_date=tx_date)

        # 3. 总体状态 (VC Status)
        if vc.subject_status == SubjectStatus.FINISH and vc.cash_status == CashStatus.FINISH:
            if vc.status != VCStatus.FINISH:
                vc.update_status(VCStatus.FINISH, transaction_date=tx_date)

        if not ext_session: session.commit()
    finally:
        if not ext_session: session.close()

def check_vc_overall_status(vc, session):
    """外部调用的快捷同步接口"""
    virtual_contract_state_machine(vc.id, None, None, session=session)
