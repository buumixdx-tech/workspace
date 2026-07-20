"""
财务 Actions 单元测试
"""

import pytest
from datetime import datetime
from logic.finance import (
    create_cash_flow_action,
    internal_transfer_action,
    external_fund_action,
    CreateCashFlowSchema,
    InternalTransferSchema,
    ExternalFundSchema,
)


class TestCashFlowActions:
    """资金流水测试"""

    def test_create_cash_flow_success(self, db_session, sample_virtual_contract):
        """✅ 正常创建资金流水"""
        # Given - 使用有效的资金类型常量
        from logic.constants import CashFlowType
        payload = CreateCashFlowSchema(
            vc_id=sample_virtual_contract.id,
            type=CashFlowType.PREPAYMENT,
            amount=10000,
            transaction_date=datetime.now()
        )

        # When
        result = create_cash_flow_action(db_session, payload)

        # Then
        assert result.success is True

    def test_create_cash_flow_vc_not_found(self, db_session):
        """❌ 虚拟合同不存在"""
        from logic.constants import CashFlowType
        payload = CreateCashFlowSchema(
            vc_id=99999,
            type=CashFlowType.PREPAYMENT,
            amount=1000,
            transaction_date=datetime.now()
        )

        result = create_cash_flow_action(db_session, payload)

        assert result.success is False


class TestInternalTransferAction:
    """内部划拔测试"""

    def test_internal_transfer_same_account_fails(self, db_session):
        """✅ 转账到同一账户会在 Schema 验证时失败"""
        # Given: 使用相同的账户 ID
        # When & Then: Pydantic 验证器会在构造时拦截，抛出 ValidationError
        with pytest.raises(Exception) as exc_info:
            InternalTransferSchema(
                from_acc_id=1,
                to_acc_id=1,  # 相同账户
                amount=1000,
                transaction_date=datetime.now()
            )
        
        # 验证错误信息
        assert "不能相同" in str(exc_info.value)


class TestExternalFundAction:
    """外部出入金测试"""

    def test_external_fund_schema_validation(self, db_session):
        """✅ 验证外部资金 Schema"""
        # Given: 直接使用 Schema 验证
        payload = ExternalFundSchema(
            account_id=1,
            fund_type="客户回款",
            amount=50000,
            transaction_date=datetime.now(),
            external_entity="测试客户",
            is_inbound=True
        )

        # When & Then: Schema 验证通过
        assert payload.amount == 50000
        assert payload.is_inbound is True