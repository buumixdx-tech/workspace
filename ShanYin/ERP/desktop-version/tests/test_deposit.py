"""
押金管理单元测试
测试押金计算、分摊、退还等逻辑
"""

import pytest
from datetime import datetime
from logic import deposit
from logic.constants import (
    VCType, VCStatus, CashFlowType, OperationalStatus
)
from models import VirtualContract, CashFlow, EquipmentInventory


class TestDepositModule:
    """押金模块入口测试"""

    def test_deposit_module_by_vc_id(self, db_session, sample_virtual_contract):
        """✅ 通过 VC ID 触发押金处理"""
        # Given: VC 有押金配置
        sample_virtual_contract.elements = {
            "items": [
                {"sku_id": 1, "qty": 10, "deposit": 100}
            ],
            "total_amount": 10000
        }
        sample_virtual_contract.deposit_info = {"should_receive": 1000}
        db_session.flush()

        # When
        deposit.deposit_module(vc_id=sample_virtual_contract.id, session=db_session)

        # Then: should_receive 会被重新计算
        db_session.refresh(sample_virtual_contract)
        assert sample_virtual_contract.deposit_info is not None

    def test_deposit_module_by_cf_id(self, db_session, sample_virtual_contract):
        """✅ 通过资金流水 ID 触发押金处理"""
        # Given: 创建押金流水
        cash_flow = CashFlow(
            virtual_contract_id=sample_virtual_contract.id,
            type=CashFlowType.DEPOSIT,
            amount=500,
            transaction_date=datetime.now()
        )
        db_session.add(cash_flow)
        db_session.flush()

        # When
        deposit.deposit_module(cf_id=cash_flow.id, session=db_session)

        # Then: 应该成功执行
        assert True  # 未抛出异常


class TestProcessVCDeposit:
    """VC 押金处理测试"""

    def test_calculate_should_receive_from_elements(self, db_session, sample_virtual_contract):
        """✅ 根据合同明细计算应收押金"""
        # Given: 设备采购合同，有 SKU 明细
        sample_virtual_contract.type = VCType.EQUIPMENT_PROCUREMENT
        sample_virtual_contract.elements = {
            "items": [
                {"sku_id": 1, "qty": 5, "deposit": 200},
                {"sku_id": 2, "qty": 3, "deposit": 150}
            ]
        }
        sample_virtual_contract.deposit_info = {}
        db_session.flush()

        # When
        deposit.process_vc_deposit(db_session, sample_virtual_contract.id)

        # Then: should_receive = 5*200 + 3*150 = 1000 + 450 = 1450
        db_session.refresh(sample_virtual_contract)
        assert sample_virtual_contract.deposit_info.get("should_receive") == 1450

    def test_should_receive_zero_when_no_deposit(self, db_session, sample_virtual_contract):
        """✅ 没有押金的 SKU 不计算"""
        # Given
        sample_virtual_contract.type = VCType.EQUIPMENT_PROCUREMENT
        sample_virtual_contract.elements = {
            "items": [
                {"sku_id": 1, "qty": 10, "deposit": 0}  # 无押金
            ]
        }
        sample_virtual_contract.deposit_info = {}
        db_session.flush()

        # When
        deposit.process_vc_deposit(db_session, sample_virtual_contract.id)

        # Then
        db_session.refresh(sample_virtual_contract)
        assert sample_virtual_contract.deposit_info.get("should_receive") == 0


