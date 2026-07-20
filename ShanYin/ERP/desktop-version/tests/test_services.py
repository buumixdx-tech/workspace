"""
services 模块单元测试
测试 get_returnable_items 等跨模块业务逻辑
"""

import pytest
from datetime import datetime
from logic import services
from logic.constants import (
    VCType, VCStatus, ReturnDirection, OperationalStatus, DeviceStatus
)
from models import VirtualContract, EquipmentInventory, MaterialInventory, SKU, Point, CashFlow, SupplyChain, Supplier


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def equip_vc(db_session, sample_business, sample_sku):
    """设备采购型虚拟合同（含 EquipmentInventory 实物档案）"""
    vc = VirtualContract(
        business_id=sample_business.id,
        type=VCType.EQUIPMENT_PROCUREMENT,
        elements={
            "items": [
                {
                    "id": "ei_sn_001",
                    "sku_id": sample_sku.id,
                    "qty": 3,
                    "price": 1000,
                    "deposit": 100,
                    "subtotal": 3000,
                    "sn_list": []
                }
            ],
            "total_amount": 3000
        },
        deposit_info={"should_receive": 300, "total_deposit": 0},
        status=VCStatus.EXE,
        subject_status="发货",
        cash_status=VCStatus.EXE
    )
    db_session.add(vc)
    db_session.flush()

    # 创建 3 台设备的实物档案（均在运营中）
    for i in range(3):
        eq = EquipmentInventory(
            virtual_contract_id=vc.id,
            sku_id=sample_sku.id,
            sn=f"SN-EQ-{i+1:03d}",
            operational_status=OperationalStatus.OPERATING,
            device_status=DeviceStatus.NORMAL,
            deposit_amount=100
        )
        db_session.add(eq)
    db_session.flush()
    return vc


@pytest.fixture
def stock_vc(db_session, sample_business, sample_sku):
    """库存采购型虚拟合同（含 STOCK 状态 EquipmentInventory）"""
    vc = VirtualContract(
        business_id=sample_business.id,
        type=VCType.STOCK_PROCUREMENT,
        elements={
            "items": [
                {
                    "id": "si_sn_001",
                    "sku_id": sample_sku.id,
                    "qty": 2,
                    "price": 800,
                    "deposit": 50,
                    "subtotal": 1600,
                    "sn_list": []
                }
            ],
            "total_amount": 1600
        },
        deposit_info={"should_receive": 100, "total_deposit": 0},
        status=VCStatus.EXE,
        subject_status="发货",
        cash_status=VCStatus.EXE
    )
    db_session.add(vc)
    db_session.flush()

    # 2 台设备在库存状态
    for i in range(2):
        eq = EquipmentInventory(
            virtual_contract_id=vc.id,
            sku_id=sample_sku.id,
            sn=f"SN-STOCK-{i+1:03d}",
            operational_status=OperationalStatus.STOCK,
            device_status=DeviceStatus.NORMAL,
            deposit_amount=50
        )
        db_session.add(eq)
    db_session.flush()
    return vc


@pytest.fixture
def material_procurement_vc(db_session, sample_business, sample_sku):
    """物料采购型虚拟合同（含批次信息，精确追溯）"""
    # 创建两个点位
    point_a = Point(name="仓库A", customer_id=sample_business.customer_id)
    point_b = Point(name="仓库B", customer_id=sample_business.customer_id)
    db_session.add(point_a)
    db_session.add(point_b)
    db_session.flush()

    # 需要 supply_chain_id 来触发跨 VC 批次聚合
    from logic.constants import SKUType
    # sample_sku.supplier_id 来自 conftest.py 的 sample_supplier
    sc = SupplyChain(supplier_id=sample_sku.supplier_id, type=SKUType.MATERIAL)
    db_session.add(sc)
    db_session.flush()

    vc = VirtualContract(
        business_id=sample_business.id,
        supply_chain_id=sc.id,
        type=VCType.MATERIAL_PROCUREMENT,
        elements={
            "items": [
                {
                    "sku_id": sample_sku.id,
                    "sku_name": sample_sku.name,
                    "qty": 20,
                    "price": 10,
                    "receiving_point_id": point_a.id,
                    "batch_no": "BATCH-A"
                },
                {
                    "sku_id": sample_sku.id,
                    "sku_name": sample_sku.name,
                    "qty": 30,
                    "price": 10,
                    "receiving_point_id": point_b.id,
                    "batch_no": "BATCH-B"
                }
            ],
            "total_amount": 500
        },
        deposit_info={"should_receive": 0, "total_deposit": 0},
        status=VCStatus.EXE,
        subject_status="执行",
        cash_status=VCStatus.EXE
    )
    db_session.add(vc)
    db_session.flush()

    # 物料库存批次（用于 MATERIAL_PROCUREMENT 退货查实际库存量）
    mat_inv_a = MaterialInventory(
        sku_id=sample_sku.id,
        batch_no="BATCH-A",
        point_id=point_a.id,
        qty=20.0,
        latest_purchase_vc_id=vc.id
    )
    mat_inv_b = MaterialInventory(
        sku_id=sample_sku.id,
        batch_no="BATCH-B",
        point_id=point_b.id,
        qty=15.0,
        latest_purchase_vc_id=vc.id
    )
    db_session.add(mat_inv_a)
    db_session.add(mat_inv_b)
    db_session.flush()
    return vc


