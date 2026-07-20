"""
VC Elements 统一结构测试
验证 6 种 VC 类型创建的 elements 数据结构完全正确
"""

import pytest
from logic.vc import (
    create_procurement_vc_action,
    create_material_supply_vc_action,
    create_return_vc_action,
    create_mat_procurement_vc_action,
    create_stock_procurement_vc_action,
    create_inventory_allocation_action,
    CreateProcurementVCSchema,
    CreateMaterialSupplyVCSchema,
    CreateReturnVCSchema,
    CreateMatProcurementVCSchema,
    CreateStockProcurementVCSchema,
    AllocateInventorySchema,
    VCElementSchema,
)
from logic.constants import VCType, VCStatus, SubjectStatus, CashStatus


# ---------------------------------------------------------------------------
# 公共 fixture：基础数据
# ---------------------------------------------------------------------------

@pytest.fixture
def base_data(db_session, sample_customer, sample_supplier):
    """创建业务、供应链、SKU 等基础数据"""
    from models import Business, SupplyChain, SKU

    # 业务（推进到 ACTIVE）
    biz = Business(customer_id=sample_customer.id, status="业务开展", details={})
    db_session.add(biz)
    db_session.flush()

    # 供应链
    sc = SupplyChain(
        supplier_id=sample_supplier.id,
        type="设备"
    )
    db_session.add(sc)
    db_session.flush()

    # SKU（设备类）
    sku_equip = SKU(supplier_id=sample_supplier.id, name="测试设备A", type_level1="设备", type_level2="主机")
    db_session.add(sku_equip)
    db_session.flush()

    from models import SupplyChainItem
    sci = SupplyChainItem(supply_chain_id=sc.id, sku_id=sku_equip.id, price=1000.0, is_floating=False)
    db_session.add(sci)
    db_session.flush()

    # SKU（物料类）
    sku_mat = SKU(supplier_id=sample_supplier.id, name="测试物料A", type_level1="物料")
    db_session.add(sku_mat)
    db_session.flush()

    return {
        "business": biz,
        "supply_chain": sc,
        "sku_equip": sku_equip,
        "sku_mat": sku_mat,
        "supplier": sample_supplier,
    }


# ---------------------------------------------------------------------------
# 通用断言：验证 elements 元素结构
# ---------------------------------------------------------------------------

def assert_element_item(elem: dict, expected_keys: dict):
    """验证单个 element 条目的所有字段"""
    assert "id" in elem, f"element 缺少 id 字段"
    assert "shipping_point_id" in elem, "element 缺少 shipping_point_id"
    assert "receiving_point_id" in elem, "element 缺少 receiving_point_id"
    assert "sku_id" in elem, "element 缺少 sku_id"
    assert "qty" in elem, "element 缺少 qty"
    assert "price" in elem, "element 缺少 price"
    assert "deposit" in elem, "element 缺少 deposit"
    assert "subtotal" in elem, "element 缺少 subtotal"
    assert "sn_list" in elem, "element 缺少 sn_list"
    assert isinstance(elem["sn_list"], list), "sn_list 必须是 list"

    # id 格式验证：sp{shipping}_rp{receiving}_sku{sku}_bn{batch_no}（batch_no 为空时输出 _bn-）
    assert elem["id"] == f"sp{elem['shipping_point_id']}_rp{elem['receiving_point_id']}_sku{elem['sku_id']}_bn-"

    # 小计验证
    assert abs(elem["subtotal"] - elem["qty"] * elem["price"]) < 0.01

    # 期望值比对
    for key, val in expected_keys.items():
        assert elem[key] == val, f"element.{key} 期望 {val}，实际 {elem[key]}"