class TestProcessVCDepositEdgeCases:
    """VC 押金处理边界情况测试"""

    def test_should_receive_from_elements_no_inventory(self, db_session, sample_virtual_contract):
        """✅ 尚未发货时，根据合同 elements 计算 should_receive（inv_exists=False 路径）"""
        sample_virtual_contract.type = VCType.EQUIPMENT_PROCUREMENT
        sample_virtual_contract.elements = {
            "items": [
                {"sku_id": 1, "qty": 4, "deposit": 100},
                {"sku_id": 2, "qty": 2, "deposit": 50}
            ]
        }
        sample_virtual_contract.deposit_info = {}
        db_session.flush()
        # 确保没有 EquipmentInventory 记录（inv_exists=False）

        deposit.process_vc_deposit(db_session, sample_virtual_contract.id)

        db_session.refresh(sample_virtual_contract)
        # 4*100 + 2*50 = 400 + 100 = 500
        assert sample_virtual_contract.deposit_info.get("should_receive") == 500

    def test_should_receive_zero_uses_epsilon_fallback(self, db_session, sample_virtual_contract):
        """✅ should_receive=0 时 ratio=1.0 EPSILON 回退（不应导致除零）"""
        sample_virtual_contract.type = VCType.EQUIPMENT_PROCUREMENT
        sample_virtual_contract.elements = {
            "items": [
                {"sku_id": 1, "qty": 10, "deposit": 0}  # deposit=0 → should_receive=0
            ]
        }
        db_session.flush()

        # 创建一条押金流水，使 paid_deposit > 0，触发分摊逻辑
        from models import CashFlow
        cf = CashFlow(
            virtual_contract_id=sample_virtual_contract.id,
            type=CashFlowType.DEPOSIT,
            amount=100,
            transaction_date=datetime.now()
        )
        db_session.add(cf)
        db_session.flush()

        # 处理押金：should_receive=0 → ratio=1.0（EPSILON fallback），不应除零崩溃
        deposit.process_vc_deposit(db_session, sample_virtual_contract.id)
        assert True  # 未抛出异常

    def test_deposit_no_inventories_skip_distribution(self, db_session, sample_virtual_contract):
        """✅ 没有运营中设备时跳过 distribution 分摊"""
        sample_virtual_contract.type = VCType.EQUIPMENT_PROCUREMENT
        sample_virtual_contract.elements = {
            "items": [{"sku_id": 1, "qty": 5, "deposit": 200}]
        }
        # 有押金流水使 paid_deposit > 0
        sample_virtual_contract.deposit_info = {"should_receive": 1000, "total_deposit": 500}
        db_session.flush()

        # 有 CashFlow 使 process_vc_deposit 走到分摊逻辑
        cf = CashFlow(
            virtual_contract_id=sample_virtual_contract.id,
            type=CashFlowType.DEPOSIT,
            amount=500,
            transaction_date=datetime.now()
        )
        db_session.add(cf)
        db_session.flush()

        # 处理押金：没有 EquipmentInventory，inventories 为空，直接 return
        deposit.process_vc_deposit(db_session, sample_virtual_contract.id)
        assert True  # 未抛出异常


class TestProcessCFDeposit:
    """资金流水押金处理测试"""

    def test_add_deposit_increases_total(self, db_session, sample_virtual_contract):
        """✅ 收取押金增加总额"""
        # Given: VC 当前押金为 0
        sample_virtual_contract.deposit_info = {"total_deposit": 0}
        db_session.flush()

        # 创建押金流水
        cash_flow = CashFlow(
            virtual_contract_id=sample_virtual_contract.id,
            type=CashFlowType.DEPOSIT,
            amount=1000,
            transaction_date=datetime.now()
        )
        db_session.add(cash_flow)
        db_session.flush()

        # When
        deposit.process_cf_deposit(db_session, cash_flow.id)

        # Then: total_deposit 应增加
        db_session.refresh(sample_virtual_contract)
        assert sample_virtual_contract.deposit_info.get("total_deposit") == 1000

    def test_return_deposit_decreases_total(self, db_session, sample_virtual_contract):
        """✅ 退还押金减少总额"""
        # Given: VC 当前押金为 1000
        sample_virtual_contract.deposit_info = {"total_deposit": 1000}
        db_session.flush()

        # 创建退还押金流水
        cash_flow = CashFlow(
            virtual_contract_id=sample_virtual_contract.id,
            type=CashFlowType.RETURN_DEPOSIT,
            amount=300,
            transaction_date=datetime.now()
        )
        db_session.add(cash_flow)
        db_session.flush()

        # When
        deposit.process_cf_deposit(db_session, cash_flow.id)

        # Then: total_deposit 应减少
        db_session.refresh(sample_virtual_contract)
        assert sample_virtual_contract.deposit_info.get("total_deposit") == 700


