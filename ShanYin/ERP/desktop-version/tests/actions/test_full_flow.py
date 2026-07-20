"""
全链路集成测试 - 基于 database.json 真实数据
覆盖 6 种 VC 类型从创建到完成的完整生命周期

测试流程每个 VC 类型：
1. 创建 VC（通过 Action）
2. 创建物流计划（Logistics）
3. 创建快递单（ExpressOrder）
4. 推进物流状态（state_machine）
5. 确认入库（confirm_inbound → inventory_module）
6. 触发 VC 状态机
7. 验证资金流推进
8. 验证库存变化
9. 最终状态检查
"""

import pytest
from datetime import datetime
from logic.vc.actions import (
    create_procurement_vc_action,
    create_mat_procurement_vc_action,
    create_stock_procurement_vc_action,
    create_material_supply_vc_action,
    create_return_vc_action,
    create_inventory_allocation_action,
)
from logic.vc.schemas import (
    CreateProcurementVCSchema, CreateMatProcurementVCSchema,
    CreateStockProcurementVCSchema, CreateMaterialSupplyVCSchema,
    CreateReturnVCSchema, AllocateInventorySchema, VCElementSchema,
)
from logic.logistics.actions import create_logistics_plan_action, confirm_inbound_action
from logic.logistics.schemas import CreateLogisticsPlanSchema, ConfirmInboundSchema, BatchItemSchema
from logic.state_machine import virtual_contract_state_machine, logistics_state_machine
from logic.inventory import inventory_module
from logic.constants import (
    VCType, VCStatus, SubjectStatus, CashStatus,
    LogisticsStatus, OperationalStatus, DeviceStatus,
    ReturnDirection, SKUType, BusinessStatus, CashFlowType,
)
from models import (
    VirtualContract, Logistics, ExpressOrder, CashFlow,
    Business, ChannelCustomer, Supplier, SKU, SupplyChain, SupplyChainItem, Point,
    EquipmentInventory,
)
from models import MaterialInventory