def assert_vc_elements_structure(vc, expected_type: str, expected_elements_count: int):
    """验证 VC elements 整体结构"""
    elems = vc.elements
    assert elems is not None, "elements 不能为 None"
    assert "items" in elems, "elements 缺少顶层 items 键"
    assert "vc_type" not in elems, "elements 不应包含冗余 vc_type 字段"
    assert "skus" not in elems, "elements 不应包含旧结构 skus"
    assert "points" not in elems, "elements 不应包含旧结构 points"

    items = elems["items"]
    assert isinstance(items, list), "items 必须是 list"
    assert len(items) == expected_elements_count, f"items 数量期望 {expected_elements_count}，实际 {len(items)}"

    for item in items:
        assert_element_item(item, {})

    # type 字段独立存在于 VC 表，不在 elements 内
    assert vc.type == expected_type, f"vc.type 期望 {expected_type}，实际 {vc.type}"


# ---------------------------------------------------------------------------
# 测试 1：设备采购 VC
# ---------------------------------------------------------------------------

class TestEquipmentProcurementElements:
    """设备采购 VC elements 结构验证"""

    def test_elements_structure_single_item(self, db_session, base_data):
        """✅ 单一条目设备采购"""
        from models import Point, SupplyChain

        biz = base_data["business"]
        sku = base_data["sku_equip"]
        supplier = base_data["supplier"]

        # 创建设备采购所需的点位数据
        # 1. 供应商仓库（发货点）
        sup_wh = Point(name="测试供应商仓", type="供应商仓", supplier_id=supplier.id)
        db_session.add(sup_wh)
        db_session.flush()

        # 2. 客户仓库（收货点）
        cust_wh = Point(name="客户仓库A", type="客户仓", customer_id=biz.customer_id)
        db_session.add(cust_wh)
        db_session.flush()

        # 3. 供应链（用于查找供应商仓库）
        sc = SupplyChain(supplier_id=supplier.id, type="设备")
        db_session.add(sc)
        db_session.flush()

        payload = CreateProcurementVCSchema(
            business_id=biz.id,
            sc_id=sc.id,
            elements=[
                VCElementSchema(
                    shipping_point_id=0,  # 由供应链确定，不使用
                    receiving_point_id=cust_wh.id,
                    sku_id=sku.id,
                    qty=5,
                    price=1000.0,
                    deposit=100.0,
                    subtotal=5000.0,
                    sn_list=[]
                )
            ],
            total_amt=5000.0,
            total_deposit=500.0,
            payment={"prepayment_ratio": 0.3, "balance_period": 30, "day_rule": "自然日", "start_trigger": "入库"},
            description="测试设备采购"
        )

        result = create_procurement_vc_action(db_session, payload)
        assert result.success is True, f"设备采购创建失败: {result.error}"

        from models import VirtualContract
        vc = db_session.query(VirtualContract).get(result.data["vc_id"])
        assert vc is not None

        assert_vc_elements_structure(vc, VCType.EQUIPMENT_PROCUREMENT, 1)
        elems = vc.elements
        assert "total_amount" in elems
        assert "payment_terms" in elems
        assert elems["total_amount"] == 5000.0
        assert elems["payment_terms"]["prepayment_ratio"] == 0.3

        item = elems["items"][0]
        # 商业逻辑：shipping_point_id=供应商仓库, receiving_point_id=客户仓库
        assert_element_item(item, {
            "shipping_point_id": sup_wh.id,
            "receiving_point_id": cust_wh.id,
            "sku_id": sku.id,
            "qty": 5.0,
            "price": 1000.0,
            "deposit": 100.0,
            "subtotal": 5000.0,
            "sn_list": [],
        })
        assert item["id"] == f"sp{sup_wh.id}_rp{cust_wh.id}_sku{sku.id}_bn-"

        assert vc.status == VCStatus.EXE
        assert vc.subject_status == SubjectStatus.EXE
        assert vc.cash_status == CashStatus.EXE
        assert vc.deposit_info["should_receive"] == 500.0

    def test_elements_structure_multiple_items(self, db_session, base_data):
        """✅ 多条目设备采购（同一 SKU 不同收货点位）"""
        from models import Point, SupplyChain

        biz = base_data["business"]
        sku = base_data["sku_equip"]
        supplier = base_data["supplier"]

        # 供应商仓库
        sup_wh = Point(name="测试供应商仓", type="供应商仓", supplier_id=supplier.id)
        db_session.add(sup_wh)
        db_session.flush()

        # 两个客户仓库
        cust_wh1 = Point(name="客户仓库A", type="客户仓", customer_id=biz.customer_id)
        cust_wh2 = Point(name="客户仓库B", type="客户仓", customer_id=biz.customer_id)
        db_session.add_all([cust_wh1, cust_wh2])
        db_session.flush()

        sc = SupplyChain(supplier_id=supplier.id, type="设备")
        db_session.add(sc)
        db_session.flush()

        payload = CreateProcurementVCSchema(
            business_id=biz.id,
            sc_id=sc.id,
            elements=[
                VCElementSchema(
                    shipping_point_id=0, receiving_point_id=cust_wh1.id,
                    sku_id=sku.id, qty=2, price=1000.0, deposit=100.0, subtotal=2000.0, sn_list=[]
                ),
                VCElementSchema(
                    shipping_point_id=0, receiving_point_id=cust_wh2.id,
                    sku_id=sku.id, qty=3, price=1000.0, deposit=100.0, subtotal=3000.0, sn_list=[]
                ),
            ],
            total_amt=5000.0,
            total_deposit=500.0,
            payment={"prepayment_ratio": 0.3, "balance_period": 0, "day_rule": "自然日", "start_trigger": "入库"},
            description=""
        )

        result = create_procurement_vc_action(db_session, payload)
        assert result.success is True

        from models import VirtualContract
        vc = db_session.query(VirtualContract).get(result.data["vc_id"])
        elems = vc.elements

        assert_vc_elements_structure(vc, VCType.EQUIPMENT_PROCUREMENT, 2)
        assert elems["items"][0]["receiving_point_id"] == cust_wh1.id
        assert elems["items"][1]["receiving_point_id"] == cust_wh2.id
        assert elems["items"][0]["qty"] == 2.0
        assert elems["items"][1]["qty"] == 3.0
        # 所有 item 发货点相同（供应商仓库）
        assert elems["items"][0]["shipping_point_id"] == sup_wh.id
        assert elems["items"][1]["shipping_point_id"] == sup_wh.id


