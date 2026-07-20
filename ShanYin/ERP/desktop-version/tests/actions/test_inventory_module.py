"""
库存模块 inventory_module 单元测试
覆盖所有 VC 类型的库存操作，重点测试 Point ID 在 stock_distribution 中的使用

边界条件测试：
1. EQUIPMENT_PROCUREMENT - 设备采购入库，按收货点位存储
2. STOCK_PROCUREMENT - 库存采购入库，按收货点位存储
3. MATERIAL_PROCUREMENT - 物料采购入库，按收货点位分仓库记录
4. MATERIAL_SUPPLY - 物料供应出库，按发货点位分仓库扣减
5. RETURN - 退货处理，按收/发货点位增减库存
"""

import pytest
from datetime import datetime
from logic.inventory import inventory_module
from logic.constants import (
    VCType, VCStatus, SubjectStatus, CashStatus,
    OperationalStatus, DeviceStatus, ReturnDirection, SystemConstants
)


class TestEquipmentProcurementInventory:
    """设备采购入库测试"""

    def test_equipment_procurement_with_point_id(self, db_session, sample_customer, sample_supplier, sample_sku):
        """✅ 设备采购入库 - 收货点位ID正确存储"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, EquipmentInventory

        # 创建点位
        point = type('Point', (), {'id': 100})()  # 模拟点位

        # 创建业务和VC（设备采购）
        business = Business(
            customer_id=sample_customer.id,
            status="业务开展",
            details={}
        )
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.EQUIPMENT_PROCUREMENT,
            elements={
                "elements": [
                    {
                        "sku_id": sample_sku.id,
                        "sku_name": sample_sku.name,
                        "qty": 2,
                        "price": 1000,
                        "deposit": 500,
                        "sn": "-",
                        "receiving_point_id": 100,
                        "receiving_point_name": "客户部署点"
                    }
                ],
                "total_amount": 2000
            },
            deposit_info={"should_receive": 1000, "total_deposit": 0},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        # 创建物流
        logistics = Logistics(
            virtual_contract_id=vc.id,
            status="在途"
        )
        db_session.add(logistics)
        db_session.flush()

        # 创建快递单（包含收货点位Id）
        express_order = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="SF1234567890",
            items=[
                {"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 1},
                {"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 1}
            ],
            address_info={
                "收货点位Id": 100,
                "收货点位名称": "客户部署点",
                "收货方联系电话": "13800138000",
                "发货点位名称": "供应商仓库",
                "address": "测试地址"
            },
            status="签收"
        )
        db_session.add(express_order)
        db_session.flush()

        # 执行入库
        inventory_module(logistics.id, equipment_sn_json=["SN001", "SN002"], session=db_session)

        # 验证设备库存
        equipment_list = db_session.query(EquipmentInventory).all()
        assert len(equipment_list) == 2

        for eq in equipment_list:
            assert eq.point_id == 100  # 收货点位ID正确
            assert eq.sn in ["SN001", "SN002"]
            assert eq.operational_status == OperationalStatus.OPERATING
            assert eq.device_status == DeviceStatus.NORMAL

    def test_equipment_procurement_without_point_id(self, db_session, sample_customer, sample_supplier, sample_sku):
        """✅ 设备采购入库 - 无点位ID时使用默认值"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, EquipmentInventory

        business = Business(
            customer_id=sample_customer.id,
            status="业务开展",
            details={}
        )
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.EQUIPMENT_PROCUREMENT,
            elements={
                "elements": [
                    {"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 1, "price": 1000}
                ],
                "total_amount": 1000
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        express_order = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="SF1234567891",
            items=[{"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 1}],
            address_info={"address": "测试地址"},  # 无点位ID
            status="签收"
        )
        db_session.add(express_order)
        db_session.flush()

        inventory_module(logistics.id, equipment_sn_json=["SN003"], session=db_session)

        equipment_list = db_session.query(EquipmentInventory).all()
        assert len(equipment_list) == 1
        assert equipment_list[0].sn == "SN003"

    def test_equipment_procurement_duplicate_sn(self, db_session, sample_customer, sample_supplier, sample_sku):
        """✅ 设备采购入库 - 重复SN被跳过（不报错）"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, EquipmentInventory

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.EQUIPMENT_PROCUREMENT,
            elements={"items": [{"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 2, "price": 1000}], "total_amount": 2000},
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        express_order = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="SF999",
            items=[{"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 2}],
            address_info={"收货点位Id": 1, "address": "测试"},
            status="签收"
        )
        db_session.add(express_order)
        db_session.flush()

        # 执行入库，包含已存在的SN
        inventory_module(logistics.id, equipment_sn_json=["SN999", "SN001"], session=db_session)

        # SN999被跳过（不存在），SN001被创建
        equipment_list = db_session.query(EquipmentInventory).filter(EquipmentInventory.sn == "SN001").all()
        assert len(equipment_list) == 1


class TestStockProcurementInventory:
    """库存采购入库测试"""

    def test_stock_procurement_with_point_id(self, db_session, sample_customer, sample_supplier, sample_sku):
        """✅ 库存采购入库 - 收货点位ID正确存储"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, EquipmentInventory

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.STOCK_PROCUREMENT,
            elements={
                "items": [{"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 1, "price": 1000}],
                "total_amount": 1000
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        express_order = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="SF444444",
            items=[{"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 1}],
            address_info={
                "收货点位Id": 200,
                "收货点位名称": "自有仓库A",
                "收货方联系电话": "13800138000",
                "address": "仓库地址"
            },
            status="签收"
        )
        db_session.add(express_order)
        db_session.flush()

        inventory_module(logistics.id, equipment_sn_json=["STOCK001"], session=db_session)

        equipment_list = db_session.query(EquipmentInventory).all()
        assert len(equipment_list) == 1
        assert equipment_list[0].sn == "STOCK001"
        assert equipment_list[0].operational_status == OperationalStatus.STOCK  # 库存采购状态为库存


class TestMaterialProcurementInventory:
    """物料采购入库测试"""

    def test_material_procurement_single_warehouse(self, db_session, sample_customer, sample_supplier):
        """✅ 物料采购入库 - 单仓库，创建批次行"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, MaterialInventory, SKU, Point

        # 创建物料SKU
        material_sku = SKU(
            supplier_id=sample_supplier.id,
            name="测试物料-001",
            model="SKU001",
            type_level1="物料",
            type_level2="原料"
        )
        db_session.add(material_sku)
        db_session.flush()

        # 创建仓库点位
        warehouse = Point(name="物料仓库A", type="自有仓")
        db_session.add(warehouse)
        db_session.flush()

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.MATERIAL_PROCUREMENT,
            elements={
                "items": [{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 100, "price": 10}],
                "total_amount": 1000
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        express_order = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="MF555555",
            items=[{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 100}],
            address_info={
                "收货点位Id": warehouse.id,
                "收货点位名称": "物料仓库A",
                "收货方联系电话": "13900139000",
                "发货点位名称": "供应商仓库",
                "address": "仓库地址"
            },
            status="签收"
        )
        db_session.add(express_order)
        db_session.flush()

        inventory_module(logistics.id, session=db_session)

        # 验证物料库存批次行
        batch = db_session.query(MaterialInventory).filter(
            MaterialInventory.sku_id == material_sku.id
        ).first()
        assert batch is not None
        assert batch.qty == 100.0
        assert batch.point_id == warehouse.id
        assert batch.batch_no is not None
        assert f"-{material_sku.model}" in batch.batch_no
        assert batch.latest_purchase_vc_id == vc.id

        # 验证SKU采购统计已更新
        db_session.refresh(material_sku)
        assert material_sku.params.get("historical_purchase_qty") == 100.0
        assert material_sku.params.get("average_price") == 10.0
        assert material_sku.params.get("latest_purchase_vc_id") == vc.id

    def test_material_procurement_multiple_warehouses(self, db_session, sample_customer, sample_supplier):
        """✅ 物料采购入库 - 多仓库，每个仓库独立批次行"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, MaterialInventory, SKU
        from datetime import datetime

        material_sku = SKU(supplier_id=sample_supplier.id, name="测试物料-002", model="MAT002", type_level1="物料")
        db_session.add(material_sku)
        db_session.flush()

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.MATERIAL_PROCUREMENT,
            elements={
                "items": [{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 200, "price": 10}],
                "total_amount": 2000
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        # 第一个快递单 - 仓库301
        express_order1 = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="MF666666",
            items=[{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 80}],
            address_info={
                "收货点位Id": 301,
                "收货点位名称": "仓库A",
                "address": "地址A"
            },
            status="签收"
        )
        db_session.add(express_order1)

        # 第二个快递单 - 仓库302
        express_order2 = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="MF777777",
            items=[{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 120}],
            address_info={
                "收货点位Id": 302,
                "收货点位名称": "仓库B",
                "address": "地址B"
            },
            status="签收"
        )
        db_session.add(express_order2)
        db_session.flush()

        inventory_module(logistics.id, session=db_session)

        # 验证两个批次行
        batches = db_session.query(MaterialInventory).filter(
            MaterialInventory.sku_id == material_sku.id,
            MaterialInventory.qty > 0
        ).all()
        assert len(batches) == 2

        batch_map = {b.point_id: b for b in batches}
        assert 301 in batch_map
        assert 302 in batch_map
        assert batch_map[301].qty == 80.0
        assert batch_map[302].qty == 120.0

        # 验证SKU采购统计
        db_session.refresh(material_sku)
        assert material_sku.params.get("historical_purchase_qty") == 200.0
        assert material_sku.params.get("average_price") == 10.0

    def test_material_procurement_accumulate_existing(self, db_session, sample_customer, sample_supplier):
        """✅ 物料采购入库 - 追加同一批次"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, MaterialInventory, SKU
        from datetime import datetime

        material_sku = SKU(supplier_id=sample_supplier.id, name="测试物料-003", model="MAT003", type_level1="物料",
                           params={"historical_purchase_qty": 50.0, "average_price": 5.0})
        db_session.add(material_sku)
        db_session.flush()

        # 预先创建批次库存（与新采购同一日期同一SKU）
        batch_no = f"{datetime.now().strftime('%Y%m%d')}-{material_sku.model}"
        existing_mat = MaterialInventory(
            sku_id=material_sku.id,
            batch_no=batch_no,
            point_id=400,
            qty=50.0,
            latest_purchase_vc_id=999  # 旧采购VC
        )
        db_session.add(existing_mat)
        db_session.flush()

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.MATERIAL_PROCUREMENT,
            elements={
                "items": [{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 30, "price": 6}],
                "total_amount": 180
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        express_order = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="MF888888",
            items=[{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 30}],
            address_info={
                "收货点位Id": 400,  # 同一个仓库
                "收货点位名称": "仓库C",
                "address": "地址C"
            },
            status="签收"
        )
        db_session.add(express_order)
        db_session.flush()

        inventory_module(logistics.id, session=db_session)

        # 验证同一批次累加
        batch = db_session.query(MaterialInventory).filter(
            MaterialInventory.sku_id == material_sku.id,
            MaterialInventory.point_id == 400,
            MaterialInventory.batch_no == batch_no
        ).first()
        assert batch is not None
        assert batch.qty == 80.0  # 50 + 30

        # 验证SKU采购统计已更新
        db_session.refresh(material_sku)
        assert material_sku.params.get("historical_purchase_qty") == 80.0  # 50 + 30
        assert material_sku.params.get("average_price") == ((50 * 5.0 + 30 * 6) / 80)


class TestMaterialSupplyInventory:
    """物料供应出库测试"""

    def test_material_supply_deduct_by_shipping_point(self, db_session, sample_customer, sample_supplier):
        """✅ 物料供应出库 - 按发货点位扣减批次库存"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, MaterialInventory, SKU
        from datetime import datetime

        material_sku = SKU(supplier_id=sample_supplier.id, name="供应物料-001", model="SUP001", type_level1="物料")
        db_session.add(material_sku)
        db_session.flush()

        # 预先创建批次库存
        batch_no = f"{datetime.now().strftime('%Y%m%d')}-{material_sku.model}"
        existing_mat1 = MaterialInventory(
            sku_id=material_sku.id, batch_no=batch_no, point_id=500, qty=150.0
        )
        existing_mat2 = MaterialInventory(
            sku_id=material_sku.id, batch_no=batch_no, point_id=501, qty=50.0
        )
        db_session.add(existing_mat1)
        db_session.add(existing_mat2)
        db_session.flush()

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.MATERIAL_SUPPLY,
            elements={
                "items": [{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 30, "price": 12}],
                "total_amount": 360
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        express_order = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="MS999999",
            items=[{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 30}],
            address_info={
                "收货点位Id": 600,
                "收货点位名称": "客户仓库",
                "发货点位Id": 500,  # 从仓库500发货
                "发货点位名称": "自有仓库A",
                "address": "客户地址"
            },
            status="签收"
        )
        db_session.add(express_order)
        db_session.flush()

        inventory_module(logistics.id, session=db_session)

        # 验证扣减：仓库500的批次被扣30
        batch1 = db_session.query(MaterialInventory).filter(
            MaterialInventory.sku_id == material_sku.id,
            MaterialInventory.point_id == 500
        ).first()
        assert batch1.qty == 120.0  # 150 - 30

        # 仓库501未变化
        batch2 = db_session.query(MaterialInventory).filter(
            MaterialInventory.sku_id == material_sku.id,
            MaterialInventory.point_id == 501
        ).first()
        assert batch2.qty == 50.0

    def test_material_supply_without_shipping_point_id(self, db_session, sample_customer, sample_supplier):
        """✅ 物料供应出库 - 无发货点位ID使用默认仓"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, MaterialInventory, SKU, Point
        from datetime import datetime

        material_sku = SKU(supplier_id=sample_supplier.id, name="供应物料-002", model="SUP002", type_level1="物料")
        db_session.add(material_sku)
        db_session.flush()

        # 创建默认点位
        default_point = Point(name="默认点位")
        db_session.add(default_point)
        db_session.flush()

        # 预先创建批次库存
        batch_no = f"{datetime.now().strftime('%Y%m%d')}-{material_sku.model}"
        existing_mat = MaterialInventory(
            sku_id=material_sku.id, batch_no=batch_no, point_id=default_point.id, qty=100.0
        )
        db_session.add(existing_mat)
        db_session.flush()

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.MATERIAL_SUPPLY,
            elements={"items": [{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 20, "price": 10}], "total_amount": 200},
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        express_order = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="MS888888",
            items=[{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 20}],
            address_info={
                "收货点位Id": 700,
                "收货点位名称": "客户仓",
                # 无发货点位Id，代码 fallback 到默认点位
                "address": "地址"
            },
            status="签收"
        )
        db_session.add(express_order)
        db_session.flush()

        inventory_module(logistics.id, session=db_session)

        # 验证默认仓扣减
        batch = db_session.query(MaterialInventory).filter(
            MaterialInventory.sku_id == material_sku.id,
            MaterialInventory.point_id == default_point.id
        ).first()
        assert batch.qty == 80.0


class TestReturnInventory:
    """退货库存处理测试"""

    def test_return_customer_to_us_inbound(self, db_session, sample_customer, sample_supplier):
        """✅ 退货-客户退给我们：物料入库，收货点位增加库存（追加到同一批次）"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, MaterialInventory, SKU
        from datetime import datetime

        material_sku = SKU(supplier_id=sample_supplier.id, name="退货物料-001", model="RET001", type_level1="物料",
                           params={"historical_purchase_qty": 100.0, "average_price": 10.0})
        db_session.add(material_sku)
        db_session.flush()

        # 已有批次库存（与退货同一日期同一SKU）
        batch_no = f"{datetime.now().strftime('%Y%m%d')}-{material_sku.model}"
        existing_mat = MaterialInventory(
            sku_id=material_sku.id, batch_no=batch_no, point_id=800, qty=100.0
        )
        db_session.add(existing_mat)
        db_session.flush()

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        # 创建原采购VC（作为 related_vc）
        orig_vc = VirtualContract(
            business_id=business.id,
            type=VCType.MATERIAL_PROCUREMENT,
            elements={
                "items": [{"sku_id": material_sku.id, "qty": 100, "price": 10}],
                "total_amount": 1000
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(orig_vc)
        db_session.flush()

        # 退货VC
        vc = VirtualContract(
            business_id=business.id,
            type=VCType.RETURN,
            related_vc_id=orig_vc.id,
            return_direction=ReturnDirection.CUSTOMER_TO_US,
            elements={
                "items": [
                    {"sku_id": material_sku.id, "qty": 20, "price": 10, "batch_no": batch_no}
                ],
                "total_refund": 200
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        express_order = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="RT111111",
            items=[{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 20}],
            address_info={
                "收货点位Id": 800,  # 收货点位
                "收货点位名称": "退货接收点",
                "发货点位名称": "客户位置",
                "address": "退货地址"
            },
            status="签收"
        )
        db_session.add(express_order)
        db_session.flush()

        inventory_module(logistics.id, session=db_session)

        # 验证退货入库：_get_or_create_batch 会追加到同一批次
        batch = db_session.query(MaterialInventory).filter(
            MaterialInventory.sku_id == material_sku.id,
            MaterialInventory.point_id == 800,
            MaterialInventory.batch_no == batch_no
        ).first()
        assert batch is not None
        assert batch.qty == 120.0  # 100 + 20，追加到同一批次

        # SKU历史采购统计不变（退货不计入）
        db_session.refresh(material_sku)
        assert material_sku.params.get("historical_purchase_qty") == 100.0

    def test_return_us_to_supplier_outbound(self, db_session, sample_customer, sample_supplier):
        """✅ 退货-我们退给供应商：物料出库，发货点位减少库存，回退采购统计"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, MaterialInventory, SKU
        from datetime import datetime

        material_sku = SKU(supplier_id=sample_supplier.id, name="退货物料-002", model="RET002", type_level1="物料",
                           params={"historical_purchase_qty": 100.0, "average_price": 10.0})
        db_session.add(material_sku)
        db_session.flush()

        # 创建原采购批次
        batch_no = f"{datetime.now().strftime('%Y%m%d')}-{material_sku.model}"
        existing_mat = MaterialInventory(
            sku_id=material_sku.id, batch_no=batch_no, point_id=900, qty=100.0
        )
        db_session.add(existing_mat)
        db_session.flush()

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        # 原采购VC（用于退货回退）
        orig_vc = VirtualContract(
            business_id=business.id,
            type=VCType.MATERIAL_PROCUREMENT,
            elements={
                "items": [{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 100, "price": 10}],
                "total_amount": 1000
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(orig_vc)
        db_session.flush()

        # 退货VC
        vc = VirtualContract(
            business_id=business.id,
            type=VCType.RETURN,
            related_vc_id=orig_vc.id,
            return_direction=ReturnDirection.US_TO_SUPPLIER,
            elements={
                "items": [
                    {"sku_id": material_sku.id, "qty": 30, "price": 10, "batch_no": batch_no}
                ],
                "total_refund": 300
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        express_order = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="RT222222",
            items=[{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 30}],
            address_info={
                "收货点位名称": "供应商仓库",
                "发货点位Id": 900,  # 发货点位
                "发货点位名称": "自有仓库B",
                "address": "供应商地址"
            },
            status="签收"
        )
        db_session.add(express_order)
        db_session.flush()

        inventory_module(logistics.id, session=db_session)

        # 验证退货出库：批次数量减少
        batch = db_session.query(MaterialInventory).filter(
            MaterialInventory.sku_id == material_sku.id,
            MaterialInventory.point_id == 900
        ).first()
        assert batch.qty == 70.0  # 100 - 30

        # 验证采购统计增量回退（退货量从历史采购量中扣除）
        db_session.refresh(material_sku)
        assert material_sku.params.get("historical_purchase_qty") == 70.0  # 100 - 30
        assert material_sku.params.get("average_price") == 10.0


class TestInventoryEdgeCases:
    """库存边界条件测试"""

    def test_express_order_items_only_sku_qty(self, db_session, sample_customer, sample_supplier, sample_sku):
        """✅ ExpressOrder items 只包含 sku_id, sku_name, qty（简化结构）"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, EquipmentInventory

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.EQUIPMENT_PROCUREMENT,
            elements={
                "items": [{"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 1, "price": 1000}],
                "total_amount": 1000
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        # items 只包含3个字段：sku_id, sku_name, qty
        express_order = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="SFEDGE001",
            items=[
                {"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 1}
            ],
            address_info={
                "收货点位Id": 999,
                "收货点位名称": "测试点",
                "收货方联系电话": "13899998888",
                "address": "地址"
            },
            status="签收"
        )
        db_session.add(express_order)
        db_session.flush()

        # 应该正常工作
        inventory_module(logistics.id, equipment_sn_json=["SNEDGE1"], session=db_session)

        equipment_list = db_session.query(EquipmentInventory).all()
        assert len(equipment_list) == 1
        assert equipment_list[0].sn == "SNEDGE1"

    def test_multiple_express_orders_same_vc(self, db_session, sample_customer, sample_supplier, sample_sku):
        """✅ 同一VC多个快递单，每个仓库独立批次行"""
        from models import Business, VirtualContract, Logistics, ExpressOrder, MaterialInventory, SKU
        from datetime import datetime

        material_sku = SKU(supplier_id=sample_supplier.id, name="多单物料-001", model="MULTI01", type_level1="物料")
        db_session.add(material_sku)
        db_session.flush()

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.MATERIAL_PROCUREMENT,
            elements={
                "items": [{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 150, "price": 5}],
                "total_amount": 750
            },
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        # 快递单1 -> 仓库111
        eo1 = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="MFMulti01",
            items=[{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 60}],
            address_info={"收货点位Id": 111, "收货点位名称": "仓1", "address": "地址1"},
            status="签收"
        )
        db_session.add(eo1)

        # 快递单2 -> 仓库222
        eo2 = ExpressOrder(
            logistics_id=logistics.id,
            tracking_number="MFMulti02",
            items=[{"sku_id": material_sku.id, "sku_name": material_sku.name, "qty": 90}],
            address_info={"收货点位Id": 222, "收货点位名称": "仓2", "address": "地址2"},
            status="签收"
        )
        db_session.add(eo2)
        db_session.flush()

        inventory_module(logistics.id, session=db_session)

        # 验证两个批次行
        batches = db_session.query(MaterialInventory).filter(
            MaterialInventory.sku_id == material_sku.id,
            MaterialInventory.qty > 0
        ).all()
        assert len(batches) == 2

        batch_map = {b.point_id: b for b in batches}
        assert batch_map[111].qty == 60.0
        assert batch_map[222].qty == 90.0

        # 验证采购统计
        db_session.refresh(material_sku)
        assert material_sku.params.get("historical_purchase_qty") == 150.0

    def test_empty_express_orders(self, db_session, sample_customer, sample_supplier, sample_sku):
        """✅ 物流无快递单时不创建库存"""
        from models import Business, VirtualContract, Logistics

        business = Business(customer_id=sample_customer.id, status="业务开展", details={})
        db_session.add(business)
        db_session.flush()

        vc = VirtualContract(
            business_id=business.id,
            type=VCType.MATERIAL_PROCUREMENT,
            elements={"items": [{"sku_id": sample_sku.id, "sku_name": sample_sku.name, "qty": 10, "price": 100}], "total_amount": 1000},
            deposit_info={},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE
        )
        db_session.add(vc)
        db_session.flush()

        logistics = Logistics(virtual_contract_id=vc.id, status="在途")
        db_session.add(logistics)
        db_session.flush()

        # 不添加任何 ExpressOrder
        inventory_module(logistics.id, session=db_session)

        # 无库存创建
        from models import MaterialInventory
        mat = db_session.query(MaterialInventory).filter(MaterialInventory.sku_id == sample_sku.id).first()
        assert mat is None