class TestDepositDistribution:
    """押金分摊测试"""

    def test_distribute_deposit_to_equipment(self, db_session, sample_virtual_contract):
        """✅ 押金分摊到每台设备（有实际押金流水）"""
        # Given: 有设备库存且有押金流水
        sample_virtual_contract.type = VCType.EQUIPMENT_PROCUREMENT
        sample_virtual_contract.elements = {
            "items": [{"sku_id": 1, "deposit": 100}]
        }
        db_session.flush()

        # 创建设备库存
        for i in range(5):
            inv = EquipmentInventory(
                virtual_contract_id=sample_virtual_contract.id,
                sku_id=1,
                operational_status=OperationalStatus.OPERATING,
                sn=f"SN00{i+1}"
            )
            db_session.add(inv)
        db_session.flush()

        # 创建押金流水（使 paid_deposit > 0）
        cf = CashFlow(
            virtual_contract_id=sample_virtual_contract.id,
            type=CashFlowType.DEPOSIT,
            amount=500,
            transaction_date=datetime.now()
        )
        db_session.add(cf)
        db_session.flush()

        # When: 处理押金
        deposit.process_vc_deposit(db_session, sample_virtual_contract.id)

        # Then: 函数执行成功，分摊逻辑已验证
        # 注：由于 should_receive 会被重新计算为 500，ratio = 500/500 = 1
        # 每台设备分摊 100 * 1 = 100
        inventories = db_session.query(EquipmentInventory).filter(
            EquipmentInventory.virtual_contract_id == sample_virtual_contract.id
        ).all()

        # 验证每台设备都分配了押金
        total_distributed = sum(inv.deposit_amount for inv in inventories)
        assert total_distributed == 500  # 500 / 5 台 = 每台 100


class TestReturnVCDepositRedirect:
    """退货单押金重定向测试"""

    def test_return_vc_deposit_redirects_to_original(self, db_session, sample_customer):
        """✅ 退货单的押金变动作用于原合同"""
        # Given: 创建原合同
        from logic.business import create_business_action, CreateBusinessSchema
        from logic.constants import BusinessStatus
        
        biz_payload = CreateBusinessSchema(customer_id=sample_customer.id)
        biz_result = create_business_action(db_session, biz_payload)
        
        original_vc = VirtualContract(
            business_id=biz_result.data["business_id"],
            type=VCType.EQUIPMENT_PROCUREMENT,
            elements={"total_amount": 10000},
            deposit_info={"total_deposit": 500},
            status=VCStatus.EXE,
            subject_status="执行",
            cash_status="执行"
        )
        db_session.add(original_vc)
        db_session.flush()

        # 创建退货单，关联原合同
        return_vc = VirtualContract(
            business_id=biz_result.data["business_id"],
            type=VCType.RETURN,
            related_vc_id=original_vc.id,
            elements={"total_amount": 1000},
            deposit_info={"total_deposit": 0},
            status=VCStatus.EXE,
            subject_status="执行",
            cash_status="执行"
        )
        db_session.add(return_vc)
        db_session.flush()

        # 退货单的押金流水
        cf = CashFlow(
            virtual_contract_id=return_vc.id,
            type=CashFlowType.DEPOSIT,
            amount=100,
            transaction_date=datetime.now()
        )
        db_session.add(cf)
        db_session.flush()

        # When: 处理退货单的押金
        deposit.process_cf_deposit(db_session, cf.id)

        # Then: 原合同的押金应增加（重定向）
        db_session.refresh(original_vc)
        assert original_vc.deposit_info.get("total_deposit") == 600