# ---------------------------------------------------------------------------
# 测试 2：库存采购 VC
# ---------------------------------------------------------------------------

class TestStockProcurementElements:
    """库存采购 VC elements 结构验证"""

    def test_elements_structure(self, db_session, base_data):
        """✅ 库存采购 elements 结构"""
        from models import Point, SupplyChain

        sc = base_data["supply_chain"]
        sku = base_data["sku_equip"]
        supplier = base_data["supplier"]

        # 供应商仓库（发货点）
        sup_wh = Point(name="测试供应商仓", type="供应商仓", supplier_id=supplier.id)
        db_session.add(sup_wh)
        db_session.flush()

        # 我们仓库（收货点）
        our_wh = Point(name="总部仓", type="自有仓")
        db_session.add(our_wh)
        db_session.flush()

        payload = CreateStockProcurementVCSchema(
            sc_id=sc.id,
            elements=[
                VCElementSchema(
                    shipping_point_id=0,
                    receiving_point_id=our_wh.id,
                    sku_id=sku.id, qty=10, price=2000.0,
                    deposit=0.0, subtotal=20000.0, sn_list=[]
                )
            ],
            total_amt=20000.0,
            payment={"prepayment_ratio": 0.5, "balance_period": 0, "day_rule": "自然日", "start_trigger": "入库"}
        )

        result = create_stock_procurement_vc_action(db_session, payload)
        assert result.success is True, f"库存采购创建失败: {result.error}"

        from models import VirtualContract
        vc = db_session.query(VirtualContract).get(result.data["vc_id"])
        assert vc is not None

        assert_vc_elements_structure(vc, VCType.STOCK_PROCUREMENT, 1)
        elems = vc.elements
        assert "total_amount" in elems
        assert "payment_terms" in elems
        assert elems["total_amount"] == 20000.0
        assert elems["payment_terms"]["prepayment_ratio"] == 0.5

        item = elems["items"][0]
        # 商业逻辑：shipping_point_id=供应商仓库, receiving_point_id=我们仓库
        assert_element_item(item, {
            "shipping_point_id": sup_wh.id,
            "receiving_point_id": our_wh.id,
            "sku_id": sku.id,
            "qty": 10.0,
            "price": 2000.0,
            "deposit": 0.0,
            "subtotal": 20000.0,
            "sn_list": [],
        })

        assert vc.cash_status == CashStatus.EXE