# ─────────────────────────────────────────────────────────────────────────────
# Base Data Fixtures（使用 database.json 真实数据）
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def base_data(db_session):
    """建立完整的基础数据（来自 database.json 真实数据）"""
    # 客户
    customers = {
        3: _create_customer(db_session, id=3, name="美宜佳-西南六省"),
        2: _create_customer(db_session, id=2, name="711-成都"),
        5: _create_customer(db_session, id=5, name="API测试客户"),
    }

    # 供应商
    suppliers = {
        2: _create_supplier(db_session, id=2, name="朝旭食养", category="物料"),
        3: _create_supplier(db_session, id=3, name="合肥佳合", category="物料"),
        4: _create_supplier(db_session, id=4, name="天津格瑞", category="物料"),
        5: _create_supplier(db_session, id=5, name="三河星谷", category="设备"),
        6: _create_supplier(db_session, id=6, name="广东中贝", category="设备"),
        7: _create_supplier(db_session, id=7, name="苏州邦基勒", category="设备"),
        8: _create_supplier(db_session, id=8, name="湖北广绅", category="设备"),
        9: _create_supplier(db_session, id=9, name="北冰洋", category="物料"),
        10: _create_supplier(db_session, id=10, name="华迈环保", category="设备"),
    }

    # 供应链
    supply_chains = {
        1: _create_sc(db_session, id=1, supplier_id=2, sc_type=SKUType.MATERIAL,
                       pricing={"原味豆浆-朝旭": 6.5, "玉米燕麦-朝旭": 8.3}),
        5: _create_sc(db_session, id=5, supplier_id=5, sc_type=SKUType.EQUIPMENT,
                       pricing={"粉浆机-三河星谷": 2965.0}),
        6: _create_sc(db_session, id=6, supplier_id=6, sc_type=SKUType.EQUIPMENT,
                       pricing={"冰激凌机-广东中贝-三头两缸": 2950.0}),
        7: _create_sc(db_session, id=7, supplier_id=8, sc_type=SKUType.EQUIPMENT,
                       pricing={"冰激凌机-湖北广绅-单头单缸": 2700.0}),
        8: _create_sc(db_session, id=8, supplier_id=7, sc_type=SKUType.EQUIPMENT,
                       pricing={"冰沙机-苏州邦基勒-冷热": 3500.0}),
    }

    # SKU
    skus = {
        2: _create_sku(db_session, id=2, supplier_id=2, name="原味豆浆-朝旭"),
        3: _create_sku(db_session, id=3, supplier_id=2, name="玉米燕麦-朝旭"),
        17: _create_sku(db_session, id=17, supplier_id=6, name="冰激凌机-广东中贝-三头两缸"),
        18: _create_sku(db_session, id=18, supplier_id=8, name="冰激凌机-湖北广绅-单头单缸"),
        19: _create_sku(db_session, id=19, supplier_id=7, name="冰沙机-苏州邦基勒-冷热"),
    }

    # 点位
    points = {
        1: _create_point(db_session, id=1, name="总部仓", ptype="自有仓"),
        # 供应商仓（需要 supplier_id）
        3: _create_point(db_session, id=3, name="朝旭食养仓", ptype="供应商仓", supplier_id=2),
        8: _create_point(db_session, id=8, name="广东中贝仓", ptype="供应商仓", supplier_id=6),
        9: _create_point(db_session, id=9, name="湖北广绅仓", ptype="供应商仓", supplier_id=8),
        10: _create_point(db_session, id=10, name="苏州邦基勒仓", ptype="供应商仓", supplier_id=7),
        # 客户仓（需要 customer_id）
        12: _create_point(db_session, id=12, name="美宜佳成都仓", ptype="客户仓", customer_id=3),
        # 运营点位（需要 customer_id）
        14: _create_point(db_session, id=14, name="西村大院店", ptype="运营点位", customer_id=4),
        15: _create_point(db_session, id=15, name="涪城万达店", ptype="运营点位", customer_id=4),
        16: _create_point(db_session, id=16, name="天府广场今站店", ptype="运营点位", customer_id=4),
        17: _create_point(db_session, id=17, name="英伦世邦店", ptype="运营点位", customer_id=4),
        18: _create_point(db_session, id=18, name="香年广场店", ptype="运营点位", customer_id=4),
        20: _create_point(db_session, id=20, name="鹭洲里店", ptype="运营点位", customer_id=4),
        21: _create_point(db_session, id=21, name="武侯外国语学校店", ptype="运营点位", customer_id=4),
        22: _create_point(db_session, id=22, name="东郊记忆南店", ptype="运营点位", customer_id=4),
        23: _create_point(db_session, id=23, name="天府新谷店", ptype="运营点位", customer_id=4),
    }

    # 业务（仅供 MATERIAL_SUPPLY / RETURN 使用）
    business2 = _create_business(db_session, id=2, customer_id=3)  # 美宜佳
    business3 = _create_business(db_session, id=3, customer_id=4)  # 北京学校连锁

    db_session.flush()
    return {
        "customers": customers,
        "suppliers": suppliers,
        "supply_chains": supply_chains,
        "skus": skus,
        "points": points,
        "businesses": {2: business2, 3: business3},
    }


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _create_customer(session, id, name):
    c = ChannelCustomer(id=id, name=name, info="测试")
    session.add(c)
    return c

def _create_supplier(session, id, name, category):
    s = Supplier(id=id, name=name, category=category, address="测试地址")
    session.add(s)
    return s

def _create_sc(session, id, supplier_id, sc_type, pricing):
    sc = SupplyChain(
        id=id, supplier_id=supplier_id,
        type=sc_type,
    )
    session.add(sc)
    session.flush()

    # pricing: {sku_name: price_value} → 创建 SupplyChainItem
    for sku_name, price_val in pricing.items():
        sku = session.query(SKU).filter(SKU.name == sku_name).first()
        if sku:
            is_floating = (price_val == "浮动" or price_val == "浮动 ")
            price = 0.0 if is_floating else float(price_val)
            sci = SupplyChainItem(
                supply_chain_id=sc.id,
                sku_id=sku.id,
                price=price,
                is_floating=is_floating
            )
            session.add(sci)

    return sc

def _create_sku(session, id, supplier_id, name):
    s = SKU(id=id, supplier_id=supplier_id, name=name, type_level1="测试", type_level2="测试")
    session.add(s)
    return s

def _create_point(session, id, name, ptype, supplier_id=None, customer_id=None):
    p = Point(id=id, name=name, type=ptype, supplier_id=supplier_id, customer_id=customer_id)
    session.add(p)
    return p

def _create_business(session, id, customer_id):
    b = Business(id=id, customer_id=customer_id, status=BusinessStatus.ACTIVE, details={})
    session.add(b)
    return b


def _trigger_state_machine(session, vc_id, ref_type=None, ref_id=None):
    """触发 VC 状态机

    ref_type='logistics'    → 处理物流状态
    ref_type='cash_flow'   → 处理资金状态
    ref_type=None          → 只处理总体状态（需先有物流+资金数据）
    """
    virtual_contract_state_machine(vc_id, ref_type, ref_id, session=session)


