"""
虚拟合同模型单元测试
"""

import pytest
from models import VirtualContract, Logistics, CashFlow


class TestVirtualContractModel:
    """虚拟合同模型测试"""

    def test_create_virtual_contract(self, db_session, sample_business):
        """✅ 创建虚拟合同"""
        # Given & When
        vc = VirtualContract(
            business_id=sample_business.id,
            type="设备采购",
            elements={"total_amount": 10000},
            deposit_info={"should_receive": 1000},
            status="执行",
            subject_status="执行",
            cash_status="执行"
        )
        db_session.add(vc)
        db_session.flush()

        # Then
        assert vc.id is not None
        assert vc.business_id == sample_business.id
        assert vc.status == "执行"

    def test_update_status(self, db_session, sample_virtual_contract):
        """✅ 更新总体状态"""
        # Given
        vc = sample_virtual_contract

        # When
        vc.update_status("完成")

        # Then
        db_session.flush()
        assert vc.status == "完成"

    def test_update_subject_status(self, db_session, sample_virtual_contract):
        """✅ 更新标的状态"""
        # Given
        vc = sample_virtual_contract

        # When
        vc.update_subject_status("已完成")

        # Then
        db_session.flush()
        assert vc.subject_status == "已完成"

    def test_update_cash_status(self, db_session, sample_virtual_contract):
        """✅ 更新资金状态"""
        # Given
        vc = sample_virtual_contract

        # When
        vc.update_cash_status("已结清")

        # Then
        db_session.flush()
        assert vc.cash_status == "已结清"

    def test_status_no_change_if_same(self, db_session, sample_virtual_contract):
        """✅ 相同状态不更新"""
        # Given
        original_status = sample_virtual_contract.status
        original_timestamp = sample_virtual_contract.status_timestamp

        # When
        sample_virtual_contract.update_status(original_status)

        # Then: 时间戳不应改变
        assert sample_virtual_contract.status_timestamp == original_timestamp


class TestVirtualContractRelationships:
    """虚拟合同关联关系测试"""

    def test_add_logistics_to_vc(self, db_session, sample_virtual_contract):
        """✅ 为 VC 添加物流"""
        # Given
        vc = sample_virtual_contract

        # When
        logistics = Logistics(
            virtual_contract_id=vc.id,
            status="待发货"
        )
        db_session.add(logistics)
        db_session.flush()

        # Then
        from models import VirtualContract
        fetched_vc = db_session.query(VirtualContract).get(vc.id)
        assert len(fetched_vc.logistics) == 1
        assert fetched_vc.logistics[0].status == "待发货"

    def test_add_cashflow_to_vc(self, db_session, sample_virtual_contract):
        """✅ 为 VC 添加资金流"""
        # Given
        vc = sample_virtual_contract

        # When
        cashflow = CashFlow(
            virtual_contract_id=vc.id,
            type="预付款",
            amount=5000
        )
        db_session.add(cashflow)
        db_session.flush()

        # Then
        from models import VirtualContract
        fetched_vc = db_session.query(VirtualContract).get(vc.id)
        assert len(fetched_vc.cash_flows) == 1
        assert fetched_vc.cash_flows[0].amount == 5000


class TestVirtualContractStatusLogs:
    """虚拟合同状态日志测试"""

    def test_status_change_creates_log(self, db_session, sample_virtual_contract):
        """✅ 状态变更创建日志"""
        # Given
        vc = sample_virtual_contract

        # When
        vc.update_status("完成")

        # Then: 检查日志是否创建
        from models import VirtualContractStatusLog
        logs = db_session.query(VirtualContractStatusLog).filter(
            VirtualContractStatusLog.vc_id == vc.id
        ).all()

        assert len(logs) >= 1
        # 最新日志应该是"完成"状态
        latest_log = logs[-1]
        assert latest_log.status_name == "完成"