# ---------------------------------------------------------------------------
# 测试 3：物料采购 VC
# ---------------------------------------------------------------------------

class TestMaterialProcurementElements:
    """物料采购 VC elements 结构验证"""

    def test_elements_structure(self, db_session, sample_supplier):
        """✅ 物料采购 elements 结构"""
        from models import SupplyChain, SKU, Business, Point
        from logic.constants import SKUType

        # 供应商仓库（发货点）
        sup_wh = Point(name="测试供应商仓", type="供应商仓", supplier_id=sample_supplier.id)
        db_session.add(sup_wh)
        db_session.flush()

        # 我们仓库（收货点）
        our_wh = Point(name="总部仓", type="自有仓")
        db_session.add(our_wh)
        db_session.flush()

        sc = SupplyChain(
            supplier_id=sample_supplier.id,
            type=SKUType.MATERIAL
        )
        db_session.add(sc)
        db_session.flush()

        sku = SKU(supplier_id=sample_supplier.id, name="测试物料X", type_level1="物料")
        db_session.add(sku)
        db_session.flush()

        from models import SupplyChainItem
        sci = SupplyChainItem(supply_chain_id=sc.id, sku_id=sku.id, price=5.0, is_floating=False)
        db_session.add(sci)
        db_session.flush()

        payload = CreateMatProcurementVCSchema(
            sc_id=sc.id,
            elements=[
                VCElementSchema(
                    shipping_point_id=0,
                    receiving_point_id=our_wh.id,
                    sku_id=sku.id, qty=100, price=5.0,
                    deposit=0.0, subtotal=500.0, sn_list=[]
                )
            ],
            total_amt=500.0,
            payment={"prepayment_ratio": 0.0, "balance_period": 30, "day_rule": "自然日", "start_trigger": "入库"}
        )

        result = create_mat_procurement_vc_action(db_session, payload)
        assert result.success is True, f"物料采购创建失败: {result.error}"

        from models import VirtualContract
        vc = db_session.query(VirtualContract).get(result.data["vc_id"])
        assert vc is not None

        assert_vc_elements_structure(vc, VCType.MATERIAL_PROCUREMENT, 1)
        elems = vc.elements
        assert "total_amount" in elems
        assert "payment_terms" in elems
        assert elems["total_amount"] == 500.0

        item = elems["items"][0]
        # 商业逻辑：shipping_point_id=供应商仓库, receiving_point_id=我们仓库
        assert_element_item(item, {
            "shipping_point_id": sup_wh.id,
            "receiving_point_id": our_wh.id,
            "sku_id": sku.id,
            "qty": 100.0,
            "price": 5.0,
            "deposit": 0.0,
            "subtotal": 500.0,
            "sn_list": [],
        })


# ---------------------------------------------------------------------------
# 测试 4：物料供应 VC
# ---------------------------------------------------------------------------