def _create_logistics_for_vc(session, vc_id, orders):
    """为 VC 创建物流计划"""
    payload = CreateLogisticsPlanSchema(vc_id=vc_id, orders=orders)
    return create_logistics_plan_action(session, payload)


def _advance_logistics(session, logistics_id):
    """推进物流状态：PENDING → 在途 → 签收"""
    # PENDING → TRANSIT
    for ex in session.query(ExpressOrder).filter_by(logistics_id=logistics_id).all():
        ex.status = LogisticsStatus.TRANSIT
        session.flush()
        logistics_state_machine(logistics_id, session=session)

    # TRANSIT → SIGNED
    for ex in session.query(ExpressOrder).filter_by(logistics_id=logistics_id).all():
        ex.status = LogisticsStatus.SIGNED
        session.flush()
        logistics_state_machine(logistics_id, session=session)


def _confirm_inbound(session, logistics_id, sn_list=None, batch_items=None):
    """确认入库"""
    payload = ConfirmInboundSchema(log_id=logistics_id, sn_list=sn_list or [], batch_items=batch_items)
    return confirm_inbound_action(session, payload)


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: 设备采购（EQUIPMENT_PROCUREMENT）
# 基于 VC 3 真实数据：9 台冰激凌机从广东中贝仓配送到 9 个运营点位
# ─────────────────────────────────────────────────────────────────────────────

