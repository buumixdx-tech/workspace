"""
业务 Actions 单元测试
根据实际业务逻辑调整的测试用例
"""

import pytest
from logic.business import (
    create_business_action,
    advance_business_stage_action,
    update_business_status_action,
    delete_business_action,
    CreateBusinessSchema,
    AdvanceBusinessStageSchema,
    UpdateBusinessStatusSchema,
)
from logic.constants import BusinessStatus
from api.middleware.error_handler import NotFoundError


class TestCreateBusinessAction:
    """创建业务测试"""

    def test_create_business_success(self, db_session, sample_customer):
        """✅ 正常创建业务"""
        # Given
        payload = CreateBusinessSchema(customer_id=sample_customer.id)

        # When
        result = create_business_action(db_session, payload)

        # Then
        assert result.success is True
        assert result.data is not None
        assert "business_id" in result.data
        assert result.data["business_id"] > 0


class TestAdvanceBusinessStageAction:
    """推进业务阶段测试"""

    def test_advance_from_draft_to_evaluation(self, db_session, sample_customer):
        """✅ 从草稿推进到业务评估阶段"""
        # 先创建业务（状态为 DRAFT）
        payload = CreateBusinessSchema(customer_id=sample_customer.id)
        result = create_business_action(db_session, payload)
        business_id = result.data["business_id"]

        # Given: 从 DRAFT 推进到 EVALUATION
        payload = AdvanceBusinessStageSchema(
            business_id=business_id,
            next_status=BusinessStatus.EVALUATION,
            comment="客户有意向"
        )

        # When
        result = advance_business_stage_action(db_session, payload)

        # Then
        assert result.success is True

    def test_advance_from_evaluation_to_feedback(self, db_session, sample_customer):
        """✅ 从业务评估推进到客户反馈"""
        # 先创建业务并推进到 EVALUATION
        payload = CreateBusinessSchema(customer_id=sample_customer.id)
        result = create_business_action(db_session, payload)
        business_id = result.data["business_id"]

        # 推进到 EVALUATION
        payload = AdvanceBusinessStageSchema(
            business_id=business_id,
            next_status=BusinessStatus.EVALUATION,
            comment="评估完成"
        )
        advance_business_stage_action(db_session, payload)

        # Given: 从 EVALUATION 推进到 FEEDBACK
        payload = AdvanceBusinessStageSchema(
            business_id=business_id,
            next_status=BusinessStatus.FEEDBACK,
            comment="客户反馈积极"
        )

        # When
        result = advance_business_stage_action(db_session, payload)

        # Then
        assert result.success is True

    def test_advance_to_active_with_payment_terms(self, db_session, sample_customer):
        """✅ 推进到开展阶段（有结算条款）"""
        # 先创建业务并推进到合适阶段
        payload = CreateBusinessSchema(customer_id=sample_customer.id)
        result = create_business_action(db_session, payload)
        business_id = result.data["business_id"]

        # 推进到 FEEDBACK -> LANDING -> ACTIVE
        for status in [BusinessStatus.EVALUATION, BusinessStatus.FEEDBACK, BusinessStatus.LANDING]:
            payload = AdvanceBusinessStageSchema(
                business_id=business_id,
                next_status=status,
                comment="测试"
            )
            advance_business_stage_action(db_session, payload)

        # Given: 从 FEEDBACK 推进到 ACTIVE（有结算条款）
        payload = AdvanceBusinessStageSchema(
            business_id=business_id,
            next_status=BusinessStatus.ACTIVE,
            comment="正式开展",
            payment_terms={
                "prepayment_ratio": 0.3,
                "balance_period": 30
            }
        )

        # When
        result = advance_business_stage_action(db_session, payload)

        # Then
        assert result.success is True


class TestUpdateBusinessStatusAction:
    """更新业务状态测试"""

    def test_update_business_status_success(self, db_session, sample_business):
        """✅ 正常更新业务状态"""
        # Given
        payload = UpdateBusinessStatusSchema(
            business_id=sample_business.id,
            status="业务评估",
            details={"备注": "更新测试"}
        )

        # When
        result = update_business_status_action(db_session, payload)

        # Then
        assert result.success is True

    def test_update_business_not_found(self, db_session):
        """❌ 业务不存在时抛出 NotFoundError"""
        payload = UpdateBusinessStatusSchema(
            business_id=99999,
            status="业务评估"
        )

        with pytest.raises(NotFoundError):
            update_business_status_action(db_session, payload)


class TestDeleteBusinessAction:
    """删除业务测试"""

    def test_delete_business_success(self, db_session, sample_business):
        """✅ 正常删除业务"""
        # Given
        business_id = sample_business.id

        # When
        result = delete_business_action(db_session, business_id)

        # Then
        assert result.success is True

    def test_delete_business_not_found(self, db_session):
        """❌ 业务不存在时抛出 NotFoundError"""
        with pytest.raises(NotFoundError):
            delete_business_action(db_session, 99999)