@pytest.fixture
def material_supply_vc_new_structure(db_session, sample_business, sample_sku):
    """物料供应型虚拟合同（新结构 elements[]，含 Point 记录）"""
    # 创建一个 Point 记录用于关联（直接用字符串 type，避免费型枚举存储问题）
    point = Point(
        name="客户点位-A",
        customer_id=sample_business.customer_id,
        type="运营点位"
    )
    db_session.add(point)
    db_session.flush()

    vc = VirtualContract(
        business_id=sample_business.id,
        type=VCType.MATERIAL_SUPPLY,
        elements={
            "items": [
                {
                    "sku_id": sample_sku.id,
                    "sku_name": sample_sku.name,
                    "qty": 30,
                    "price": 15,
                    "receiving_point_id": point.id
                }
            ],
            "total_amount": 450
        },
        deposit_info={"should_receive": 0, "total_deposit": 0},
        status=VCStatus.EXE,
        subject_status="发货",
        cash_status=VCStatus.EXE
    )
    db_session.add(vc)
    db_session.flush()
    return vc


@pytest.fixture
def material_supply_vc_old_structure(db_session, sample_business, sample_sku):
    """物料供应型虚拟合同（旧结构 points[]）"""
    vc = VirtualContract(
        business_id=sample_business.id,
        type=VCType.MATERIAL_SUPPLY,
        elements={
            "points": [
                {
                    "pointName": "旧仓库-测试",
                    "items": [
                        {"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 10, "price": 20}
                    ]
                }
            ],
            "total_amount": 200
        },
        deposit_info={"should_receive": 0, "total_deposit": 0},
        status=VCStatus.EXE,
        subject_status="发货",
        cash_status=VCStatus.EXE
    )
    db_session.add(vc)
    db_session.flush()
    return vc


# =============================================================================
# get_returnable_items — 设备采购类退货
# =============================================================================

class TestGetReturnableEquipment:
    """设备采购/库存采购退货：按 EquipmentInventory 实物档案计算"""

    def test_equipment_procurement_returnable_operating(self, db_session, equip_vc):
        """✅ 设备采购退货（客户→我）：返回所有 OPERATING 状态的设备"""
        result = services.get_returnable_items(
            db_session, equip_vc.id, {ReturnDirection.CUSTOMER_TO_US}
        )
        assert len(result) == 3
        for item in result:
            assert item["qty"] == 1
            assert item["sn"].startswith("SN-EQ-")
            assert item["price"] == 0.0  # CUSTOMER_TO_US → price=0

    def test_equipment_procurement_returnable_stock(self, db_session, stock_vc):
        """✅ 设备采购退货（我→供应商）：返回所有 STOCK 状态的设备"""
        result = services.get_returnable_items(
            db_session, stock_vc.id, {ReturnDirection.US_TO_SUPPLIER}
        )
        assert len(result) == 2
        for item in result:
            assert item["qty"] == 1
            assert item["sn"].startswith("SN-STOCK-")
            # US_TO_SUPPLIER: price 从 SKU.params.unit_price 获取（sample_sku 无 params 时 fallback 为 0）
            assert item["price"] >= 0

    def test_equipment_procurement_locked_by_existing_return_sn(self, db_session, equip_vc, sample_sku):
        """✅ 已有退货单（SN 级别）锁定：被锁定的 SN 不出现在退货列表"""
        # 创建一个退货单，锁定 SN-EQ-001
        return_vc = VirtualContract(
            business_id=equip_vc.business_id,
            type=VCType.RETURN,
            related_vc_id=equip_vc.id,
            elements={
                "items": [
                    {"sn": "SN-EQ-001", "sku_id": sample_sku.id, "qty": 1}
                ]
            },
            status=VCStatus.EXE,
            subject_status="执行",
            cash_status=VCStatus.EXE
        )
        db_session.add(return_vc)
        db_session.flush()

        result = services.get_returnable_items(
            db_session, equip_vc.id, {ReturnDirection.CUSTOMER_TO_US}
        )
        assert len(result) == 2
        sns = {r["sn"] for r in result}
        assert "SN-EQ-001" not in sns
        assert "SN-EQ-002" in sns
        assert "SN-EQ-003" in sns

    def test_unknown_vc_id_returns_empty(self, db_session):
        """✅ 无效 VC ID：返回空列表"""
        result = services.get_returnable_items(db_session, 99999, {ReturnDirection.CUSTOMER_TO_US})
        assert result == []


# =============================================================================
# get_returnable_items — 物料采购类退货
# =============================================================================

class TestGetReturnableMaterialProcurement:
    """物料采购退货：按批次维度聚合，支持跨 VC 批次追溯"""

    def test_material_procurement_returnable(self, db_session, material_procurement_vc):
        """✅ 物料采购退货：按批次聚合，返回 MaterialInventory 实际库存量"""
        result = services.get_returnable_items(
            db_session, material_procurement_vc.id, {ReturnDirection.US_TO_SUPPLIER}
        )
        # BATCH-A: VC qty=20, Inventory qty=20 → 最终 qty=20
        # BATCH-B: VC qty=30, Inventory qty=15 → 最终 qty=15（库存覆盖）
        assert len(result) == 2
        by_batch = {r["batch_no"]: r for r in result}
        assert by_batch["BATCH-A"]["qty"] == 20
        assert by_batch["BATCH-A"]["point_id"] is not None
        assert by_batch["BATCH-B"]["qty"] == 15  # 库存量覆盖 VC 元素量
        assert by_batch["BATCH-B"]["batch_no"] == "BATCH-B"

    def test_material_procurement_returnable_partial(self, db_session, sample_business, sample_sku):
        """✅ 物料采购退货：无 supply_chain_id 时返回空（无法跨 VC 聚合）"""
        point_x = Point(name="仓库X", customer_id=sample_business.customer_id)
        db_session.add(point_x)
        db_session.flush()

        vc = VirtualContract(
            business_id=sample_business.id,
            # 注意：没有 supply_chain_id，新逻辑返回空
            type=VCType.MATERIAL_PROCUREMENT,
            elements={
                "items": [
                    {"sku_id": sample_sku.id, "name": sample_sku.name, "qty": 5, "price": 10,
                     "receiving_point_id": point_x.id, "batch_no": "BATCH-X"}
                ]
            },
            deposit_info={"should_receive": 0, "total_deposit": 0},
            status=VCStatus.EXE,
            subject_status="执行",
            cash_status=VCStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        mat_inv = MaterialInventory(
            sku_id=sample_sku.id,
            batch_no="BATCH-X",
            point_id=point_x.id,
            qty=3.0,
            latest_purchase_vc_id=vc.id
        )
        db_session.add(mat_inv)
        db_session.flush()

        result = services.get_returnable_items(db_session, vc.id, {ReturnDirection.US_TO_SUPPLIER})
        # 无 supply_chain_id，无法跨 VC 聚合，返回空
        assert result == []

    def test_material_procurement_locked_by_existing_return_qty(
        self, db_session, material_procurement_vc, sample_sku
    ):
        """✅ 已有退货单（批次维度）锁定：batch_no 匹配则该批次标记为已退"""
        # 获取 BATCH-A 的 point_id
        batch_a_point_id = None
        for e in material_procurement_vc.elements["items"]:
            if e.get("batch_no") == "BATCH-A":
                batch_a_point_id = e.get("receiving_point_id")
                break

        return_vc = VirtualContract(
            business_id=material_procurement_vc.business_id,
            supply_chain_id=material_procurement_vc.supply_chain_id,
            type=VCType.RETURN,
            related_vc_id=material_procurement_vc.id,
            elements={
                "items": [
                    {"sku_id": sample_sku.id, "batch_no": "BATCH-A",
                     "receiving_point_id": batch_a_point_id, "qty": 10}
                ]
            },
            status=VCStatus.EXE,
            subject_status="执行",
            cash_status=VCStatus.EXE
        )
        db_session.add(return_vc)
        db_session.flush()

        result = services.get_returnable_items(
            db_session, material_procurement_vc.id, {ReturnDirection.US_TO_SUPPLIER}
        )
        by_batch = {r["batch_no"]: r for r in result}
        # BATCH-A 已退货 → qty=0, returnable=False
        assert by_batch["BATCH-A"]["qty"] == 0.0
        assert by_batch["BATCH-A"]["returnable"] is False
        assert by_batch["BATCH-A"]["returned_note"] == "已退货"
        # BATCH-B 未退货 → qty=15（库存量）
        assert by_batch["BATCH-B"]["qty"] == 15
        assert by_batch["BATCH-B"]["returnable"] is True


# =============================================================================
# get_returnable_items — 物料供应类退货
# =============================================================================

class TestGetReturnableMaterialSupply:
    """物料供应退货：客户退回，新结构按 batch_no 批次维度"""

    def test_material_supply_new_structure(self, db_session, material_supply_vc_new_structure):
        """✅ 物料供应退货（新结构 items[]）：返回聚合批次数据"""
        result = services.get_returnable_items(
            db_session, material_supply_vc_new_structure.id, {ReturnDirection.CUSTOMER_TO_US}
        )
        assert len(result) == 1
        assert result[0]["qty"] == 30
        assert result[0]["point_id"] is not None
        # batch_no 默认为 "-"（未指定）
        assert result[0]["batch_no"] == "-"

    def test_material_supply_locked_by_existing_return(
        self, db_session, material_supply_vc_new_structure, sample_sku
    ):
        """✅ 物料供应退货：batch_no 匹配时标记为已退"""
        # 新结构退货 VC 必须指定 batch_no 以实现批次锁定
        point_id = material_supply_vc_new_structure.elements["items"][0]["receiving_point_id"]
        return_vc = VirtualContract(
            business_id=material_supply_vc_new_structure.business_id,
            type=VCType.RETURN,
            related_vc_id=material_supply_vc_new_structure.id,
            elements={
                "items": [
                    {
                        "sku_id": sample_sku.id,
                        "receiving_point_id": point_id,
                        "batch_no": "-",  # 与 supply VC 的 batch_no="-" 匹配
                        "qty": 10
                    }
                ]
            },
            status=VCStatus.EXE,
            subject_status="执行",
            cash_status=VCStatus.EXE
        )
        db_session.add(return_vc)
        db_session.flush()

        result = services.get_returnable_items(
            db_session, material_supply_vc_new_structure.id, {ReturnDirection.CUSTOMER_TO_US}
        )
        assert len(result) == 1
        assert result[0]["qty"] == 0.0  # 整批已退
        assert result[0]["returnable"] is False


# =============================================================================
# get_returnable_items — 边界情况
# =============================================================================

class TestGetReturnableEdgeCases:
    """边界情况"""

    def test_cancelled_return_vc_does_not_lock(self, db_session, equip_vc, sample_sku):
        """✅ 已取消的退货单不计入锁定量"""
        return_vc = VirtualContract(
            business_id=equip_vc.business_id,
            type=VCType.RETURN,
            related_vc_id=equip_vc.id,
            elements={
                "items": [
                    {"sn": "SN-EQ-001", "sku_id": sample_sku.id, "qty": 1}
                ]
            },
            status=VCStatus.CANCELLED,  # 已取消
            subject_status="执行",
            cash_status=VCStatus.EXE
        )
        db_session.add(return_vc)
        db_session.flush()

        result = services.get_returnable_items(
            db_session, equip_vc.id, {ReturnDirection.CUSTOMER_TO_US}
        )
        # 取消的退货不锁定，应返回全部 3 台
        assert len(result) == 3

    def test_no_inventory_returns_empty(self, db_session, sample_business):
        """✅ 设备采购合同但无实物档案：返回空（无货可退）"""
        vc = VirtualContract(
            business_id=sample_business.id,
            type=VCType.EQUIPMENT_PROCUREMENT,
            elements={
                "items": [
                    {"sku_id": 1, "qty": 5, "price": 1000, "deposit": 100}
                ]
            },
            deposit_info={"should_receive": 500, "total_deposit": 0},
            status=VCStatus.EXE,
            subject_status="执行",
            cash_status=VCStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        result = services.get_returnable_items(
            db_session, vc.id, {ReturnDirection.CUSTOMER_TO_US}
        )
        assert result == []