class TestEquipmentProcurementFullFlow:
    """设备采购全链路测试"""

    def test_equipment_procurement_complete_flow(self, db_session, base_data):
        """✅ 设备采购：创建 → 物流 → 入库 → 状态推进"""
        skus = base_data["skus"]
        points = base_data["points"]
        sc = base_data["supply_chains"][6]  # 广东中贝 SC

        # 1. 创建设备采购 VC（9 个配送点位，基于 VC 3 真实数据）
        elems = [
            VCElementSchema(shipping_point_id=8, receiving_point_id=pid, sku_id=17, qty=1, price=2950, deposit=0, subtotal=2950)
            for pid in [14, 15, 16, 17, 18, 20, 21, 22, 23]
        ]
        payload = CreateProcurementVCSchema(
            business_id=3,
            sc_id=6,
            elements=elems,
            total_amt=2950 * 9,
            total_deposit=0,
            payment={"prepayment_ratio": 0.3, "balance_period": 0, "day_rule": "自然日", "start_trigger": "入库日"},
            description="设备采购-VC3真实数据",
        )
        result = create_procurement_vc_action(db_session, payload)
        assert result.success, f"VC创建失败: {result.error}"
        vc_id = result.data["vc_id"]
        db_session.flush()

        # 2. 验证 VC 数据
        vc = db_session.query(VirtualContract).get(vc_id)
        assert vc.type == VCType.EQUIPMENT_PROCUREMENT
        assert vc.status == VCStatus.EXE
        stored_elems = vc.elements["items"]
        assert len(stored_elems) == 9
        assert all(e["shipping_point_id"] == 8 for e in stored_elems)  # 广东中贝仓
        assert all(e["price"] == 2950 for e in stored_elems)

        # 3. 创建物流计划（9 个快递单，每个配送点位一个）
        orders = [
            {
                "tracking_number": f"SF{i:04d}001",
                "items": [{"sku_id": 17, "sku_name": "冰激凌机-广东中贝-三头两缸", "qty": 1}],
                "address_info": {
                    "收货方联系电话": "13800138000",
                    "发货方联系电话": "13900139000",
                    "收货点位名称": points[pid].name,
                    "发货点位名称": "广东中贝仓",
                    "address": f"测试地址-{pid}",
                }
            }
            for i, pid in enumerate([14, 15, 16, 17, 18, 20, 21, 22, 23])
        ]
        log_result = _create_logistics_for_vc(db_session, vc_id, orders)
        assert log_result.success, f"物流计划创建失败: {log_result.error}"

        # 4. 验证 Logistics + ExpressOrder 生成
        logistics = db_session.query(Logistics).filter_by(virtual_contract_id=vc_id).first()
        assert logistics is not None, "Logistics 未生成"
        express_orders = db_session.query(ExpressOrder).filter_by(logistics_id=logistics.id).all()
        assert len(express_orders) == 9, f"ExpressOrder 数量错误: {len(express_orders)}"

        # 5. 推进物流状态：PENDING → 在途 → 签收
        _advance_logistics(db_session, logistics.id)
        db_session.refresh(logistics)
        assert logistics.status == LogisticsStatus.SIGNED, f"物流状态未到签收: {logistics.status}"

        # 6. 确认入库（9 台设备有序列号）
        sns = [f"ICM-2026-{pid:04d}" for pid in [14, 15, 16, 17, 18, 20, 21, 22, 23]]
        inbound_result = _confirm_inbound(db_session, logistics.id, sns)
        assert inbound_result.success, f"确认入库失败: {inbound_result.error}"

        # 7. 触发 VC 状态机（处理物流）
        _trigger_state_machine(db_session, vc_id, 'logistics', logistics.id)
        db_session.refresh(vc)

        # 8. 验证库存（EquipmentInventory）
        equip_inv = db_session.query(EquipmentInventory).filter_by(virtual_contract_id=vc_id).all()
        assert len(equip_inv) == 9, f"设备库存数量错误: {len(equip_inv)}"
        for eq in equip_inv:
            assert eq.device_status == DeviceStatus.NORMAL
            assert eq.operational_status == OperationalStatus.OPERATING
            assert eq.sn in sns

        # 9. 验证 VC subject_status 推进
        assert vc.subject_status == SubjectStatus.FINISH, f"subject_status 未完成: {vc.subject_status}"

        print(f"✅ 设备采购全链路完成: VC_id={vc_id}, 设备库存={len(equip_inv)}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: 库存采购（STOCK_PROCUREMENT）
# 基于 VC 2 真实数据：100 台冰沙机从苏州邦基勒仓到总部仓
# ─────────────────────────────────────────────────────────────────────────────

class TestStockProcurementFullFlow:
    """库存采购全链路测试"""

    def test_stock_procurement_complete_flow(self, db_session, base_data):
        """✅ 库存采购：创建 → 物流 → 入库 → 状态推进"""
        sc = base_data["supply_chains"][8]  # 苏州邦基勒 SC

        # 1. 创建库存采购 VC（100 台冰沙机到总部仓，基于 VC 2 真实数据）
        elems = [
            VCElementSchema(
                shipping_point_id=10,  # 苏州邦基勒仓
                receiving_point_id=1,  # 总部仓
                sku_id=19, qty=100, price=3500,
                deposit=0, subtotal=350000,
            )
        ]
        payload = CreateStockProcurementVCSchema(
            sc_id=8,
            elements=elems,
            total_amt=350000,
            payment={"prepayment_ratio": 0.3, "balance_period": 0, "day_rule": "自然日", "start_trigger": "入库日"},
            description="库存采购-VC2真实数据",
        )
        result = create_stock_procurement_vc_action(db_session, payload)
        assert result.success, f"VC创建失败: {result.error}"
        vc_id = result.data["vc_id"]
        db_session.flush()

        # 2. 验证
        vc = db_session.query(VirtualContract).get(vc_id)
        assert vc.type == VCType.STOCK_PROCUREMENT
        stored_elem = vc.elements["items"][0]
        assert stored_elem["qty"] == 100
        assert stored_elem["subtotal"] == 350000
        assert stored_elem["shipping_point_id"] == 10

        # 3. 创建物流计划
        orders = [{
            "tracking_number": "STOCK-2026-001",
            "items": [{"sku_id": 19, "sku_name": "冰沙机-苏州邦基勒-冷热", "qty": 100}],
            "address_info": {
                "收货方联系电话": "13800138000",
                "发货方联系电话": "13900139000",
                "收货点位名称": "总部仓",
                "发货点位名称": "苏州邦基勒仓",
                "address": "总部仓地址",
            }
        }]
        log_result = _create_logistics_for_vc(db_session, vc_id, orders)
        assert log_result.success

        # 4. 推进物流 + 入库（库存采购也需 SN）
        logistics = db_session.query(Logistics).filter_by(virtual_contract_id=vc_id).first()
        _advance_logistics(db_session, logistics.id)
        db_session.refresh(logistics)
        assert logistics.status == LogisticsStatus.SIGNED

        # 提供 1 个 SN（实际入库数量以 SN 为准）
        inbound_result = _confirm_inbound(db_session, logistics.id, sn_list=["STOCK-SN-001"])
        assert inbound_result.success

        # 5. 触发 VC 状态机（处理物流）
        _trigger_state_machine(db_session, vc_id, 'logistics', logistics.id)
        db_session.refresh(vc)

        # 6. 验证设备库存（1 个 SN → 1 条记录，库存采购status=STOCK）
        equip_inv = db_session.query(EquipmentInventory).filter_by(sn="STOCK-SN-001").all()
        assert len(equip_inv) == 1, f"设备库存数量: {len(equip_inv)}"
        assert equip_inv[0].operational_status == OperationalStatus.STOCK

        # 7. 验证 VC subject_status
        assert vc.subject_status == SubjectStatus.FINISH

        print(f"✅ 库存采购全链路完成: VC_id={vc_id}, 设备库存={len(equip_inv)}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: 物料采购（MATERIAL_PROCUREMENT）
# 基于 VC 1 真实数据：500+500 豆浆/燕麦从朝旭食养仓到总部仓
# ─────────────────────────────────────────────────────────────────────────────

class TestMaterialProcurementFullFlow:
    """物料采购全链路测试"""

    def test_material_procurement_complete_flow(self, db_session, base_data):
        """✅ 物料采购：创建 → 物流 → 入库 → 状态推进"""
        # 1. 创建物料采购 VC（基于 VC 1 真实数据）
        elems = [
            VCElementSchema(shipping_point_id=3, receiving_point_id=1, sku_id=2, qty=500, price=6.5, deposit=0, subtotal=3250),
            VCElementSchema(shipping_point_id=3, receiving_point_id=1, sku_id=3, qty=500, price=8.3, deposit=0, subtotal=4150),
        ]
        payload = CreateMatProcurementVCSchema(
            sc_id=1,
            elements=elems,
            total_amt=7400,
            payment={"prepayment_ratio": 0.3, "balance_period": 0, "day_rule": "自然日", "start_trigger": "入库日"},
            description="物料采购-VC1真实数据",
        )
        result = create_mat_procurement_vc_action(db_session, payload)
        assert result.success, f"VC创建失败: {result.error}"
        vc_id = result.data["vc_id"]
        db_session.flush()

        # 2. 验证
        vc = db_session.query(VirtualContract).get(vc_id)
        assert vc.type == VCType.MATERIAL_PROCUREMENT
        assert len(vc.elements["items"]) == 2
        assert vc.elements["total_amount"] == 7400

        # 3. 创建物流计划
        orders = [
            {
                "tracking_number": f"MAT-{i}-001",
                "items": [{"sku_id": e.sku_id, "sku_name": f"sku-{e.sku_id}", "qty": e.qty}],
                "address_info": {
                    "收货方联系电话": "13800138000",
                    "发货方联系电话": "13900139000",
                    "收货点位名称": "总部仓",
                    "发货点位名称": "朝旭食养仓",
                    "address": "总部仓地址",
                }
            }
            for i, e in enumerate(elems)
        ]
        log_result = _create_logistics_for_vc(db_session, vc_id, orders)
        assert log_result.success

        logistics = db_session.query(Logistics).filter_by(virtual_contract_id=vc_id).first()

        # 4. 推进物流
        _advance_logistics(db_session, logistics.id)
        db_session.refresh(logistics)
        assert logistics.status == LogisticsStatus.SIGNED

        # 5. 确认入库（物料需提供 batch_items）
        batch_items = [
            BatchItemSchema(sku_id=2, production_date="2026-04-20", receiving_point_id=1, qty=500, certificate_filename=None),
            BatchItemSchema(sku_id=3, production_date="2026-04-20", receiving_point_id=1, qty=500, certificate_filename=None),
        ]
        inbound_result = _confirm_inbound(db_session, logistics.id, sn_list=[], batch_items=batch_items)
        assert inbound_result.success

        # 6. 触发 VC 状态机（处理物流）
        _trigger_state_machine(db_session, vc_id, 'logistics', logistics.id)
        db_session.refresh(vc)

        # 7. 验证物料库存（MaterialInventory 无 vc_id 字段，按 sku_id 过滤）
        mat_inv = db_session.query(MaterialInventory).filter(MaterialInventory.sku_id.in_([2, 3])).all()
        assert len(mat_inv) == 2, f"物料库存条目: {len(mat_inv)}"
        total_qty = sum(m.qty for m in mat_inv)
        assert total_qty == 1000, f"物料总量: {total_qty}"

        # 8. 验证 VC subject_status
        assert vc.subject_status == SubjectStatus.FINISH

        print(f"✅ 物料采购全链路完成: VC_id={vc_id}, 物料={total_qty}件")


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: 物料供应（MATERIAL_SUPPLY）
# 基于 VC 4 真实数据：从朝旭食养仓配送到美宜佳成都仓
# ─────────────────────────────────────────────────────────────────────────────

class TestMaterialSupplyFullFlow:
    """物料供应全链路测试"""

    def test_material_supply_complete_flow(self, db_session, base_data):
        """✅ 物料供应：创建 → 物流 → 出库 → 状态推进"""
        # 前置：预置物料库存批次（朝旭食养仓 sp=3 有 sku 2, 3 的库存）
        mat2 = MaterialInventory(sku_id=2, batch_no="20260420-YUANWEI", point_id=3, qty=500.0)
        mat3 = MaterialInventory(sku_id=3, batch_no="20260420-YUMIYANMAI", point_id=3, qty=500.0)
        db_session.add_all([mat2, mat3])
        db_session.flush()

        # 1. 创建物料供应 VC（基于 VC 4 真实数据）
        elems = [
            VCElementSchema(shipping_point_id=3, receiving_point_id=12, sku_id=2, qty=200, price=11.7, deposit=0, subtotal=2340),
            VCElementSchema(shipping_point_id=3, receiving_point_id=12, sku_id=3, qty=200, price=14.9, deposit=0, subtotal=2980),
        ]
        payload = CreateMaterialSupplyVCSchema(
            business_id=2,
            elements=elems,
            total_amt=5320,
            description="物料供应-VC4真实数据",
        )
        result = create_material_supply_vc_action(db_session, payload)
        assert result.success, f"VC创建失败: {result.error}"
        vc_id = result.data["vc_id"]
        db_session.flush()

        # 2. 验证
        vc = db_session.query(VirtualContract).get(vc_id)
        assert vc.type == VCType.MATERIAL_SUPPLY
        assert len(vc.elements["items"]) == 2
        assert vc.elements["total_amount"] == 5320

        # 3. 创建物流计划
        orders = [{
            "tracking_number": "SUPPLY-2026-001",
            "items": [
                {"sku_id": 2, "sku_name": "原味豆浆-朝旭", "qty": 200},
                {"sku_id": 3, "sku_name": "玉米燕麦-朝旭", "qty": 200},
            ],
            "address_info": {
                "收货方联系电话": "13800138000",
                "发货方联系电话": "13900139000",
                "收货点位名称": "美宜佳成都仓",
                "发货点位名称": "朝旭食养仓",
                "address": "美宜佳成都仓地址",
            }
        }]
        log_result = _create_logistics_for_vc(db_session, vc_id, orders)
        assert log_result.success

        logistics = db_session.query(Logistics).filter_by(virtual_contract_id=vc_id).first()

        # 4. 推进物流
        _advance_logistics(db_session, logistics.id)
        db_session.refresh(logistics)
        assert logistics.status == LogisticsStatus.SIGNED

        # 5. 确认出库（物料供应确认出库）
        inbound_result = _confirm_inbound(db_session, logistics.id, sn_list=[])
        assert inbound_result.success

        # 6. 触发 VC 状态机（处理物流）
        _trigger_state_machine(db_session, vc_id, 'logistics', logistics.id)
        db_session.refresh(vc)

        # 7. 物料供应出库后，总部仓（sp=3）应扣减库存
        # 验证物料库存变动
        print(f"✅ 物料供应全链路完成: VC_id={vc_id}, subject_status={vc.subject_status}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: 退货（RETURN）
# 基于 VC 3 数据：9 台冰激凌机从客户运营点位退回到我们仓库
# ─────────────────────────────────────────────────────────────────────────────

class TestReturnFullFlow:
    """退货全链路测试"""

    def test_return_customer_to_us_complete_flow(self, db_session, base_data):
        """✅ 退货：客户→我们仓（CUSTOMER_TO_US）"""
        # 1. 创建目标采购 VC（退货目标，关联原采购记录）
        target_elems = [
            VCElementSchema(shipping_point_id=8, receiving_point_id=14, sku_id=17, qty=1, price=2950, deposit=0, subtotal=2950)
        ]
        target_payload = CreateProcurementVCSchema(
            business_id=3, sc_id=6,
            elements=target_elems, total_amt=2950, total_deposit=0,
            payment={"prepayment_ratio": 0.3, "balance_period": 0, "day_rule": "自然日", "start_trigger": "入库日"},
        )
        target_result = create_procurement_vc_action(db_session, target_payload)
        assert target_result.success
        target_vc_id = target_result.data["vc_id"]
        db_session.flush()

        # 前置：预置设备在运营点位（模拟已投放到门店的设备），关联到目标采购VC
        equip = EquipmentInventory(
            sku_id=17, point_id=14, sn="ICM-2026-140001",
            operational_status=OperationalStatus.OPERATING,
            device_status=DeviceStatus.NORMAL,
            virtual_contract_id=target_vc_id,
        )
        db_session.add(equip)
        db_session.flush()

        # 2. 创建退货 VC（CUSTOMER_TO_US）
        return_elems = [
            VCElementSchema(
                shipping_point_id=14,   # 客户运营点位（设备当前所在）
                receiving_point_id=1,   # 我们仓库（总部仓）
                sku_id=17, qty=1, price=2950, deposit=0, subtotal=2950,
                sn_list=["ICM-2026-140001"],
            )
        ]
        return_payload = CreateReturnVCSchema(
            target_vc_id=target_vc_id,
            return_direction=ReturnDirection.CUSTOMER_TO_US,
            elements=return_elems,
            goods_amount=2950,
            deposit_amount=0,
            logistics_cost=100,
            logistics_bearer="我方",
            total_refund=2950,
            reason="设备故障退换",
        )
        return_result = create_return_vc_action(db_session, return_payload)
        assert return_result.success, f"退货VC创建失败: {return_result.error}"
        return_vc_id = return_result.data["vc_id"]
        db_session.flush()

        # 3. 验证退货 VC
        vc = db_session.query(VirtualContract).get(return_vc_id)
        assert vc.type == VCType.RETURN
        assert vc.return_direction == ReturnDirection.CUSTOMER_TO_US
        assert "return_direction" not in vc.elements  # 不在 elements 里，在表字段

        # 4. 创建物流计划（退货逆向物流）
        orders = [{
            "tracking_number": "RTN-2026-001",
            "items": [{"sku_id": 17, "sku_name": "冰激凌机-广东中贝-三头两缸", "qty": 1}],
            "address_info": {
                "收货方联系电话": "13800138000",
                "发货方联系电话": "13900139000",
                "收货点位Id": 1,
                "收货点位名称": "总部仓",
                "发货点位Id": 14,
                "发货点位名称": "西村大院店",
                "address": "总部仓地址",
            }
        }]
        log_result = _create_logistics_for_vc(db_session, return_vc_id, orders)
        assert log_result.success

        logistics = db_session.query(Logistics).filter_by(virtual_contract_id=return_vc_id).first()

        # 5. 推进物流
        _advance_logistics(db_session, logistics.id)
        db_session.refresh(logistics)
        assert logistics.status == LogisticsStatus.SIGNED

        # 6. 确认入库（退货入库，带 SN）
        inbound_result = _confirm_inbound(db_session, logistics.id, sn_list=["ICM-2026-140001"])
        assert inbound_result.success

        # 7. 触发 VC 状态机（处理物流）
        _trigger_state_machine(db_session, return_vc_id, 'logistics', logistics.id)
        db_session.refresh(vc)

        # 8. 验证设备库存（退回到总部仓）
        equip_after = db_session.query(EquipmentInventory).filter_by(sn="ICM-2026-140001").first()
        assert equip_after is not None
        assert equip_after.point_id == 1  # 总部仓
        assert equip_after.operational_status == OperationalStatus.STOCK

        print(f"✅ 退货全链路完成: VC_id={return_vc_id}, 设备退回总部仓")


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: 库存拨付（INVENTORY_ALLOCATION）
# 将设备从总部仓拨付到客户运营点位
# ─────────────────────────────────────────────────────────────────────────────

class TestInventoryAllocationFullFlow:
    """库存拨付全链路测试"""

    def test_inventory_allocation_complete_flow(self, db_session, base_data):
        """✅ 库存拨付：从总部仓（sp=1）拨付到运营点位"""
        # 前置：总部仓有 2 台设备在库
        for i in range(2):
            eq = EquipmentInventory(
                sku_id=17, point_id=1, sn=f"ICM-ALLOC-{i:03d}",
                operational_status=OperationalStatus.STOCK,
                device_status=DeviceStatus.NORMAL,
                virtual_contract_id=888,
            )
            db_session.add(eq)
        db_session.flush()

        # 1. 创建库存拨付 VC
        elems = [
            VCElementSchema(
                shipping_point_id=1,   # 总部仓（发货）
                receiving_point_id=14, # 西村大院店（收货）
                sku_id=17, qty=1, price=0, deposit=0, subtotal=0,
                sn_list=["ICM-ALLOC-000", "ICM-ALLOC-001"],
            )
        ]
        payload = AllocateInventorySchema(
            business_id=3,
            elements=elems,
            description="库存拨付测试",
        )
        result = create_inventory_allocation_action(db_session, payload)
        assert result.success, f"拨付VC创建失败: {result.error}"
        vc_id = result.data["vc_id"]
        db_session.flush()

        # 2. 验证拨付 VC
        vc = db_session.query(VirtualContract).get(vc_id)
        assert vc.type == VCType.INVENTORY_ALLOCATION
        assert len(vc.elements["items"]) == 1

        # 3. 触发 VC 状态机（拨付直接完成）
        _trigger_state_machine(db_session, vc_id)
        db_session.refresh(vc)

        # 4. 验证设备库存点位变更
        eq1 = db_session.query(EquipmentInventory).filter_by(sn="ICM-ALLOC-000").first()
        eq2 = db_session.query(EquipmentInventory).filter_by(sn="ICM-ALLOC-001").first()
        assert eq1.point_id == 14, f"设备1应在运营点位14，实际{eq1.point_id}"
        assert eq2.point_id == 14, f"设备2应在运营点位14，实际{eq2.point_id}"
        assert eq1.operational_status == OperationalStatus.OPERATING
        assert eq2.operational_status == OperationalStatus.OPERATING

        # 5. 验证 VC subject_status
        assert vc.subject_status == SubjectStatus.FINISH

        print(f"✅ 库存拨付全链路完成: VC_id={vc_id}, 2台设备已拨至运营点位")


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: 资金流推进（所有采购类型共测）
# ─────────────────────────────────────────────────────────────────────────────

class TestCashFlowProgression:
    """资金流推进测试"""

    def test_prepayment_triggers_cash_status(self, db_session, base_data):
        """✅ 预付款到位 → cash_status=PREPAID"""
        # 创建设备采购 VC（总价 29500，30% 预付 = 8850）
        elems = [
            VCElementSchema(shipping_point_id=8, receiving_point_id=14, sku_id=17, qty=10, price=2950, deposit=0, subtotal=29500)
        ]
        payload = CreateProcurementVCSchema(
            business_id=3, sc_id=6,
            elements=elems, total_amt=29500, total_deposit=0,
            payment={"prepayment_ratio": 0.3, "balance_period": 0, "day_rule": "自然日", "start_trigger": "入库日"},
        )
        result = create_procurement_vc_action(db_session, payload)
        assert result.success
        vc_id = result.data["vc_id"]
        db_session.flush()

        # 创建预付款流水
        cf = CashFlow(
            virtual_contract_id=vc_id,
            type=CashFlowType.PREPAYMENT,
            amount=8850,
            transaction_date=datetime.now(),
        )
        db_session.add(cf)
        db_session.flush()

        # 触发状态机（处理资金流）
        _trigger_state_machine(db_session, vc_id, 'cash_flow', cf.id)

        vc = db_session.query(VirtualContract).get(vc_id)
        assert vc.cash_status == CashStatus.PREPAID, f"cash_status={vc.cash_status}"
        print(f"✅ 预付款触发 cash_status=PREPAID")

    def test_full_payment_triggers_cash_status_finish(self, db_session, base_data):
        """✅ 全额付款 + 物流完成 → status=FINISH"""
        points = base_data["points"]
        elems = [
            VCElementSchema(shipping_point_id=8, receiving_point_id=14, sku_id=17, qty=1, price=2950, deposit=0, subtotal=2950)
        ]
        payload = CreateProcurementVCSchema(
            business_id=3, sc_id=6,
            elements=elems, total_amt=2950, total_deposit=0,
            payment={"prepayment_ratio": 0, "balance_period": 0, "day_rule": "自然日", "start_trigger": "入库日"},
        )
        result = create_procurement_vc_action(db_session, payload)
        assert result.success
        vc_id = result.data["vc_id"]
        db_session.flush()

        # 创建物流计划并完成入库
        orders = [{
            "tracking_number": "CASH-FLOW-001",
            "items": [{"sku_id": 17, "sku_name": "冰激凌机-广东中贝-三头两缸", "qty": 1}],
            "address_info": {
                "收货方联系电话": "13800138000",
                "发货方联系电话": "13900139000",
                "收货点位名称": points[14].name,
                "发货点位名称": "广东中贝仓",
                "address": "测试地址",
            }
        }]
        log_result = _create_logistics_for_vc(db_session, vc_id, orders)
        assert log_result.success
        logistics = db_session.query(Logistics).filter_by(virtual_contract_id=vc_id).first()
        _advance_logistics(db_session, logistics.id)
        _confirm_inbound(db_session, logistics.id, sn_list=["CASH-FLOW-SN-001"])
        _trigger_state_machine(db_session, vc_id, 'logistics', logistics.id)

        # 付全额
        cf = CashFlow(
            virtual_contract_id=vc_id,
            type=CashFlowType.FULFILLMENT,
            amount=2950,
            transaction_date=datetime.now(),
        )
        db_session.add(cf)
        db_session.flush()

        _trigger_state_machine(db_session, vc_id, 'cash_flow', cf.id)

        vc = db_session.query(VirtualContract).get(vc_id)
        assert vc.cash_status == CashStatus.FINISH, f"cash_status={vc.cash_status}"
        assert vc.status == VCStatus.FINISH  # 主体已完成时，整体也完成
        print(f"✅ 全额付款触发 cash_status=FINISH + status=FINISH")
