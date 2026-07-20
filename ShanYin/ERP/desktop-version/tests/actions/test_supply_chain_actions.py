"""
供应链 Actions 单元测试
"""

import pytest
from logic.supply_chain import create_supply_chain_action
from logic.supply_chain.schemas import CreateSupplyChainSchema, SupplyChainItemSchema


class TestSupplyChainActions:
    """供应链管理测试"""

    def test_create_supply_chain_success(self, db_session, sample_supplier, sample_sku):
        """✅ 正常创建供应链协议"""
        # Given
        payload = CreateSupplyChainSchema(
            supplier_id=sample_supplier.id,
            supplier_name=sample_supplier.name,
            type="设备",
            items=[
                SupplyChainItemSchema(sku_id=sample_sku.id, price=1000.0, is_floating=False),
            ],
            payment_terms={"prepayment_ratio": 0.3, "balance_period": 30}
        )

        # When
        result = create_supply_chain_action(db_session, payload)

        # Then
        assert result.success is True
        # 验证 SupplyChainItem 已创建
        from models import SupplyChainItem
        items = db_session.query(SupplyChainItem).filter(
            SupplyChainItem.supply_chain_id == result.data["sc_id"]
        ).all()
        assert len(items) == 1
        assert items[0].sku_id == sample_sku.id
        assert items[0].price == 1000.0

    def test_create_supply_chain_supplier_not_found(self, db_session):
        """❌ 供应商不存在"""
        payload = CreateSupplyChainSchema(
            supplier_id=99999,
            supplier_name="不存在的供应商",
            type="设备",
            items=[],
            payment_terms={}
        )

        result = create_supply_chain_action(db_session, payload)

        assert result.success is False

    def test_create_supply_chain_with_template_rules(self, db_session, sample_supplier, sample_sku):
        """✅ 创建供应链时附加模板规则"""
        payload = CreateSupplyChainSchema(
            supplier_id=sample_supplier.id,
            supplier_name=sample_supplier.name,
            type="设备",
            items=[
                SupplyChainItemSchema(sku_id=sample_sku.id, price=1000.0, is_floating=False),
            ],
            payment_terms={"prepayment_ratio": 0.3},
            contract_num="SC-20260001"
        )

        result = create_supply_chain_action(db_session, payload)

        assert result.success is True
