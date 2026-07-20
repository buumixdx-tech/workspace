"""
queries 层集成测试

使用真实 SQLite 内存数据库验证 SQL 逻辑正确性。
测试重点：
1. 过滤条件是否生效
2. 关联对象缺失时是否安全处理
3. N+1 查询问题验证
4. 接口一致性（公开函数不应接受 session 参数）
"""

import pytest
import inspect
import importlib
import importlib.util
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import (
    Base, ChannelCustomer, Supplier, Point, SKU,
    EquipmentInventory, MaterialInventory, VirtualContract,
    Business, Logistics, ExpressOrder, CashFlow,
    FinanceAccount, FinancialJournal, BankAccount
)
from logic.constants import (
    BusinessStatus, VCType, VCStatus, LogisticsStatus,
    OperationalStatus, SKUType
)


def _load_queries(domain):
    """直接从文件路径加载 queries 模块，绕过 __init__.py 中的旧导入问题"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    spec = importlib.util.spec_from_file_location(
        f"logic.{domain}.queries",
        os.path.join(root, "logic", domain, "queries.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


business_queries = _load_queries('business')
vc_queries = _load_queries('vc')
master_queries = _load_queries('master')
logistics_queries = _load_queries('logistics')
finance_queries = _load_queries('finance')


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def session(engine):
    """每个测试独立事务，测试后回滚"""
    conn = engine.connect()
    trans = conn.begin()
    Session = sessionmaker(bind=conn)
    sess = Session()
    yield sess
    sess.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def customer(session):
    c = ChannelCustomer(name="测试客户", info=None)
    session.add(c)
    session.flush()
    return c


@pytest.fixture
def supplier(session):
    s = Supplier(name="测试供应商", category="设备", address="供应商地址")
    session.add(s)
    session.flush()
    return s


@pytest.fixture
def sku(session, supplier):
    s = SKU(supplier_id=supplier.id, name="测试设备A", type_level1=SKUType.EQUIPMENT, model="M1")
    session.add(s)
    session.flush()
    return s


@pytest.fixture
def business(session, customer):
    b = Business(customer_id=customer.id, status=BusinessStatus.ACTIVE, details={})
    session.add(b)
    session.flush()
    return b


@pytest.fixture
def virtual_contract(session, business):
    vc = VirtualContract(
        business_id=business.id,
        type=VCType.EQUIPMENT_PROCUREMENT,
        status=VCStatus.EXE,
        subject_status="执行",
        cash_status="执行",
        elements={"total_amount": 5000},
        description="测试采购合同"
    )
    session.add(vc)
    session.flush()
    return vc


# =============================================================================
# 1. 接口一致性测试
# =============================================================================

class TestQueryInterfaceConsistency:
    """验证公开查询函数不接受 session 参数"""

    def _get_violations(self, module):
        return [
            name for name, func in inspect.getmembers(module, inspect.isfunction)
            if not name.startswith('_') and 'session' in inspect.signature(func).parameters
        ]

    def test_master_queries_no_session_param(self):
        assert self._get_violations(master_queries) == []

    def test_logistics_queries_no_session_param(self):
        assert self._get_violations(logistics_queries) == []

    def test_finance_queries_no_session_param(self):
        assert self._get_violations(finance_queries) == []

    def test_business_queries_no_session_param(self):
        """business/queries.py 所有公开函数不接受 session 参数"""
        assert self._get_violations(business_queries) == []

    def test_vc_queries_no_session_param(self):
        """vc/queries.py 所有公开函数不接受 session 参数（UI 层专用点选择函数除外）"""
        # 以下函数是 UI 层专用，需要 session 参数用于复杂联表查询
        ui_helper_funcs = {
            'get_valid_receiving_points_for_procurement',
            'get_valid_receiving_points_for_mat_procurement',
            'get_valid_shipping_points_for_mat_procurement',
            'get_valid_receiving_points_for_material_supply',
            'get_valid_shipping_points_for_material_supply',
            'get_valid_receiving_points_for_allocation',
            'get_valid_shipping_points_for_allocation',
            'get_valid_shipping_points_for_return_equipment',
            'get_valid_shipping_points_for_return_mat',
            'get_valid_receiving_points_for_return',
            # 物料批次查询（session-aware）
            'get_available_batches_by_sku',
            'get_latest_supply_batches_by_sku',
        }
        violations = [
            name for name, func in inspect.getmembers(vc_queries, inspect.isfunction)
            if not name.startswith('_') and 'session' in inspect.signature(func).parameters
            and name not in ui_helper_funcs
        ]
        assert violations == [], f"VC query functions with session param (excluding UI helpers): {violations}"


# =============================================================================
# 2. 业务查询集成测试
# =============================================================================

class TestBusinessQueriesIntegration:

    def test_detail_not_found(self, session):
        """不存在的 ID 应返回 None"""
        with patch.object(business_queries, 'get_session', return_value=session):
            result = business_queries.get_business_detail(99999)
        assert result is None

    def test_get_businesses_for_execution_no_session_param(self):
        """get_businesses_for_execution 已修复，不再接受 session 参数"""
        sig = inspect.signature(business_queries.get_businesses_for_execution)
        assert 'session' not in sig.parameters


# =============================================================================
# 3. VC 查询集成测试
# =============================================================================

class TestVCQueriesIntegration:

    def test_filter_by_type(self, session, business):
        vc1 = VirtualContract(
            business_id=business.id, type=VCType.EQUIPMENT_PROCUREMENT,
            status=VCStatus.EXE, subject_status="执行", cash_status="执行",
            elements={"total_amount": 1000}
        )
        vc2 = VirtualContract(
            business_id=business.id, type=VCType.MATERIAL_SUPPLY,
            status=VCStatus.EXE, subject_status="执行", cash_status="执行",
            elements={"total_amount": 500}
        )
        session.add_all([vc1, vc2])
        session.flush()

        with patch.object(vc_queries, 'get_session', return_value=session):
            result = vc_queries.get_vc_list(vc_type=VCType.EQUIPMENT_PROCUREMENT)
            types = [r['type'] for r in result]
            assert VCType.EQUIPMENT_PROCUREMENT in types
            assert VCType.MATERIAL_SUPPLY not in types

    def test_detail_returns_elements(self, session, virtual_contract):
        with patch.object(vc_queries, 'get_session', return_value=session):
            result = vc_queries.get_vc_detail(virtual_contract.id)

        assert result is not None
        assert result['elements']['total_amount'] == 5000

    def test_detail_not_found(self, session):
        with patch.object(vc_queries, 'get_session', return_value=session):
            result = vc_queries.get_vc_detail(99999)
        assert result is None

    def test_cash_flows_empty(self, session, virtual_contract):
        with patch.object(vc_queries, 'get_session', return_value=session):
            result = vc_queries.get_vc_cash_flows(virtual_contract.id)
        assert result == []

    def test_count_by_business(self, session, business):
        vc1 = VirtualContract(
            business_id=business.id, type=VCType.EQUIPMENT_PROCUREMENT,
            status=VCStatus.EXE, subject_status="执行", cash_status="执行", elements={}
        )
        vc2 = VirtualContract(
            business_id=business.id, type=VCType.MATERIAL_SUPPLY,
            status=VCStatus.EXE, subject_status="执行", cash_status="执行", elements={}
        )
        session.add_all([vc1, vc2])
        session.flush()

        with patch.object(vc_queries, 'get_session', return_value=session):
            count = vc_queries.get_vc_count_by_business(business.id)
        assert count == 2

    def test_time_rules_for_vc_empty(self, session, virtual_contract):
        with patch.object(vc_queries, 'get_session', return_value=session):
            result = vc_queries.get_time_rules_for_vc(virtual_contract.id)
        assert result == []

    def test_status_logs_empty(self, session, virtual_contract):
        with patch.object(vc_queries, 'get_session', return_value=session):
            result = vc_queries.get_vc_status_logs(virtual_contract.id)
        assert result == []


# =============================================================================
# 4. 主数据查询集成测试
# =============================================================================

class TestMasterQueriesIntegration:

    def test_customer_search_keyword(self, session):
        """关键词搜索应过滤结果"""
        c1 = ChannelCustomer(name="北京科技公司", info=None)
        c2 = ChannelCustomer(name="上海贸易公司", info=None)
        session.add_all([c1, c2])
        session.flush()

        with patch.object(master_queries, 'get_session', return_value=session):
            result = master_queries.get_customers_for_ui(search_keyword="北京")
            names = [r['name'] for r in result]
            assert "北京科技公司" in names
            assert "上海贸易公司" not in names

    def test_skus_filter_by_supplier(self, session, supplier, sku):
        """supplier_id 过滤"""
        s2 = Supplier(name="其他供应商", category="物料", address="地址")
        session.add(s2)
        session.flush()
        sku2 = SKU(supplier_id=s2.id, name="其他物料", type_level1=SKUType.MATERIAL)
        session.add(sku2)
        session.flush()

        with patch.object(master_queries, 'get_session', return_value=session):
            result = master_queries.get_skus_for_ui(supplier_id=supplier.id)
            names = [r['name'] for r in result]
            assert "测试设备A" in names
            assert "其他物料" not in names

    def test_stock_equipment_status_filter(self, session, sku):
        """operational_status 过滤应只返回库存中的设备"""
        eq_stock = EquipmentInventory(
            sku_id=sku.id, sn="SN001",
            operational_status=OperationalStatus.STOCK, device_status="正常"
        )
        eq_operating = EquipmentInventory(
            sku_id=sku.id, sn="SN002",
            operational_status=OperationalStatus.OPERATING, device_status="正常"
        )
        session.add_all([eq_stock, eq_operating])
        session.flush()

        with patch.object(master_queries, 'get_session', return_value=session):
            result = master_queries.get_stock_equipment_for_allocation()

        sns = [r['sn'] for r in result]
        assert "SN001" in sns
        assert "SN002" not in sns

    def test_stock_equipment_no_point_shows_default(self, session, sku):
        """point_id 为 None 时，warehouse_name 应显示默认值"""
        eq = EquipmentInventory(
            sku_id=sku.id, sn="SN_NO_POINT",
            operational_status=OperationalStatus.STOCK,
            device_status="正常", point_id=None
        )
        session.add(eq)
        session.flush()

        with patch.object(master_queries, 'get_session', return_value=session):
            result = master_queries.get_stock_equipment_for_allocation()

        match = next((r for r in result if r['sn'] == "SN_NO_POINT"), None)
        assert match is not None
        assert match['warehouse_name'] in ("自有仓", "库存中")

    def test_sku_map_by_names(self, session, sku):
        """get_sku_map_by_names 应返回名称到详情的映射"""
        with patch.object(master_queries, 'get_session', return_value=session):
            result = master_queries.get_sku_map_by_names(["测试设备A"])

        assert "测试设备A" in result
        assert result["测试设备A"]["id"] == sku.id


# =============================================================================
# 5. 物流查询集成测试
# =============================================================================

class TestLogisticsQueriesIntegration:

    def test_filter_by_status(self, session, virtual_contract):
        l1 = Logistics(virtual_contract_id=virtual_contract.id, status=LogisticsStatus.PENDING)
        l2 = Logistics(virtual_contract_id=virtual_contract.id, status=LogisticsStatus.TRANSIT)
        session.add_all([l1, l2])
        session.flush()

        with patch.object(logistics_queries, 'get_session', return_value=session):
            result = logistics_queries.get_logistics_list_for_ui(status_list=[LogisticsStatus.PENDING])

        statuses = [r['status'] for r in result]
        assert LogisticsStatus.PENDING in statuses
        assert LogisticsStatus.TRANSIT not in statuses

    def test_filter_by_vc_id(self, session, business):
        vc1 = VirtualContract(
            business_id=business.id, type=VCType.EQUIPMENT_PROCUREMENT,
            status=VCStatus.EXE, subject_status="执行", cash_status="执行", elements={}
        )
        vc2 = VirtualContract(
            business_id=business.id, type=VCType.EQUIPMENT_PROCUREMENT,
            status=VCStatus.EXE, subject_status="执行", cash_status="执行", elements={}
        )
        session.add_all([vc1, vc2])
        session.flush()

        l1 = Logistics(virtual_contract_id=vc1.id, status=LogisticsStatus.PENDING)
        l2 = Logistics(virtual_contract_id=vc2.id, status=LogisticsStatus.PENDING)
        session.add_all([l1, l2])
        session.flush()

        with patch.object(logistics_queries, 'get_session', return_value=session):
            result = logistics_queries.get_logistics_list_for_ui(vc_id=vc1.id)

        assert all(r['vc_id'] == vc1.id for r in result)

    def test_express_orders_by_logistics(self, session, virtual_contract):
        """get_express_orders_by_logistics 返回指定物流的快递单"""
        log = Logistics(virtual_contract_id=virtual_contract.id, status=LogisticsStatus.PENDING)
        session.add(log)
        session.flush()

        o1 = ExpressOrder(logistics_id=log.id, tracking_number="SF001", status=LogisticsStatus.PENDING)
        session.add(o1)
        session.flush()

        with patch.object(logistics_queries, 'get_session', return_value=session):
            result = logistics_queries.get_express_orders_by_logistics(log.id)
            assert any(r['tracking_number'] == "SF001" for r in result)

    def test_empty_returns_list(self, session):
        with patch.object(logistics_queries, 'get_session', return_value=session):
            result = logistics_queries.get_logistics_list_for_ui()
        assert isinstance(result, list)

    def test_dashboard_summary_structure(self, session):
        """dashboard 返回结构应包含必要字段"""
        with patch.object(logistics_queries, 'get_session', return_value=session):
            result = logistics_queries.get_logistics_dashboard_summary()
            assert 'logistics_summary' in result
            assert 'express_summary' in result


# =============================================================================
# 6. 财务查询集成测试
# =============================================================================

class TestFinanceQueriesIntegration:

    def test_cash_flow_filter_by_vc(self, session, virtual_contract):
        """get_cash_flow_list_for_ui 按 vc_id 过滤资金流"""
        cf = CashFlow(
            virtual_contract_id=virtual_contract.id,
            type="预付款", amount=1000.0,
            transaction_date=datetime.now()
        )
        session.add(cf)
        session.flush()

        with patch.object(finance_queries, 'get_session', return_value=session):
            result = finance_queries.get_cash_flow_list_for_ui(vc_id=virtual_contract.id)
            assert len(result) >= 1
            assert all(r['vc_id'] == virtual_contract.id for r in result)

    def test_cash_flow_no_payer_account_no_crash(self, session, virtual_contract):
        """payer_account 为 None 时，格式化不应崩溃"""
        cf = CashFlow(
            virtual_contract_id=virtual_contract.id,
            type="预付款", amount=500.0,
            transaction_date=datetime.now(),
            payer_account_id=None, payee_account_id=None
        )
        session.add(cf)
        session.flush()

        with patch.object(finance_queries, 'get_session', return_value=session):
            result = finance_queries.get_cash_flow_list_for_ui(vc_id=virtual_contract.id)
            assert result[0]['payer_info']['label'] == "未指定/现金"

    def test_journal_entries_filter_by_account(self, session):
        acc1 = FinanceAccount(level1_name="应收账款", direction="Debit", category="资产")
        acc2 = FinanceAccount(level1_name="应付账款", direction="Credit", category="负债")
        session.add_all([acc1, acc2])
        session.flush()

        j1 = FinancialJournal(
            account_id=acc1.id, debit=1000.0, credit=0.0,
            transaction_date=datetime.now(), voucher_no="V001", summary="测试"
        )
        j2 = FinancialJournal(
            account_id=acc2.id, debit=0.0, credit=1000.0,
            transaction_date=datetime.now(), voucher_no="V001", summary="测试"
        )
        session.add_all([j1, j2])
        session.flush()

        with patch.object(finance_queries, 'get_session', return_value=session):
            result = finance_queries.get_journal_entries_for_ui(account_id=acc1.id)

        assert all(r['account_id'] == acc1.id for r in result)


# =============================================================================
# 7. N+1 查询检测测试
# =============================================================================

class TestNPlusOneDetection:
    """检测 N+1 查询问题，记录当前状态"""

    def test_get_points_query_count(self, session, customer):
        """记录 get_points_for_ui 的 SQL 执行次数"""
        for i in range(5):
            p = Point(name=f"点位{i}", customer_id=customer.id, type="运营点位")
            session.add(p)
        session.flush()

        sql_count = [0]

        @event.listens_for(session.bind, "before_cursor_execute")
        def count_queries(conn, cursor, statement, parameters, context, executemany):
            sql_count[0] += 1

        with patch.object(master_queries, 'get_session', return_value=session):
            result = master_queries.get_points_for_ui(customer_id=customer.id)
            assert len(result) == 5
            print(f"\nget_points_for_ui(5个点位) 执行了 {sql_count[0]} 次 SQL")
            # 修复 N+1 后取消注释：
            assert sql_count[0] <= 3
