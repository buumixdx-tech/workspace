"""
虚拟合同 Actions 单元测试
根据实际 Schema 定义编写的测试用例
"""

import pytest
from logic.vc import (
    create_procurement_vc_action,
    create_material_supply_vc_action,
    create_return_vc_action,
    update_vc_action,
    delete_vc_action,
    CreateProcurementVCSchema,
    CreateMaterialSupplyVCSchema,
    CreateReturnVCSchema,
    VCElementSchema,
    UpdateVCSchema,
    DeleteVCSchema
)
from api.middleware.error_handler import NotFoundError


class TestCreateProcurementVCAction:
    """设备采购执行单创建测试"""

    def test_create_procurement_vc_success(self, db_session, sample_business, sample_sku, sample_supplier):
        """✅ 正常创建设备采购单"""
        from models import Point, SupplyChain

        # 创建设备采购所需的数据
        sup_wh = Point(name="测试供应商仓", type="供应商仓", supplier_id=sample_supplier.id)
        db_session.add(sup_wh)
        cust_wh = Point(name="客户仓库A", type="客户仓", customer_id=sample_business.customer_id)
        db_session.add(cust_wh)
        db_session.flush()

        sc = SupplyChain(supplier_id=sample_supplier.id, type="设备")
        db_session.add(sc)
        db_session.flush()

        payload = CreateProcurementVCSchema(
            business_id=sample_business.id,
            sc_id=sc.id,
            elements=[
                VCElementSchema(
                    shipping_point_id=0,
                    receiving_point_id=cust_wh.id,
                    sku_id=sample_sku.id,
                    qty=10,
                    price=1000,
                    deposit=100,
                    subtotal=10000,
                    sn_list=[]
                )
            ],
            total_amt=10000,
            total_deposit=1000,
            payment={"prepayment_ratio": 0.3},
            description="测试采购单"
        )

        result = create_procurement_vc_action(db_session, payload)

        assert result.success is True, f"创建失败: {result.error}"
        assert result.data is not None
        assert "vc_id" in result.data
        assert result.data["vc_id"] > 0

    def test_create_procurement_vc_business_not_found(self, db_session, sample_sku):
        """❌ 业务不存在"""
        # Given
        payload = CreateProcurementVCSchema(
            business_id=99999,
            sc_id=None,
            elements=[
                VCElementSchema(
                    shipping_point_id=1,
                    receiving_point_id=2,
                    sku_id=sample_sku.id,
                    qty=1,
                    price=1000,
                    deposit=0,
                    subtotal=1000,
                    sn_list=[]
                )
            ],
            total_amt=1000,
            total_deposit=0,
            payment={}
        )

        # When
        result = create_procurement_vc_action(db_session, payload)

        # Then
        assert result.success is False

    def test_create_procurement_vc_invalid_status(self, db_session, sample_business, sample_sku):
        """❌ 业务状态不允许下单"""
        # Given: 将业务状态改为已终止
        from models import Business
        sample_business.status = "业务终止"
        db_session.commit()

        payload = CreateProcurementVCSchema(
            business_id=sample_business.id,
            sc_id=None,
            elements=[
                VCElementSchema(
                    shipping_point_id=1,
                    receiving_point_id=2,
                    sku_id=sample_sku.id,
                    qty=1,
                    price=1000,
                    deposit=0,
                    subtotal=1000,
                    sn_list=[]
                )
            ],
            total_amt=1000,
            total_deposit=0,
            payment={}
        )

        # When
        result = create_procurement_vc_action(db_session, payload)

        # Then
        assert result.success is False


class TestCreateMaterialSupplyVCAction:
    """物料供应执行单创建测试"""

    def test_create_material_supply_business_not_found(self, db_session):
        """❌ 业务不存在"""
        payload = CreateMaterialSupplyVCSchema(
            business_id=99999,
            elements=[],
            total_amt=0
        )

        result = create_material_supply_vc_action(db_session, payload)

        assert result.success is False


class TestCreateReturnVCAction:
    """退货执行单创建测试"""

    def test_create_return_vc_target_not_found(self, db_session):
        """❌ 目标 VC 不存在"""
        payload = CreateReturnVCSchema(
            target_vc_id=99999,
            return_direction="客户退我方",
            elements=[],
            goods_amount=0,
            deposit_amount=0,
            logistics_cost=0,
            logistics_bearer="我方",
            total_refund=0,
            reason="测试"
        )

        result = create_return_vc_action(db_session, payload)

        assert result.success is False


class TestUpdateVCAction:
    """更新虚拟合同测试"""

    def test_update_vc_success(self, db_session, sample_virtual_contract):
        """✅ 正常更新 VC"""
        # Given
        new_description = "更新后的描述"
        new_elements = {"elements": [{"id": "sp1_rp2_sku1", "shipping_point_id": 1, "receiving_point_id": 2, "sku_id": 1, "qty": 1, "price": 1000, "deposit": 0, "subtotal": 1000, "sn_list": []}]}
        new_deposit_info = {"should_receive": 2000}

        # When
        payload = UpdateVCSchema(
            id=sample_virtual_contract.id,
            description=new_description,
            elements=new_elements,
            deposit_info=new_deposit_info
        )
        result = update_vc_action(db_session, payload)

        # Then
        assert result.success is True

    def test_update_vc_not_found(self, db_session):
        """❌ VC 不存在时抛出 NotFoundError"""
        payload = UpdateVCSchema(
            id=99999,
            description="描述",
            elements={},
            deposit_info={}
        )
        with pytest.raises(NotFoundError):
            update_vc_action(db_session, payload)


class TestDeleteVCAction:
    """删除虚拟合同测试"""

    def test_delete_vc_success(self, db_session, sample_virtual_contract):
        """✅ 正常删除 VC"""
        # Given
        vc_id = sample_virtual_contract.id

        # When
        payload = DeleteVCSchema(id=vc_id)
        result = delete_vc_action(db_session, payload)

        # Then
        assert result.success is True

    def test_delete_vc_not_found(self, db_session):
        """❌ VC 不存在时抛出 NotFoundError"""
        payload = DeleteVCSchema(id=99999)
        with pytest.raises(NotFoundError):
            delete_vc_action(db_session, payload)