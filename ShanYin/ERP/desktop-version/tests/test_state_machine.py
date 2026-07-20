"""
状态机单元测试
测试物流、虚拟合同的状态转换逻辑
"""

import pytest
from datetime import datetime
from logic import state_machine
from logic.constants import (
    LogisticsStatus, VCType, VCStatus, SubjectStatus, CashStatus,
    CashFlowType, OperationalStatus
)
from models import VirtualContract, Logistics, ExpressOrder, CashFlow, Business


class TestLogisticsStateMachine:
    """物流单状态机测试"""

    def test_logistics_status_update_from_express_orders(self, db_session, sample_virtual_contract):
        """✅ 物流单状态根据快递单更新"""
        # Given: 创建物流单和快递单
        logistics = Logistics(
            virtual_contract_id=sample_virtual_contract.id,
            status=LogisticsStatus.PENDING
        )
        db_session.add(logistics)
        db_session.flush()

        # 创建快递单（全部签收）
        express1 = ExpressOrder(
            logistics_id=logistics.id,
            status=LogisticsStatus.SIGNED
        )
        express2 = ExpressOrder(
            logistics_id=logistics.id,
            status=LogisticsStatus.SIGNED
        )
        db_session.add_all([express1, express2])
        db_session.flush()

        # When: 触发状态机
        state_machine.logistics_state_machine(logistics.id, session=db_session)

        # Then: 物流单状态应更新为 SIGNED
        db_session.refresh(logistics)
        assert logistics.status == LogisticsStatus.SIGNED

    def test_logistics_status_transit(self, db_session, sample_virtual_contract):
        """✅ 部分快递单在途"""
        # Given
        logistics = Logistics(
            virtual_contract_id=sample_virtual_contract.id,
            status=LogisticsStatus.PENDING
        )
        db_session.add(logistics)
        db_session.flush()

        express1 = ExpressOrder(logistics_id=logistics.id, status=LogisticsStatus.SIGNED)
        express2 = ExpressOrder(logistics_id=logistics.id, status=LogisticsStatus.TRANSIT)
        db_session.add_all([express1, express2])
        db_session.flush()

        # When
        state_machine.logistics_state_machine(logistics.id, session=db_session)

        # Then
        db_session.refresh(logistics)
        assert logistics.status == LogisticsStatus.TRANSIT

    def test_logistics_finish_not_overwritten(self, db_session, sample_virtual_contract):
        """✅ 已完成的物流单状态不会被覆盖"""
        # Given: 物流单状态为 FINISH
        logistics = Logistics(
            virtual_contract_id=sample_virtual_contract.id,
            status=LogisticsStatus.FINISH
        )
        db_session.add(logistics)
        db_session.flush()

        express = ExpressOrder(logistics_id=logistics.id, status=LogisticsStatus.PENDING)
        db_session.add(express)
        db_session.flush()

        # When
        state_machine.logistics_state_machine(logistics.id, session=db_session)

        # Then: 状态应保持 FINISH
        db_session.refresh(logistics)
        assert logistics.status == LogisticsStatus.FINISH


class TestVirtualContractStateMachine:
    """虚拟合同状态机测试"""

    def test_subject_status_updates_from_logistics(self, db_session, sample_virtual_contract):
        """✅ 标的状态跟随物流状态更新"""
        # Given: 创建物流单并完成
        logistics = Logistics(
            virtual_contract_id=sample_virtual_contract.id,
            status=LogisticsStatus.FINISH
        )
        db_session.add(logistics)
        db_session.flush()

        # When: 触发 VC 状态机
        state_machine.virtual_contract_state_machine(
            sample_virtual_contract.id, 'logistics', logistics.id, session=db_session
        )

        # Then: 标的状态应为 FINISH
        db_session.refresh(sample_virtual_contract)
        assert sample_virtual_contract.subject_status == SubjectStatus.FINISH

    def test_cash_status_prepaid(self, db_session, sample_virtual_contract):
        """✅ 预付款到位后状态更新为已预付"""
        # Given: VC 有预付比例条款
        sample_virtual_contract.elements = {
            "total_amount": 10000,
            "payment_terms": {"prepayment_ratio": 0.3}
        }
        db_session.flush()

        # 创建预付款流水（30% = 3000）
        cash_flow = CashFlow(
            virtual_contract_id=sample_virtual_contract.id,
            type=CashFlowType.PREPAYMENT,
            amount=3000,
            transaction_date=datetime.now()
        )
        db_session.add(cash_flow)
        db_session.flush()

        # When: 触发资金状态处理
        state_machine.virtual_contract_state_machine(
            sample_virtual_contract.id, 'cash_flow', cash_flow.id, session=db_session
        )

        # Then: 现金状态应为 PREPAID
        db_session.refresh(sample_virtual_contract)
        assert sample_virtual_contract.cash_status == CashStatus.PREPAID

    def test_cash_status_finish(self, db_session, sample_virtual_contract):
        """✅ 货款和押金都结清后状态为完成"""
        # Given
        sample_virtual_contract.elements = {"total_amount": 10000}
        sample_virtual_contract.deposit_info = {"should_receive": 1000}
        db_session.flush()

        # 创建货款流水
        cf1 = CashFlow(
            virtual_contract_id=sample_virtual_contract.id,
            type=CashFlowType.FULFILLMENT,
            amount=10000,
            transaction_date=datetime.now()
        )
        # 创建押金流水
        cf2 = CashFlow(
            virtual_contract_id=sample_virtual_contract.id,
            type=CashFlowType.DEPOSIT,
            amount=1000,
            transaction_date=datetime.now()
        )
        db_session.add_all([cf1, cf2])
        db_session.flush()

        # When
        state_machine.virtual_contract_state_machine(
            sample_virtual_contract.id, 'cash_flow', cf2.id, session=db_session
        )

        # Then: 两个状态都应为 FINISH
        db_session.refresh(sample_virtual_contract)
        assert sample_virtual_contract.cash_status == CashStatus.FINISH

    def test_overall_status_finish(self, db_session, sample_virtual_contract):
        """✅ 标的和资金都完成后，总体状态为完成"""
        # Given: 标的和资金都完成
        sample_virtual_contract.subject_status = SubjectStatus.FINISH
        sample_virtual_contract.cash_status = CashStatus.FINISH
        db_session.flush()

        # When
        state_machine.virtual_contract_state_machine(
            sample_virtual_contract.id, None, None, session=db_session
        )

        # Then: 总体状态应为 FINISH
        db_session.refresh(sample_virtual_contract)
        assert sample_virtual_contract.status == VCStatus.FINISH


