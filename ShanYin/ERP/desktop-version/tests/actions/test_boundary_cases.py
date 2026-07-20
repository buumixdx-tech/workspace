"""
资金流与物流边界条件测试
测试各种边界情况和异常场景

注意：这些测试验证完善后的边界校验功能。
"""

import pytest
from datetime import datetime, timedelta
from logic.finance import create_cash_flow_action, CreateCashFlowSchema
from logic.logistics import (
    create_logistics_plan_action,
    confirm_inbound_action,
    update_express_order_status_action,
    CreateLogisticsPlanSchema,
    ConfirmInboundSchema,
    ExpressOrderStatusSchema,
)
from logic.constants import CashFlowType, VCStatus


class TestCashFlowBoundary:
    """资金流水边界条件测试"""

    # ==================== 金额边界 ====================
    
    def test_cash_flow_amount_zero(self, db_session, sample_virtual_contract):
        """✅ 金额为0在 Schema 验证时就会失败（Pydantic 保护）"""
        with pytest.raises(Exception) as exc_info:
            CreateCashFlowSchema(
                vc_id=sample_virtual_contract.id,
                type=CashFlowType.PREPAYMENT,
                amount=0,
                transaction_date=datetime.now()
            )
        assert "greater than 0" in str(exc_info.value)

    def test_cash_flow_amount_negative(self, db_session, sample_virtual_contract):
        """✅ 金额为负数在 Schema 验证时就会失败（Pydantic 保护）"""
        with pytest.raises(Exception) as exc_info:
            CreateCashFlowSchema(
                vc_id=sample_virtual_contract.id,
                type=CashFlowType.PREPAYMENT,
                amount=-1000,
                transaction_date=datetime.now()
            )
        assert "greater than 0" in str(exc_info.value)

    def test_cash_flow_amount_very_large(self, db_session, sample_virtual_contract):
        """✅ 超大金额边界测试"""
        payload = CreateCashFlowSchema(
            vc_id=sample_virtual_contract.id,
            type=CashFlowType.PREPAYMENT,
            amount=999999999999,
            transaction_date=datetime.now()
        )
        result = create_cash_flow_action(db_session, payload)
        assert result.success is True

    def test_cash_flow_future_date(self, db_session, sample_virtual_contract):
        """✅ 未来日期资金流水"""
        payload = CreateCashFlowSchema(
            vc_id=sample_virtual_contract.id,
            type=CashFlowType.PREPAYMENT,
            amount=1000,
            transaction_date=datetime.now() + timedelta(days=365)
        )
        result = create_cash_flow_action(db_session, payload)
        assert result.success is True

    def test_cash_flow_very_old_date(self, db_session, sample_virtual_contract):
        """✅ 极早日期资金流水"""
        payload = CreateCashFlowSchema(
            vc_id=sample_virtual_contract.id,
            type=CashFlowType.PREPAYMENT,
            amount=1000,
            transaction_date=datetime(2000, 1, 1)
        )
        result = create_cash_flow_action(db_session, payload)
        assert result.success is True

    # ==================== VC状态校验 ====================
    
    def test_cash_flow_vc_cancelled(self, db_session, sample_customer):
        """✅ 已取消的 VC 不允许创建资金流水"""
        from models import Business, VirtualContract
        
        business = Business(
            customer_id=sample_customer.id,
            status="业务开展",
            details={}
        )
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type="设备采购",
            elements={"total_amount": 10000},
            deposit_info={},
            status=VCStatus.CANCELLED,
            subject_status="执行",
            cash_status="执行"
        )
        db_session.add(vc)
        db_session.flush()

        payload = CreateCashFlowSchema(
            vc_id=vc.id,
            type=CashFlowType.PREPAYMENT,
            amount=1000,
            transaction_date=datetime.now()
        )

        # 修复后：拒绝操作
        result = create_cash_flow_action(db_session, payload)
        assert result.success is False
        assert "取消" in result.error

    def test_cash_flow_vc_terminated(self, db_session, sample_customer):
        """✅ 已终止的 VC 不允许创建资金流水"""
        from models import Business, VirtualContract
        
        business = Business(
            customer_id=sample_customer.id,
            status="业务终止",
            details={}
        )
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type="设备采购",
            elements={"total_amount": 10000},
            deposit_info={},
            status=VCStatus.TERMINATED,
            subject_status="执行",
            cash_status="执行"
        )
        db_session.add(vc)
        db_session.flush()

        payload = CreateCashFlowSchema(
            vc_id=vc.id,
            type=CashFlowType.PREPAYMENT,
            amount=1000,
            transaction_date=datetime.now()
        )

        # 修复后：拒绝操作
        result = create_cash_flow_action(db_session, payload)
        assert result.success is False
        assert "终止" in result.error

    # ==================== 资金类型校验 ====================
    
    def test_cash_flow_invalid_type(self, db_session, sample_virtual_contract):
        """✅ 无效的资金类型被拒绝"""
        payload = CreateCashFlowSchema(
            vc_id=sample_virtual_contract.id,
            type="无效类型",
            amount=1000,
            transaction_date=datetime.now()
        )

        # 修复后：拒绝无效类型
        result = create_cash_flow_action(db_session, payload)
        assert result.success is False
        assert "无效" in result.error

    def test_cash_flow_all_valid_types(self, db_session, sample_virtual_contract):
        """✅ 所有定义的资金类型都能创建"""
        valid_types = [
            CashFlowType.PREPAYMENT,
            CashFlowType.FULFILLMENT,
            CashFlowType.DEPOSIT,
            CashFlowType.RETURN_DEPOSIT,
            CashFlowType.REFUND,
            CashFlowType.OFFSET_PAY,
            CashFlowType.OFFSET_IN,
            CashFlowType.DEPOSIT_OFFSET_IN,
            CashFlowType.PENALTY,
        ]

        for cf_type in valid_types:
            payload = CreateCashFlowSchema(
                vc_id=sample_virtual_contract.id,
                type=cf_type,
                amount=100,
                transaction_date=datetime.now()
            )
            result = create_cash_flow_action(db_session, payload)
            assert result.success is True, f"类型 {cf_type} 应该成功"