class TestMaterialSupplyElements:
    """物料供应 VC elements 结构验证"""

    def test_elements_structure(self, db_session, base_data):
        """✅ 物料供应 elements 结构"""
        from models import MaterialInventory, Point

        biz = base_data["business"]
        sku = base_data["sku_mat"]

        # 发货仓库（type=自有仓，且名称对应 MaterialInventory.stock_distribution 的 key）
        wh = Point(name="中心仓", type="自有仓")
        db_session.add(wh)
        db_session.flush()

        # 客户运营点位（收货点范围）
        customer_pt = Point(name="测试运营点", type="运营点位", customer_id=biz.customer_id)
        db_session.add(customer_pt)
        db_session.flush()

        # 预置物料库存（stock_distribution 的 key = str(point_id)，与真实系统一致）
        mat_inv = MaterialInventory(
            sku_id=sku.id,
            batch_no="20260315-TEST",
            point_id=wh.id,
            qty=500.0,
            latest_purchase_vc_id=None
        )
        db_session.add(mat_inv)
        db_session.flush()

        payload = CreateMaterialSupplyVCSchema(
            business_id=biz.id,
            elements=[
                VCElementSchema(
                    shipping_point_id=wh.id,  # 必须在有库存的仓库中选择
                    receiving_point_id=customer_pt.id,
                    sku_id=sku.id, qty=200, price=10.0,
                    deposit=0.0, subtotal=2000.0, sn_list=[]
                )
            ],
            total_amt=2000.0,
            description="测试物料供应"
        )

        result = create_material_supply_vc_action(db_session, payload)
        assert result.success is True, f"物料供应创建失败: {result.error}"

        from models import VirtualContract
        vc = db_session.query(VirtualContract).get(result.data["vc_id"])
        assert vc is not None

        assert_vc_elements_structure(vc, VCType.MATERIAL_SUPPLY, 1)
        elems = vc.elements
        assert "total_amount" in elems
        assert "payment_terms" in elems, "物料供应 elements 应包含 payment_terms（状态机需要用于 cash_status 演进）"

        item = elems["items"][0]
        # 商业逻辑：shipping_point_id=有库存的仓库, receiving_point_id=客户运营点位
        assert_element_item(item, {
            "shipping_point_id": wh.id,
            "receiving_point_id": customer_pt.id,
            "sku_id": sku.id,
            "qty": 200.0,
            "price": 10.0,
            "deposit": 0.0,
            "subtotal": 2000.0,
            "sn_list": [],
        })

    def test_elements_structure_multiple_skus(self, db_session, base_data):
        """✅ 物料供应多 SKU elements 结构"""
        from models import MaterialInventory, SKU, Point

        biz = base_data["business"]
        sku1 = base_data["sku_mat"]
        sku2 = SKU(supplier_id=base_data["supplier"].id, name="测试物料B", type_level1="物料")
        db_session.add(sku2)
        db_session.flush()

        # 发货仓库
        wh = Point(name="中心仓", type="自有仓")
        db_session.add(wh)
        db_session.flush()

        # 客户运营点位
        customer_pt = Point(name="测试运营点", type="运营点位", customer_id=biz.customer_id)
        db_session.add(customer_pt)
        db_session.flush()

        # 预置两个物料库存批次
        for sku in [sku1, sku2]:
            mat_inv = MaterialInventory(
                sku_id=sku.id, batch_no="20260420-TEST", point_id=wh.id, qty=500.0
            )
            db_session.add(mat_inv)
        db_session.flush()

        payload = CreateMaterialSupplyVCSchema(
            business_id=biz.id,
            elements=[
                VCElementSchema(
                    shipping_point_id=wh.id, receiving_point_id=customer_pt.id,
                    sku_id=sku1.id, qty=100, price=10.0,
                    deposit=0.0, subtotal=1000.0, sn_list=[]
                ),
                VCElementSchema(
                    shipping_point_id=wh.id, receiving_point_id=customer_pt.id,
                    sku_id=sku2.id, qty=50, price=8.0,
                    deposit=0.0, subtotal=400.0, sn_list=[]
                ),
            ],
            total_amt=1400.0,
            description=""
        )

        result = create_material_supply_vc_action(db_session, payload)
        assert result.success is True, f"物料供应创建失败: {result.error}"

        from models import VirtualContract
        vc = db_session.query(VirtualContract).get(result.data["vc_id"])
        assert_vc_elements_structure(vc, VCType.MATERIAL_SUPPLY, 2)
        elems = vc.elements
        assert elems["total_amount"] == 1400.0
        for item in elems["items"]:
            assert item["shipping_point_id"] == wh.id
            assert item["receiving_point_id"] == customer_pt.id
        assert elems["items"][0]["sku_id"] == sku1.id
        assert elems["items"][1]["sku_id"] == sku2.id


# ---------------------------------------------------------------------------
# 测试 5：退货 VC
# ---------------------------------------------------------------------------

