"""
时间规则 Actions 单元测试
"""

import pytest
from logic.time_rules import save_rule_action, delete_rule_action, TimeRuleSchema


class TestRuleActions:
    """时间规则管理测试"""

    def test_save_rule_success(self, db_session, sample_business):
        """✅ 正常保存规则"""
        # Given
        payload = TimeRuleSchema(
            related_id=sample_business.id,
            related_type="业务",
            party="客户",
            trigger_event="业务开展",
            target_event="首次结算",
            offset=30,
            unit="自然日",
            direction="after",
            inherit=1,
            status="模板"
        )

        # When
        result = save_rule_action(db_session, payload)

        # Then
        assert result.success is True

    def test_save_rule_invalid_params(self, db_session):
        """✅ Pydantic 验证器会拦截无效参数"""
        # Pydantic 在构造时就会验证 offset >= 0
        with pytest.raises(Exception) as exc_info:
            TimeRuleSchema(
                related_id=1,
                related_type="业务",
                party="客户",
                trigger_event="业务开展",
                target_event="首次结算",
                offset=-1,  # 无效：负数
                unit="自然日",
                direction="after",
                inherit=1,
                status="模板"
            )
        
        assert "greater_than_equal" in str(exc_info.value)

    def test_delete_rule_not_found(self, db_session):
        """❌ 规则不存在"""
        result = delete_rule_action(db_session, 99999)

        assert result.success is False