class TestLogisticsBoundary:
    """物流边界条件测试"""

    # ==================== 订单列表校验 ====================
    
    def test_logistics_empty_orders(self, db_session, sample_virtual_contract):
        """✅ 空订单列表被拒绝"""
        payload = CreateLogisticsPlanSchema(
            vc_id=sample_virtual_contract.id,
            orders=[]
        )
        # 修复后：拒绝空订单
        result = create_logistics_plan_action(db_session, payload)
        assert result.success is False
        assert "不能为空" in result.error

    def test_logistics_very_large_batch(self, db_session, sample_virtual_contract):
        """✅ 大量订单边界测试"""
        orders = []
        for i in range(100):
            orders.append({
                "tracking_number": f"SF{i:08d}",
                "items": [{"name": f"设备{i}", "qty": 1}],
                "address_info": {
                    "收货方联系电话": f"138{i:08d}",
                    "发货方联系电话": f"139{i:08d}",
                    "收货点位名称": f"仓库{i}",
                    "发货点位名称": f"供应商{i}",
                    "address": f"地址{i}"
                }
            })
        
        payload = CreateLogisticsPlanSchema(
            vc_id=sample_virtual_contract.id,
            orders=orders
        )
        result = create_logistics_plan_action(db_session, payload)
        assert result.success is True

    # ==================== 订单数据校验 ====================
    
    def test_logistics_missing_address(self, db_session, sample_virtual_contract):
        """✅ 缺少地址信息被拒绝"""
        payload = CreateLogisticsPlanSchema(
            vc_id=sample_virtual_contract.id,
            orders=[
                {
                    "tracking_number": "SF1234567890",
                    "items": [{"name": "设备A", "qty": 1}],
                }
            ]
        )
        result = create_logistics_plan_action(db_session, payload)
        assert result.success is False
        assert "地址" in result.error

    def test_logistics_empty_tracking_number(self, db_session, sample_virtual_contract):
        """✅ 空快递单号被拒绝"""
        payload = CreateLogisticsPlanSchema(
            vc_id=sample_virtual_contract.id,
            orders=[
                {
                    "tracking_number": "",
                    "items": [{"sku_id": 1, "sku_name": "设备A", "qty": 1}],
                    "address_info": {
                        "收货方联系电话": "13800138000",
                        "发货方联系电话": "13900139000",
                        "收货点位名称": "测试仓库",
                        "发货点位名称": "供应商",
                        "address": "测试地址"
                    }
                }
            ]
        )
        # 修复后：拒绝空单号
        result = create_logistics_plan_action(db_session, payload)
        assert result.success is False
        assert "单号" in result.error

    def test_logistics_duplicate_tracking_number(self, db_session, sample_virtual_contract):
        """✅ 重复快递单号可以创建（业务允许）"""
        payload = CreateLogisticsPlanSchema(
            vc_id=sample_virtual_contract.id,
            orders=[
                {
                    "tracking_number": "SF1234567890",
                    "items": [{"sku_id": 1, "sku_name": "设备A", "qty": 1}],
                    "address_info": {"收货方联系电话": "13800138000", "发货方联系电话": "13900139000", "收货点位名称": "仓库A", "发货点位名称": "供应商A", "address": "地址1"}
                },
                {
                    "tracking_number": "SF1234567890",
                    "items": [{"sku_id": 2, "sku_name": "设备B", "qty": 1}],
                    "address_info": {"收货方联系电话": "13800138001", "发货方联系电话": "13900139001", "收货点位名称": "仓库B", "发货点位名称": "供应商B", "address": "地址2"}
                }
            ]
        )
        result = create_logistics_plan_action(db_session, payload)
        assert result.success is True

    # ==================== 物流状态校验 ====================
    
    def test_logistics_already_finished(self, db_session, sample_virtual_contract):
        """✅ 已完成的物流不允许重复操作"""
        from models import Logistics
        
        logistics = Logistics(
            virtual_contract_id=sample_virtual_contract.id,
            status="完成"
        )
        db_session.add(logistics)
        db_session.flush()
        log_id = logistics.id

        payload = ConfirmInboundSchema(
            log_id=log_id,
            sn_list=["SN001", "SN002"]
        )
        result = confirm_inbound_action(db_session, payload)
        assert result.success is False

    # ==================== 入库序列号校验 ====================
    
    def test_inbound_empty_sn_list(self, db_session, sample_virtual_contract):
        """✅ 空序列号列表被拒绝"""
        from models import Logistics
        
        logistics = Logistics(
            virtual_contract_id=sample_virtual_contract.id,
            status="在途"
        )
        db_session.add(logistics)
        db_session.flush()
        log_id = logistics.id

        payload = ConfirmInboundSchema(
            log_id=log_id,
            sn_list=[]
        )
        # 修复后：拒绝空 SN 列表
        result = confirm_inbound_action(db_session, payload)
        assert result.success is False
        assert "不能为空" in result.error

    def test_inbound_duplicate_sn(self, db_session, sample_virtual_contract):
        """✅ 重复的设备序列号被拒绝"""
        from models import Logistics
        
        logistics = Logistics(
            virtual_contract_id=sample_virtual_contract.id,
            status="在途"
        )
        db_session.add(logistics)
        db_session.flush()
        log_id = logistics.id

        payload = ConfirmInboundSchema(
            log_id=log_id,
            sn_list=["SN001", "SN001"]
        )
        # 修复后：拒绝重复 SN
        result = confirm_inbound_action(db_session, payload)
        assert result.success is False
        assert "重复" in result.error

    def test_express_status_schema_requires_logistics_id(self, db_session, sample_virtual_contract):
        """✅ ExpressOrderStatusSchema 需要 logistics_id 字段"""
        with pytest.raises(Exception) as exc_info:
            ExpressOrderStatusSchema(
                order_id=1,
                target_status="待发货"
            )
        assert "logistics_id" in str(exc_info.value)

    # ==================== VC状态校验 ====================
    
    def test_logistics_vc_completed(self, db_session, sample_customer):
        """✅ 已完成的 VC 不允许创建物流"""
        from models import Business, VirtualContract
        
        business = Business(
            customer_id=sample_customer.id,
            status="业务完成",
            details={}
        )
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type="设备采购",
            elements={"total_amount": 10000},
            deposit_info={},
            status="完成",
            subject_status="完成",
            cash_status="完成"
        )
        db_session.add(vc)
        db_session.flush()

        payload = CreateLogisticsPlanSchema(
            vc_id=vc.id,
            orders=[
                {
                    "tracking_number": "SF1234567890",
                    "items": [{"sku_id": 1, "sku_name": "设备A", "qty": 1}],
                    "address_info": {
                        "收货方联系电话": "13800138000",
                        "发货方联系电话": "13900139000",
                        "收货点位名称": "测试仓库",
                        "发货点位名称": "供应商",
                        "address": "测试地址"
                    }
                }
            ]
        )

        # 修复后：拒绝操作
        result = create_logistics_plan_action(db_session, payload)
        assert result.success is False
        assert "完成" in result.error
