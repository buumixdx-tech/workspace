"""
物流 Actions 单元测试
"""

import pytest
from logic.logistics import (
    create_logistics_plan_action,
    confirm_inbound_action,
    CreateLogisticsPlanSchema,
    ConfirmInboundSchema,
)


class TestLogisticsActions:
    """物流管理测试"""

    def test_create_logistics_plan_success(self, db_session, sample_virtual_contract):
        """✅ 正常创建物流计划"""
        # Given
        payload = CreateLogisticsPlanSchema(
            vc_id=sample_virtual_contract.id,
            orders=[
                {
                    "tracking_number": "SF1234567890",
                    "items": [{"name": "设备A", "qty": 1}],
                    "address_info": {"收货方联系电话": "13800138000", "发货方联系电话": "13900139000", "收货点位名称": "测试仓库", "发货点位名称": "供应商仓库", "address": "测试地址"}
                }
            ]
        )

        # When
        result = create_logistics_plan_action(db_session, payload)

        # Then
        assert result.success is True

    def test_create_logistics_plan_vc_not_found(self, db_session):
        """❌ 虚拟合同不存在"""
        payload = CreateLogisticsPlanSchema(
            vc_id=99999,
            orders=[]
        )

        result = create_logistics_plan_action(db_session, payload)

        assert result.success is False


class TestConfirmInboundAction:
    """确认收货/入库测试"""

    def test_confirm_inbound_success(self, db_session, sample_virtual_contract):
        """✅ 确认入库成功（需要先有物流记录）"""
        # 先创建物流记录
        from models import Logistics
        logistics = Logistics(
            virtual_contract_id=sample_virtual_contract.id,
            status="在途"
        )
        db_session.add(logistics)
        db_session.flush()
        log_id = logistics.id

        # Given: 确认入库
        payload = ConfirmInboundSchema(
            log_id=log_id,
            sn_list=["SN001", "SN002"]
        )

        # When
        result = confirm_inbound_action(db_session, payload)

        # Then: 应该成功
        assert result.success is True

    def test_confirm_inbound_log_not_found(self, db_session):
        """❌ 物流记录不存在"""
        payload = ConfirmInboundSchema(
            log_id=99999,
            sn_list=[]
        )

        result = confirm_inbound_action(db_session, payload)

        assert result.success is False