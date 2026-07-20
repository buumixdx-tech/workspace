"""
Addon 原子化 + 合法性校验全面测试
覆盖 SKU 存在性、价格变化、同业务+同 SKU 互斥、重叠等核心规则
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import Base, AddonBusiness, Business, ChannelCustomer, SKU, Supplier, Point, VirtualContract, SupplyChain, MaterialInventory
from logic.vc import (
    create_procurement_vc_action,
    create_material_supply_vc_action,
    create_inventory_allocation_action,
    CreateProcurementVCSchema,
    CreateMaterialSupplyVCSchema,
    AllocateInventorySchema,
    VCElementSchema,
)
from logic.addon_business import (
    create_addon_business_action,
    update_addon_business_action,
)
from logic.addon_business.schemas import CreateAddonSchema, UpdateAddonSchema
from logic.addon_business.queries import (
    sku_exists_in_business,
    get_original_price_and_deposit,
    check_addon_overlap,
)
from logic.constants import AddonType, AddonStatus, BusinessStatus


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def engine():
    db_path = "data/test_addon.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def setup_data(db_session):
    """完整的测试数据依赖链"""
    customer = ChannelCustomer(name="测试客户", info="测试")
    db_session.add(customer)
    supplier = Supplier(name="测试供应商", category="设备", address="地址")
    db_session.add(supplier)
    db_session.flush()

    sku1 = SKU(supplier_id=supplier.id, name="设备-A", type_level1="设备", type_level2="主机", model="A")
    sku2 = SKU(supplier_id=supplier.id, name="设备-B", type_level1="设备", type_level2="主机", model="B")
    sku3 = SKU(supplier_id=supplier.id, name="物料-C", type_level1="物料", type_level2="原料", model="C")
    db_session.add_all([sku1, sku2, sku3])
    db_session.flush()

    # 业务 (ACTIVE)
    business = Business(customer_id=customer.id, status=BusinessStatus.ACTIVE, details={})
    db_session.add(business)

    # 供应商仓、客户仓、我们仓库、客户运营点
    sup_wh = Point(name="供应商仓", type="供应商仓", supplier_id=supplier.id)
    cust_wh = Point(name="客户仓库", type="客户仓", customer_id=customer.id)
    our_wh = Point(name="我们仓库", type="仓库")
    cust_pt = Point(name="客户运营点", type="运营", customer_id=customer.id)
    db_session.add_all([sup_wh, cust_wh, our_wh, cust_pt])
    db_session.flush()

    sc = SupplyChain(supplier_id=supplier.id, type="设备")
    sc_mat = SupplyChain(supplier_id=supplier.id, type="物料")
    db_session.add_all([sc, sc_mat])
    db_session.flush()

    return {
        "customer": customer, "supplier": supplier,
        "sku1": sku1, "sku2": sku2, "sku3": sku3,
        "business": business,
        "sup_wh": sup_wh, "cust_wh": cust_wh, "our_wh": our_wh, "cust_pt": cust_pt,
        "sc": sc, "sc_mat": sc_mat,
    }


# =============================================================================
# 辅助函数
# =============================================================================

def make_addon(session, business_id, addon_type, sku_id, override_price, override_deposit,
               start_date=None, end_date=None):
    start = start_date or datetime.now()
    payload = CreateAddonSchema(
        business_id=business_id, addon_type=addon_type, sku_id=sku_id,
        override_price=override_price, override_deposit=override_deposit,
        start_date=start, end_date=end_date, remark="测试"
    )
    return create_addon_business_action(session, payload)


# =============================================================================
# SKU 存在性查询测试
# =============================================================================

class TestSkuExistsInBusiness:
    """sku_exists_in_business 查询正确性"""

    def test_sku_not_exists_initially(self, db_session, setup_data):
        """新业务，SKU 尚未存在"""
        d = setup_data
        assert sku_exists_in_business(db_session, d["business"].id, d["sku1"].id) is False

    def test_sku_exists_after_vc_created(self, db_session, setup_data):
        """VC 创建后，SKU 存在于业务中"""
        d = setup_data
        # 先创建一条 VC
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        payload = CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        )
        result = create_procurement_vc_action(db_session, payload)
        assert result.success is True

        assert sku_exists_in_business(db_session, d["business"].id, d["sku1"].id) is True
        assert sku_exists_in_business(db_session, d["business"].id, d["sku2"].id) is False


# =============================================================================
# 原价查询测试
# =============================================================================

class TestGetOriginalPriceAndDeposit:
    """get_original_price_and_deposit 查询正确性"""

    def test_returns_none_when_no_history(self, db_session, setup_data):
        """业务无历史时返回 None"""
        d = setup_data
        p, dep = get_original_price_and_deposit(db_session, d["business"].id, d["sku1"].id)
        assert p is None and dep is None

    def test_returns_vc_price(self, db_session, setup_data):
        """从 VC elements 获取原价"""
        d = setup_data
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        payload = CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        )
        create_procurement_vc_action(db_session, payload)

        p, dep = get_original_price_and_deposit(db_session, d["business"].id, d["sku1"].id)
        assert p == 1000.0 and dep == 200.0


# =============================================================================
# 核心校验：SKU 存在性 → addon_type 互斥
# =============================================================================

class TestAddonTypeBySkuExistence:
    """SKU 已存在 → PRICE_ADJUST；不存在 → NEW_SKU"""

    def test_new_sku_requires_nonexistent_sku(self, db_session, setup_data):
        """SKU 不存在时，NEW_SKU 合法"""
        d = setup_data
        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.NEW_SKU, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=150.0,
        )
        assert result.success is True

    def test_new_sku_rejected_if_sku_already_exists(self, db_session, setup_data):
        """SKU 已存在时，NEW_SKU 被拒绝"""
        d = setup_data
        # 先创建 VC 让 SKU 存在
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        ))

        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.NEW_SKU, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=150.0,
        )
        assert result.success is False
        assert "PRICE_ADJUST" in result.error

    def test_price_adjust_requires_existing_sku(self, db_session, setup_data):
        """SKU 存在时，PRICE_ADJUST 合法"""
        d = setup_data
        # 先创建 VC 让 SKU 存在
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        ))

        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=150.0,
        )
        assert result.success is True

    def test_price_adjust_rejected_if_sku_not_exists(self, db_session, setup_data):
        """SKU 不存在时，PRICE_ADJUST 被拒绝"""
        d = setup_data
        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=150.0,
        )
        assert result.success is False
        assert "NEW_SKU" in result.error


# =============================================================================
# 核心校验：价格变化校验
# =============================================================================

class TestPriceChangeValidation:
    """override_price 或 override_deposit 至少有一个与原价不同"""

    def test_price_change_accepted(self, db_session, setup_data):
        """price 从 1000 → 800 → 合法"""
        d = setup_data
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        ))

        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=None,
        )
        assert result.success is True

    def test_price_unchanged_rejected(self, db_session, setup_data):
        """price 从 1000 → 1000（未变化）→ 拒绝"""
        d = setup_data
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        ))

        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=1000.0, override_deposit=None,
        )
        assert result.success is False
        assert "与原价不同" in result.error

    def test_deposit_unchanged_but_price_changed_accepted(self, db_session, setup_data):
        """deposit 不变，price 变化 → 合法"""
        d = setup_data
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        ))

        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=200.0,  # deposit 相同，price 变化
        )
        assert result.success is True

    def test_new_sku_price_accepted_when_no_history(self, db_session, setup_data):
        """NEW_SKU：原价未知，任何新价格都算变化 → 合法"""
        d = setup_data
        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.NEW_SKU, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=150.0,
        )
        assert result.success is True


# =============================================================================
# 核心校验：日期重叠（按 SKU，不按 addon_type）
# =============================================================================

class TestOverlapBySku:
    """同业务 + 同 SKU 禁止日期重叠（不区分 addon_type）"""

    def _create_vcs_for_overlap_tests(self, db_session, d):
        """建立 SKU 存在性（通过 VC elements），使 PRICE_ADJUST 可用"""
        elem1 = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=1, price=1000.0, deposit=200.0,
            subtotal=1000.0, sn_list=[]
        )
        elem2 = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku2"].id, qty=1, price=1100.0, deposit=220.0,
            subtotal=1100.0, sn_list=[]
        )
        create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem1, elem2], total_amt=2100.0, total_deposit=420.0,
            payment={"prepayment_ratio": 0.3}
        ))

    def test_overlap_same_sku_rejected(self, db_session, setup_data):
        """同 SKU + 日期重叠 → 拒绝"""
        d = setup_data
        self._create_vcs_for_overlap_tests(db_session, d)
        today = datetime.now()
        make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=None,
            start_date=today, end_date=today + timedelta(days=30),
        )

        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=700.0, override_deposit=None,
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=40),
        )
        assert result.success is False
        assert "重叠" in result.error

    def test_non_overlap_same_sku_allowed(self, db_session, setup_data):
        """同 SKU + 日期不重叠 → 允许"""
        d = setup_data
        self._create_vcs_for_overlap_tests(db_session, d)
        today = datetime.now()
        make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=None,
            start_date=today, end_date=today + timedelta(days=30),
        )

        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=700.0, override_deposit=None,
            start_date=today + timedelta(days=31),
            end_date=today + timedelta(days=60),
        )
        assert result.success is True

    def test_different_sku_no_overlap(self, db_session, setup_data):
        """不同 SKU → 无重叠问题"""
        d = setup_data
        self._create_vcs_for_overlap_tests(db_session, d)
        today = datetime.now()
        make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=None,
            start_date=today, end_date=today + timedelta(days=30),
        )

        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku2"].id,
            override_price=900.0, override_deposit=None,
            start_date=today, end_date=today + timedelta(days=30),
        )
        assert result.success is True

    def test_permanent_overlaps_with_any(self, db_session, setup_data):
        """永久有效 addon 与任何重叠时间段冲突"""
        d = setup_data
        self._create_vcs_for_overlap_tests(db_session, d)
        today = datetime.now()
        make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=None,
            start_date=today, end_date=None,  # 永久
        )

        result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=700.0, override_deposit=None,
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=20),
        )
        assert result.success is False
        assert "重叠" in result.error


# =============================================================================
# VC 创建时的 addon 应用（原有测试，确保原子化后 VC 应用逻辑正确）
# =============================================================================

class TestVcAddonApplication:
    """VC 创建时正确应用 addon"""

    def test_procurement_vc_with_addon(self, db_session, setup_data):
        """设备采购应用 PRICE_ADJUST"""
        d = setup_data
        # 先建立价格参照
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        ))

        # 创建 addon
        addon_result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=150.0,
        )
        assert addon_result.success is True
        addon_id = addon_result.data["addon_id"]

        # 再创建新 VC，addon 应被应用
        elem2 = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        payload2 = CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem2], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        )
        result2 = create_procurement_vc_action(db_session, payload2)
        assert result2.success is True

        vc = db_session.query(VirtualContract).get(result2.data["vc_id"])
        elems = vc.elements["items"]
        assert elems[0]["price"] == 800.0
        assert elems[0]["deposit"] == 150.0
        assert addon_id in elems[0]["addon_business_ids"]

    def test_no_addon_keeps_original(self, db_session, setup_data):
        """无 addon 时保持原价"""
        d = setup_data
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        result = create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        ))
        assert result.success is True
        vc = db_session.query(VirtualContract).get(result.data["vc_id"])
        assert vc.elements["items"][0]["price"] == 1000.0
        assert vc.elements["items"][0]["addon_business_ids"] == []

    def test_inactive_addon_not_applied(self, db_session, setup_data):
        """失效 addon 不应用"""
        d = setup_data
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        ))

        addon_result = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=None,
        )
        assert addon_result.success is True
        # 失效该 addon
        addon = db_session.query(AddonBusiness).get(addon_result.data["addon_id"])
        addon.status = AddonStatus.INACTIVE
        db_session.flush()

        elem2 = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        result2 = create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem2], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        ))
        assert result2.success is True
        vc = db_session.query(VirtualContract).get(result2.data["vc_id"])
        assert vc.elements["items"][0]["price"] == 1000.0  # addon 未应用


# =============================================================================
# update_addon_business_action 校验
# =============================================================================

class TestUpdateAddonValidation:
    """更新 addon 的合法性校验"""

    def test_update_date_overlap_rejected(self, db_session, setup_data):
        """更新日期导致重叠 → 拒绝"""
        d = setup_data
        # 先建 VC 建立 SKU 存在性
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=1, price=1000.0, deposit=200.0,
            subtotal=1000.0, sn_list=[]
        )
        create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=1000.0, total_deposit=200.0,
            payment={"prepayment_ratio": 0.3}
        ))
        today = datetime.now()
        r1 = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=None,
            start_date=today, end_date=today + timedelta(days=30),
        )
        assert r1.success is True

        r2 = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=700.0, override_deposit=None,
            start_date=today + timedelta(days=31),
            end_date=today + timedelta(days=60),
        )
        assert r2.success is True

        # 更新 r2 的起始日期使其与 r1 重叠
        payload = UpdateAddonSchema(
            addon_id=r2.data["addon_id"],
            start_date=today + timedelta(days=20),  # 重叠
            end_date=today + timedelta(days=60),
        )
        result = update_addon_business_action(db_session, payload)
        assert result.success is False
        assert "重叠" in result.error

    def test_update_price_not_changed_rejected(self, db_session, setup_data):
        """更新价格但未实际变化 → 拒绝"""
        d = setup_data
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        ))

        r1 = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=None,
        )
        assert r1.success is True

        payload = UpdateAddonSchema(
            addon_id=r1.data["addon_id"],
            override_price=800.0,  # 未变化（与当前addon.override_price相同）
        )
        result = update_addon_business_action(db_session, payload)
        assert result.success is False
        assert "当前生效值" in result.error

    def test_update_success(self, db_session, setup_data):
        """合法更新 → 成功"""
        d = setup_data
        elem = VCElementSchema(
            shipping_point_id=d["sup_wh"].id, receiving_point_id=d["cust_pt"].id,
            sku_id=d["sku1"].id, qty=2, price=1000.0, deposit=200.0,
            subtotal=2000.0, sn_list=[]
        )
        create_procurement_vc_action(db_session, CreateProcurementVCSchema(
            business_id=d["business"].id, sc_id=d["sc"].id,
            elements=[elem], total_amt=2000.0, total_deposit=400.0,
            payment={"prepayment_ratio": 0.3}
        ))

        r1 = make_addon(
            session=db_session, business_id=d["business"].id,
            addon_type=AddonType.PRICE_ADJUST, sku_id=d["sku1"].id,
            override_price=800.0, override_deposit=None,
        )
        assert r1.success is True

        payload = UpdateAddonSchema(
            addon_id=r1.data["addon_id"],
            override_price=700.0,  # 真正变化
        )
        result = update_addon_business_action(db_session, payload)
        assert result.success is True

        addon = db_session.query(AddonBusiness).get(r1.data["addon_id"])
        assert addon.override_price == 700.0
