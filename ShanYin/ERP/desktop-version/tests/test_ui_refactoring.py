"""
UI层重构全面测试套件 (已扩展)

测试范围：
1. logic/vc/queries.py
2. logic/business/queries.py
3. logic/master/queries.py
4. logic/logistics/queries.py
5. logic/finance/queries.py
6. logic/supply_chain/queries.py
7. logic/time_rules/queries.py
8. UI层集成与导入验证
"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    get_session, VirtualContract, Business, SupplyChain, 
    Point, ChannelCustomer, Supplier, SKU, TimeRule,
    Logistics, ExpressOrder, CashFlow, MaterialInventory, EquipmentInventory,
    FinanceAccount, FinancialJournal, BankAccount, ExternalPartner
)
from logic.constants import (
    VCType, VCStatus, SubjectStatus, CashStatus, 
    BusinessStatus, SKUType, LogisticsStatus,
    TimeRuleRelatedType, TimeRuleStatus, OperationalStatus
)

# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_session():
    """创建模拟数据库会话"""
    session = Mock()
    session.query = Mock(return_value=session)
    session.filter = Mock(return_value=session)
    session.filter_by = Mock(return_value=session)
    session.join = Mock(return_value=session)
    session.all = Mock(return_value=[])
    session.first = Mock(return_value=None)
    session.count = Mock(return_value=0)
    session.order_by = Mock(return_value=session)
    session.limit = Mock(return_value=session)
    session.get = Mock(return_value=None)
    session.scalar = Mock(return_value=None)
    return session

# =============================================================================
# Test Class: Business Queries
# =============================================================================

class TestBusinessQueries:
    def test_get_business_list(self, mock_session):
        from logic.business.queries import get_business_list

        mock_biz = Mock(spec=Business)
        mock_biz.id = 1
        mock_biz.customer_id = 101
        mock_biz.status = BusinessStatus.ACTIVE
        mock_biz.timestamp = datetime.now()
        mock_biz.details = {}

        mock_customer = Mock(spec=ChannelCustomer)
        mock_customer.name = "Test Customer"
        mock_biz.customer = mock_customer

        # joinedload 后通过 .all() 返回结果
        mock_session.query.return_value.options.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_biz]
        mock_session.query.return_value.options.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_biz]

        with patch('logic.business.queries.get_session', return_value=mock_session):
            result = get_business_list(status=BusinessStatus.ACTIVE)

            assert len(result) == 1
            assert result[0]['id'] == 1
            assert result[0]['customer_name'] == "Test Customer"
            assert mock_session.close.called

    def test_get_business_detail(self, mock_session):
        from logic.business.queries import get_business_detail

        mock_biz = Mock(spec=Business)
        mock_biz.id = 1
        mock_biz.customer_id = 101
        mock_biz.status = BusinessStatus.ACTIVE
        mock_biz.details = {"pricing": {"SKU-A": 100}}
        mock_biz.timestamp = datetime.now()

        mock_customer = Mock(spec=ChannelCustomer)
        mock_customer.id = 101
        mock_customer.name = "Test Customer"
        mock_customer.info = ""

        def mock_get(model_class):
            inner = Mock()
            if model_class == Business:
                inner.get.return_value = mock_biz
            elif model_class == ChannelCustomer:
                inner.get.return_value = mock_customer
            else:
                inner.get.return_value = None
            inner.filter.return_value.all.return_value = []
            return inner

        mock_session.query.side_effect = mock_get

        with patch('logic.business.queries.get_session', return_value=mock_session):
            result = get_business_detail(1)
            assert result['id'] == 1
            assert result['status'] == BusinessStatus.ACTIVE
            assert result['pricing'] == {"SKU-A": 100}

# =============================================================================
# Test Class: VC Queries
# =============================================================================

class TestVCQueries:
    def test_get_vc_list(self, mock_session):
        from logic.vc import queries as vc_q

        mock_vc = Mock(spec=VirtualContract)
        mock_vc.id = 1
        mock_vc.type = VCType.EQUIPMENT_PROCUREMENT
        mock_vc.status = VCStatus.EXE
        mock_vc.status_timestamp = datetime.now()
        mock_vc.elements = {"total_amount": 5000}
        mock_vc.business_id = None

        with patch.object(vc_q, 'get_session', return_value=mock_session), \
             patch.object(vc_q, '_batch_get_latest_log_ts', return_value={}):
            # 让所有 query chain 最终返回 [mock_vc]
            q = mock_session.query.return_value
            q.filter.return_value = q
            q.order_by.return_value = q
            q.limit.return_value = q
            q.all.return_value = [mock_vc]

            result = vc_q.get_vc_list(vc_type=VCType.EQUIPMENT_PROCUREMENT)
            assert len(result) == 1
            assert result[0]['type'] == VCType.EQUIPMENT_PROCUREMENT
            assert result[0]['total_amount'] == 5000

# =============================================================================
# Test Class: Master Queries
# =============================================================================

class TestMasterQueries:
    def test_get_customers_for_ui(self, mock_session):
        from logic.master.queries import get_customers_for_ui
        
        mock_customer = Mock(spec=ChannelCustomer)
        mock_customer.id = 1
        mock_customer.name = "Test Client"
        mock_customer.status = "active"
        mock_customer.created_at = datetime.now()
        mock_customer.contact = "John"
        mock_customer.phone = "123"
        mock_customer.email = "a@b.com"
        mock_customer.address = "Street"
        mock_customer.info = {}
        
        mock_session.all.return_value = [mock_customer]
        
        with patch('logic.master.queries.get_session', return_value=mock_session):
            result = get_customers_for_ui(search_keyword="Test")
            assert len(result) == 1
            assert result[0]['name'] == "Test Client"

    def test_get_stock_equipment_for_allocation(self, mock_session):
        from logic.master.queries import get_stock_equipment_for_allocation

        mock_eq = Mock(spec=EquipmentInventory)
        mock_eq.id = 1
        mock_eq.sn = "SN001"
        mock_eq.sku_id = 10
        mock_eq.point_id = 20
        mock_eq.operational_status = OperationalStatus.STOCK
        mock_eq.device_status = "Good"
        mock_eq.deposit_amount = 1000

        mock_sku = Mock(spec=SKU)
        mock_sku.name = "SKU-A"
        mock_sku.model = "M1"

        mock_point = Mock(spec=Point)
        mock_point.name = "Warehouse-A"

        mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = [mock_eq]
        # get 用于查 SKU 和 Point
        mock_session.query.return_value.get.side_effect = lambda id: mock_sku if id == 10 else mock_point

        with patch('logic.master.queries.get_session', return_value=mock_session):
            result = get_stock_equipment_for_allocation()
            assert len(result) == 1
            assert result[0]['sn'] == "SN001"
            assert result[0]['sku_name'] == "SKU-A"
            assert result[0]['warehouse_name'] == "Warehouse-A"

# =============================================================================
# Test Class: Finance Queries
# =============================================================================

class TestFinanceQueries:
    def test_get_cash_flow_list_for_ui(self, mock_session):
        from logic.finance.queries import get_cash_flow_list_for_ui

        mock_cf = Mock(spec=CashFlow)
        mock_cf.id = 1
        mock_cf.virtual_contract_id = 10
        mock_cf.type = "prepayment"
        mock_cf.amount = 3000
        mock_cf.transaction_date = datetime.now()
        mock_cf.timestamp = datetime.now()
        mock_cf.payer_account = None
        mock_cf.payee_account = None
        mock_cf.description = "Test CF"

        mock_vc = Mock(spec=VirtualContract)
        mock_vc.description = "Test VC"
        mock_cf.virtual_contract = mock_vc

        # joinedload 后通过 order_by + limit + all
        mock_session.query.return_value.options.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_cf]
        mock_session.query.return_value.options.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_cf]
        mock_session.query.return_value.filter.return_value.all.return_value = []

        with patch('logic.finance.queries.get_session', return_value=mock_session):
            result = get_cash_flow_list_for_ui(limit=10)
            assert len(result) == 1
            assert result[0]['amount'] == 3000
            assert result[0]['vc_description'] == "Test VC"

# =============================================================================
# Test Class: Logistics Queries
# =============================================================================

class TestLogisticsQueries:
    def test_get_logistics_list_for_ui(self, mock_session):
        from logic.logistics.queries import get_logistics_list_for_ui

        mock_log = Mock(spec=Logistics)
        mock_log.id = 1
        mock_log.virtual_contract_id = 10
        mock_log.status = LogisticsStatus.TRANSIT
        mock_log.timestamp = datetime.now()
        mock_log.finance_triggered = False

        mock_vc = Mock(spec=VirtualContract)
        mock_vc.description = "Test VC"
        mock_vc.type = VCType.EQUIPMENT_PROCUREMENT
        mock_log.virtual_contract = mock_vc
        mock_log.express_orders = []

        # joinedload 后通过 order_by + limit + all
        mock_session.query.return_value.options.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_log]
        mock_session.query.return_value.options.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_log]

        with patch('logic.logistics.queries.get_session', return_value=mock_session):
            result = get_logistics_list_for_ui(status_list=[LogisticsStatus.TRANSIT])
            assert len(result) == 1
            assert result[0]['status'] == LogisticsStatus.TRANSIT
            assert result[0]['vc_description'] == "Test VC"

# =============================================================================
# Test Class: Supply Chain Queries
# =============================================================================

class TestSupplyChainQueries:
    def test_get_supply_chain_detail_for_ui(self, mock_session):
        from logic.supply_chain.queries import get_supply_chain_detail_for_ui

        mock_sc = Mock(spec=SupplyChain)
        mock_sc.id = 1
        mock_sc.supplier_id = 101
        mock_sc.type = SKUType.EQUIPMENT
        mock_sc.pricing_config = {"SKU-A": 500}
        mock_sc.payment_terms = {"prepayment_ratio": 0.5}
        mock_sc.contract_id = None
        mock_sc.items = []  # get_pricing_dict 用到
        mock_sc.get_pricing_dict = lambda: {"SKU-A": 500}

        mock_supplier = Mock(spec=Supplier)
        mock_supplier.name = "Test Supplier"
        mock_supplier.info = {}

        def query_get_side_effect(model_or_id):
            if hasattr(model_or_id, '__tablename__') and model_or_id.__tablename__ == 'supply_chains':
                return mock_sc
            return mock_supplier if model_or_id == 101 else None

        # 处理 query(SupplyChain).options().get() 和 query(Supplier).get() 两条路径
        mock_session.query.return_value.options.return_value.get.side_effect = lambda id: mock_sc if id == 1 else None
        mock_session.query.return_value.get.side_effect = query_get_side_effect

        with patch('logic.supply_chain.queries.get_session', return_value=mock_session):
            result = get_supply_chain_detail_for_ui(1)
            assert result['supplier_name'] == "Test Supplier"
            assert result['pricing_count'] == 1
            assert result['payment_terms']['prepayment_ratio_pct'] == 50

# =============================================================================
# Test Class: Time Rule Queries
# =============================================================================

class TestTimeRuleQueries:
    def test_get_time_rules_for_ui(self, mock_session):
        from logic.time_rules.queries import get_time_rules_for_ui

        mock_rule = Mock(spec=TimeRule)
        mock_rule.id = 1
        mock_rule.related_type = TimeRuleRelatedType.BUSINESS
        mock_rule.related_id = 10
        mock_rule.party = "ourselves"
        mock_rule.trigger_event = "Event A"
        mock_rule.target_event = "Event B"
        mock_rule.offset = 1
        mock_rule.unit = "day"
        mock_rule.direction = "after"
        mock_rule.status = TimeRuleStatus.ACTIVE
        mock_rule.flag_time = None
        mock_rule.timestamp = datetime.now()
        mock_rule.resultstamp = None

        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_rule]

        with patch('logic.time_rules.queries._get_related_object_info', return_value={"name": "Biz-10", "detail": ""}):
            with patch('logic.time_rules.queries.get_session', return_value=mock_session):
                result = get_time_rules_for_ui(related_type=TimeRuleRelatedType.BUSINESS)
                assert len(result) == 1
                assert result[0]['party_label'] == "我方"
                assert result[0]['related_name'] == "Biz-10"

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