class TestReturnElements:
    """退货 VC elements 结构验证"""

    def test_elements_structure(self, db_session, base_data):
        """✅ 退货 elements 结构（挂钩VC=设备采购，退回给我们）"""
        from models import EquipmentInventory, Point, SupplyChain
        from logic.constants import OperationalStatus, DeviceStatus, ReturnDirection

        biz = base_data["business"]
        sku = base_data["sku_equip"]
        supplier = base_data["supplier"]

        # 创建供应商仓库（发货点）
        sup_wh = Point(name="测试供应商仓", type="供应商仓", supplier_id=supplier.id)
        db_session.add(sup_wh)
        db_session.flush()

        # 创建客户仓库（采购收货点 / 退货收货点）
        cust_wh = Point(name="客户仓库A", type="客户仓", customer_id=biz.customer_id)
        db_session.add(cust_wh)
        db_session.flush()

        # 创建供应链
        sc = SupplyChain(supplier_id=supplier.id, type="设备")
        db_session.add(sc)
        db_session.flush()

        # 创建目标采购 VC（设备采购）
        target_vc_payload = CreateProcurementVCSchema(
            business_id=biz.id,
            sc_id=sc.id,
            elements=[
                VCElementSchema(
                    shipping_point_id=0,
                    receiving_point_id=cust_wh.id,
                    sku_id=sku.id, qty=2, price=1000.0,
                    deposit=100.0, subtotal=2000.0, sn_list=[]
                )
            ],
            total_amt=2000.0,
            total_deposit=200.0,
            payment={"prepayment_ratio": 0.3, "balance_period": 0, "day_rule": "自然日", "start_trigger": "入库"},
            description=""
        )
        result = create_procurement_vc_action(db_session, target_vc_payload)
        assert result.success is True, f"目标采购VC创建失败: {result.error}"
        target_vc_id = result.data["vc_id"]

        # 在客户运营点位上创建设备库存（退货来源）
        # 注意：退货4.1的发货点范围是"有该sku的客户点位"
        cust_op_pt = Point(name="测试运营点", type="运营点位", customer_id=biz.customer_id)
        db_session.add(cust_op_pt)
        db_session.flush()

        eq = EquipmentInventory(
            sku_id=sku.id,
            sn="EQSN001",
            operational_status=OperationalStatus.OPERATING,
            device_status=DeviceStatus.NORMAL,
            virtual_contract_id=target_vc_id,
            point_id=cust_op_pt.id,
            deposit_amount=100.0
        )
        db_session.add(eq)
        db_session.flush()

        # 创建退货 VC（4.1.1：设备采购，退回给我们）
        # shipping_point=客户运营点位(cust_op_pt), receiving_point=我们仓库(DEFAULT_WAREHOUSE_ID)
        return_payload = CreateReturnVCSchema(
            target_vc_id=target_vc_id,
            return_direction=ReturnDirection.CUSTOMER_TO_US,
            elements=[
                VCElementSchema(
                    shipping_point_id=cust_op_pt.id,
                    receiving_point_id=1,
                    sku_id=sku.id, qty=1, price=1000.0,
                    deposit=100.0, subtotal=1000.0, sn_list=["EQSN001"]
                )
            ],
            goods_amount=1000.0,
            deposit_amount=100.0,
            logistics_cost=50.0,
            logistics_bearer="我方",
            total_refund=1050.0,
            reason="设备损坏",
            description=""
        )

        result = create_return_vc_action(db_session, return_payload)
        assert result.success is True, f"退货创建失败: {result.error}"

        from models import VirtualContract
        vc = db_session.query(VirtualContract).get(result.data["vc_id"])
        assert vc is not None

        # 验证 elements 结构
        assert_vc_elements_structure(vc, VCType.RETURN, 1)
        elems = vc.elements

        # 退货 VC 顶层保留相关字段（return_direction 已在 VC 表字段）
        assert vc.return_direction == ReturnDirection.CUSTOMER_TO_US
        assert "return_direction" not in elems
        assert "goods_amount" in elems
        assert elems["goods_amount"] == 1000.0
        assert "deposit_amount" in elems
        assert elems["deposit_amount"] == 100.0
        assert "total_refund" in elems
        assert elems["total_refund"] == 1050.0
        assert "reason" in elems
        assert elems["reason"] == "设备损坏"

        # 不应有 payment_terms
        assert "payment_terms" not in elems

        item = elems["items"][0]
        assert_element_item(item, {
            "shipping_point_id": cust_op_pt.id,
            "receiving_point_id": 1,
            "sku_id": sku.id,
            "qty": 1.0,
            "price": 1000.0,
            "deposit": 100.0,
            "subtotal": 1000.0,
            "sn_list": ["EQSN001"],
        })
        assert item["id"] == f"sp{cust_op_pt.id}_rp1_sku{sku.id}_bn-"

        # related_vc_id 正确关联
        assert vc.related_vc_id == target_vc_id