class TestStatusTransitionValidation:
    """状态转换验证测试"""

    def test_invalid_status_not_applied(self, db_session, sample_virtual_contract):
        """✅ 无效状态不会被应用"""
        # Given
        old_status = sample_virtual_contract.subject_status

        # When: 传入无效的 ref_type
        state_machine.virtual_contract_state_machine(
            sample_virtual_contract.id, 'invalid_type', None, session=db_session
        )

        # Then: 状态不应改变
        db_session.refresh(sample_virtual_contract)
        assert sample_virtual_contract.subject_status == old_status


class TestStateMachineEventEmission:
    """状态机事件派发测试 — 验证 emit_event 被正确调用"""

    def test_vc_goods_cleared_event_emitted(self, db_session, sample_virtual_contract):
        """✅ 货款结清时发出 VC_GOODS_CLEARED 事件"""
        from logic.constants import SystemEventType, SystemAggregateType
        from models import SystemEvent

        # Given: VC 货款全部结清
        sample_virtual_contract.elements = {"total_amount": 5000}
        sample_virtual_contract.deposit_info = {"should_receive": 0}
        db_session.flush()

        # 创建全额货款流水
        cf = CashFlow(
            virtual_contract_id=sample_virtual_contract.id,
            type=CashFlowType.FULFILLMENT,
            amount=5000,
            transaction_date=datetime.now()
        )
        db_session.add(cf)
        db_session.flush()

        # When
        state_machine.virtual_contract_state_machine(
            sample_virtual_contract.id, 'cash_flow', cf.id, session=db_session
        )

        # Then: VC_GOODS_CLEARED 事件应被写入 SystemEvent 表
        db_session.flush()
        events = db_session.query(SystemEvent).filter(
            SystemEvent.aggregate_id == sample_virtual_contract.id,
            SystemEvent.event_type == SystemEventType.VC_GOODS_CLEARED
        ).all()
        assert len(events) == 1
        assert events[0].payload.get("type") == "income"

    def test_vc_deposit_cleared_event_emitted(self, db_session, sample_virtual_contract):
        """✅ 押金结清时发出 VC_DEPOSIT_CLEARED 事件"""
        from logic.constants import SystemEventType
        from models import SystemEvent

        # Given: VC 应退押金为 1000（> EPSILON），押金流水 1000 使其结清
        sample_virtual_contract.elements = {"total_amount": 0}
        sample_virtual_contract.deposit_info = {"should_receive": 1000}
        db_session.flush()

        # 创建押金流水（1000 = 应退金额，结清）
        cf = CashFlow(
            virtual_contract_id=sample_virtual_contract.id,
            type=CashFlowType.DEPOSIT,
            amount=1000,
            transaction_date=datetime.now()
        )
        db_session.add(cf)
        db_session.flush()

        # When
        state_machine.virtual_contract_state_machine(
            sample_virtual_contract.id, 'cash_flow', cf.id, session=db_session
        )

        # Then: VC_DEPOSIT_CLEARED 事件应被写入
        db_session.flush()
        events = db_session.query(SystemEvent).filter(
            SystemEvent.aggregate_id == sample_virtual_contract.id,
            SystemEvent.event_type == SystemEventType.VC_DEPOSIT_CLEARED
        ).all()
        assert len(events) == 1

    def test_vc_overall_finish_emits_status_transition_event(
        self, db_session, sample_virtual_contract
    ):
        """✅ VC 总体状态变为 FINISH 时发出 VC_STATUS_TRANSITION 事件"""
        from logic.constants import SystemEventType
        from models import SystemEvent

        # Given: 标的和资金状态都完成
        sample_virtual_contract.subject_status = SubjectStatus.FINISH
        sample_virtual_contract.cash_status = CashStatus.FINISH
        db_session.flush()

        # When
        state_machine.virtual_contract_state_machine(
            sample_virtual_contract.id, None, None, session=db_session
        )

        # Then: VC_STATUS_TRANSITION 事件应被写入
        db_session.flush()
        events = db_session.query(SystemEvent).filter(
            SystemEvent.aggregate_id == sample_virtual_contract.id,
            SystemEvent.event_type == SystemEventType.VC_STATUS_TRANSITION
        ).all()
        assert len(events) == 1
        assert events[0].payload.get("to") == VCStatus.FINISH