# ---------------------------------------------------------------------------
# 测试 6：库存拨付 VC
# ---------------------------------------------------------------------------

class TestInventoryAllocationElements:
    """库存拨付 VC elements 结构验证"""

    def test_elements_structure(self, db_session, base_data):
        """✅ 库存拨付 elements 结构"""
        from models import Business, EquipmentInventory, Point
        from logic.constants import OperationalStatus, DeviceStatus

        biz = base_data["business"]

        # 创建目标点位（接收方）
        target_point = Point(name="拨入运营点", type="运营点位", customer_id=biz.customer_id)
        db_session.add(target_point)
        db_session.flush()

        # 创建两个库存设备（在总仓库 point_id=1）
        eq1 = EquipmentInventory(
            sku_id=base_data["sku_equip"].id, sn="EQSN001",
            operational_status=OperationalStatus.STOCK,
            device_status=DeviceStatus.NORMAL,
            point_id=1, deposit_amount=0.0
        )
        eq2 = EquipmentInventory(
            sku_id=base_data["sku_equip"].id, sn="EQSN002",
            operational_status=OperationalStatus.STOCK,
            device_status=DeviceStatus.NORMAL,
            point_id=1, deposit_amount=0.0
        )
        db_session.add_all([eq1, eq2])
        db_session.flush()

        payload = AllocateInventorySchema(
            business_id=biz.id,
            elements=[
                VCElementSchema(
                    shipping_point_id=1, receiving_point_id=target_point.id,
                    sku_id=base_data["sku_equip"].id,
                    qty=2, price=0.0,
                    deposit=0.0, subtotal=0.0,
                    sn_list=[eq1.sn, eq2.sn]
                )
            ],
            description="测试库存拨付"
        )

        result = create_inventory_allocation_action(db_session, payload)
        assert result.success is True, f"库存拨付创建失败: {result.error}"

        from models import VirtualContract
        vc = db_session.query(VirtualContract).get(result.data["vc_id"])
        assert vc is not None

        # 验证 elements 结构
        assert_vc_elements_structure(vc, VCType.INVENTORY_ALLOCATION, 1)
        elems = vc.elements
        assert "total_amount" in elems
        assert elems["total_amount"] == 0.0
        assert "payment_terms" not in elems
        assert "return_direction" not in elems

        item = elems["items"][0]
        assert_element_item(item, {
            "shipping_point_id": 1,
            "receiving_point_id": target_point.id,
            "sku_id": base_data["sku_equip"].id,
            "qty": 2.0,
            "price": 0.0,
            "deposit": 0.0,
            "subtotal": 0.0,
            "sn_list": [eq1.sn, eq2.sn],
        })
        assert item["id"] == f"sp1_rp{target_point.id}_sku{base_data['sku_equip'].id}_bn-"

        # 库存拨付：subject_status 和 cash_status 直接 FINISH
        assert vc.subject_status == SubjectStatus.FINISH
        assert vc.cash_status == CashStatus.FINISH

        # 设备状态已更新
        db_session.refresh(eq1)
        db_session.refresh(eq2)
        assert eq1.operational_status == OperationalStatus.OPERATING
        assert eq1.point_id == target_point.id
        assert eq1.virtual_contract_id == vc.id


# ---------------------------------------------------------------------------
# 测试 7：通用断言——验证 elements 中无冗余字段
# ---------------------------------------------------------------------------

class TestElementsNoRedundancy:
    """验证 elements 结构无旧结构残留"""

    def test_no_skus_key(self, db_session, base_data):
        """✅ 新结构 elements 不含 skus 键"""
        from models import Point, SupplyChain

        biz = base_data["business"]
        sku = base_data["sku_equip"]
        supplier = base_data["supplier"]

        # 供应商仓库 + 客户仓库
        sup_wh = Point(name="测试供应商仓", type="供应商仓", supplier_id=supplier.id)
        db_session.add(sup_wh)
        db_session.flush()
        cust_wh = Point(name="客户仓库A", type="客户仓", customer_id=biz.customer_id)
        db_session.add(cust_wh)
        db_session.flush()
        sc = SupplyChain(supplier_id=supplier.id, type="设备")
        db_session.add(sc)
        db_session.flush()

        payload = CreateProcurementVCSchema(
            business_id=biz.id, sc_id=sc.id,
            elements=[
                VCElementSchema(
                    shipping_point_id=0, receiving_point_id=cust_wh.id,
                    sku_id=sku.id, qty=1, price=100.0,
                    deposit=0.0, subtotal=100.0, sn_list=[]
                )
            ],
            total_amt=100.0, total_deposit=0.0,
            payment={"prepayment_ratio": 0.0, "balance_period": 0, "day_rule": "自然日", "start_trigger": "入库"},
            description=""
        )
        result = create_procurement_vc_action(db_session, payload)
        assert result.success is True, f"创建失败: {result.error}"

        from models import VirtualContract
        vc = db_session.query(VirtualContract).get(result.data["vc_id"])
        elems = vc.elements

        assert "skus" not in elems
        assert "points" not in elems
        assert "return_items" not in elems
        assert "allocation_items" not in elems
        assert "vc_type" not in elems
        assert "items" in elems

    def test_id_field_consistency(self, db_session, base_data):
        """✅ id 字段与实际 (sp, rp, sku) 一致"""
        from models import Point, SupplyChain

        biz = base_data["business"]
        sku = base_data["sku_equip"]
        supplier = base_data["supplier"]

        # 供应商仓库 + 客户仓库
        sup_wh = Point(name="测试供应商仓", type="供应商仓", supplier_id=supplier.id)
        db_session.add(sup_wh)
        db_session.flush()
        cust_wh = Point(name="客户仓库A", type="客户仓", customer_id=biz.customer_id)
        db_session.add(cust_wh)
        db_session.flush()
        sc = SupplyChain(supplier_id=supplier.id, type="设备")
        db_session.add(sc)
        db_session.flush()

        # 传入客户仓库作为收货点（会被校验通过），发货点由供应链决定
        payload = CreateProcurementVCSchema(
            business_id=biz.id, sc_id=sc.id,
            elements=[
                VCElementSchema(
                    shipping_point_id=0, receiving_point_id=cust_wh.id,
                    sku_id=sku.id, qty=3, price=500.0,
                    deposit=50.0, subtotal=1500.0, sn_list=[]
                )
            ],
            total_amt=1500.0, total_deposit=150.0,
            payment={"prepayment_ratio": 0.3, "balance_period": 0, "day_rule": "自然日", "start_trigger": "入库"},
            description=""
        )
        result = create_procurement_vc_action(db_session, payload)
        assert result.success is True

        from models import VirtualContract
        vc = db_session.query(VirtualContract).get(result.data["vc_id"])
        item = vc.elements["items"][0]

        # 商业逻辑：shipping_point_id=供应商仓库, receiving_point_id=客户仓库
        assert item["shipping_point_id"] == sup_wh.id
        assert item["receiving_point_id"] == cust_wh.id
        assert item["sku_id"] == sku.id
        assert item["id"] == f"sp{sup_wh.id}_rp{cust_wh.id}_sku{sku.id}_bn-"
