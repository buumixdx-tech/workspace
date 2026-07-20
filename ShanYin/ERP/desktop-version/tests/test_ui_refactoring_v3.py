import pytest
from datetime import datetime
from models import get_session, Business, ChannelCustomer, Supplier, SKU, Point, BankAccount, VirtualContract, Logistics, ExpressOrder, TimeRule, PartnerRelation, ExternalPartner
from logic.constants import VCType, VCStatus, SubjectStatus, CashStatus, CashFlowType, AccountOwnerType, PointType, PartnerRelationType, ReturnDirection
from logic.master.queries import get_customers_for_ui, get_suppliers_for_ui, get_points_for_ui, get_bank_accounts_for_ui
from logic.logistics.queries import get_logistics_list_for_ui, get_express_orders_by_logistics
from logic.vc.queries import get_vc_list_for_overview, get_vc_by_id
from logic.business.queries import get_business_detail
from logic.time_rules.queries import get_time_rules_for_ui


def test_get_time_rules_for_ui_fields():
    """验证时间规则查询包含必备字段"""
    results = get_time_rules_for_ui(limit=5)
    if results:
        rule = results[0]
        assert "id" in rule
        assert "status_label" in rule
        assert "created_at" in rule
    session = get_session()
    # 确保至少有一个数据
    p = session.query(Point).first()
    if not p:
        pytest.skip("No Point data for testing")
    
    results = get_points_for_ui(limit=5)
    assert isinstance(results, list)
    if results:
        point_dict = results[0]
        assert isinstance(point_dict, dict)
        assert "id" in point_dict
        assert "owner_label" in point_dict
        assert "customer_name" in point_dict
        assert "type" in point_dict
        assert "address" in point_dict

def test_get_suppliers_for_ui_fields():
    """验证供应商查询包含 category 字段"""
    results = get_suppliers_for_ui(limit=1)
    if results:
        sup = results[0]
        assert "category" in sup
        assert isinstance(sup["category"], str)

def test_get_bank_accounts_for_ui_fields():
    """验证银行账户查询包含 owner_label 和 holder_name"""
    results = get_bank_accounts_for_ui(limit=1)
    if results:
        acc = results[0]
        assert "owner_label" in acc
        assert "holder_name" in acc
        assert "account_no" in acc
        # 验证账号不是脱敏的（用于编辑器）
        assert "*" not in acc["account_no"] or len(acc["account_no"]) > 10

def test_get_logistics_list_for_ui_fields():
    """验证物流列表包含基础字段且不报属性错误"""
    results = get_logistics_list_for_ui(limit=1)
    if results:
        log = results[0]
        assert "id" in log
        assert "status" in log
        assert "timestamp" in log
        assert "vc_description" in log

def test_get_express_orders_by_logistics_fields():
    """验证快递单查询包含 created_at (映射自 timestamp)"""
    # 找一个有快递单的物流 ID
    session = get_session()
    eo = session.query(ExpressOrder).first()
    if eo:
        results = get_express_orders_by_logistics(eo.logistics_id)
        assert isinstance(results, list)
        if results:
            order = results[0]
            assert "created_at" in order
            # 验证时间格式
            assert ":" in order["created_at"]

def test_get_business_detail_fields():
    """验证业务详情包含顶层 customer_id"""
    session = get_session()
    biz = session.query(Business).first()
    if biz:
        detail = get_business_detail(biz.id)
        assert detail is not None
        assert "customer_id" in detail
        assert "id" in detail
        assert isinstance(detail["customer"], dict)

def test_calculate_cashflow_progress_robustness():
    """测试计算进度对 None 值的防御性"""
    from logic.services import calculate_cashflow_progress
    session = get_session()
    
    # 构造一个极简 VC 字典，模拟缺失 elements
    mock_vc = {
        "id": 9999,
        "type": VCType.EQUIPMENT_PROCUREMENT,
        "elements": None,
        "deposit_info": None
    }
    
    # 不应报错
    progress = calculate_cashflow_progress(session, mock_vc, [])
    assert "goods" in progress
    assert progress["goods"]["total"] == 0.0
    assert progress["deposit"]["should"] == 0.0

def test_get_suggested_cashflow_parties_dict_support():
    """测试建议收付方适配字典对象"""
    from logic.services import get_suggested_cashflow_parties
    session = get_session()
    
    mock_vc = {
        "id": 8888,
        "type": VCType.MATERIAL_SUPPLY,
        "business_id": None,
        "elements": {"total_amount": 1000}
    }
    
    # 不应报 AttributeError: 'dict' object has no attribute 'type'
    parties = get_suggested_cashflow_parties(session, mock_vc, cf_type=CashFlowType.FULFILLMENT)
    assert len(parties) == 4
    # 物料供应建议收付方：付款方是客户
    assert parties[0] == AccountOwnerType.CUSTOMER

def test_get_suggested_cashflow_parties_material_supply_with_single_procurement_partner(db_session, sample_business):
    """MATERIAL_SUPPLY：Business 关联恰好一个'采购执行'合作方时，payer 应为 PARTNER"""
    from logic.services import get_suggested_cashflow_parties

    # 创建测试合作方
    partner = ExternalPartner(name="测试合作方_采购执行")
    db_session.add(partner)
    db_session.flush()

    # 创建恰好一个"采购执行"关系
    rel = PartnerRelation(
        partner_id=partner.id,
        owner_type="business",
        owner_id=sample_business.id,
        relation_type=PartnerRelationType.PROCUREMENT
    )
    db_session.add(rel)
    db_session.flush()

    mock_vc = {
        "id": 9999,
        "type": VCType.MATERIAL_SUPPLY,
        "business_id": sample_business.id,
        "supply_chain_id": None,
        "return_direction": None,
        "elements": {"total_amount": 1000}
    }
    parties = get_suggested_cashflow_parties(db_session, mock_vc, cf_type=CashFlowType.FULFILLMENT)
    # payer 应为合作方
    assert parties[0] == AccountOwnerType.PARTNER, f"Expected PARTNER, got {parties[0]}"
    assert parties[1] == partner.id, f"Expected partner.id={partner.id}, got {parties[1]}"


def test_get_suggested_cashflow_parties_material_supply_with_multiple_procurement_partners(db_session, sample_business):
    """MATERIAL_SUPPLY：Business 关联多个'采购执行'合作方时，payer 应退回 CUSTOMER"""
    from logic.services import get_suggested_cashflow_parties

    # 创建两个合作方
    partner1 = ExternalPartner(name="测试合作方_甲")
    partner2 = ExternalPartner(name="测试合作方_乙")
    db_session.add_all([partner1, partner2])
    db_session.flush()

    rel1 = PartnerRelation(partner_id=partner1.id, owner_type="business", owner_id=sample_business.id, relation_type=PartnerRelationType.PROCUREMENT)
    rel2 = PartnerRelation(partner_id=partner2.id, owner_type="business", owner_id=sample_business.id, relation_type=PartnerRelationType.PROCUREMENT)
    db_session.add_all([rel1, rel2])
    db_session.flush()

    mock_vc = {
        "id": 9998,
        "type": VCType.MATERIAL_SUPPLY,
        "business_id": sample_business.id,
        "supply_chain_id": None,
        "return_direction": None,
        "elements": {"total_amount": 1000}
    }
    parties = get_suggested_cashflow_parties(db_session, mock_vc, cf_type=CashFlowType.FULFILLMENT)
    # 多个合作方时应退回渠道客户
    assert parties[0] == AccountOwnerType.CUSTOMER, f"Expected CUSTOMER, got {parties[0]}"
    assert parties[1] == sample_business.customer_id, f"Expected customer_id={sample_business.customer_id}, got {parties[1]}"


def test_get_suggested_cashflow_parties_return_customer_to_us_with_single_procurement_partner(db_session, sample_business):
    """RETURN CUSTOMER_TO_US：Business 关联恰好一个'采购执行'合作方时，payee 应为 PARTNER"""
    from logic.services import get_suggested_cashflow_parties

    partner = ExternalPartner(name="测试合作方_退货")
    db_session.add(partner)
    db_session.flush()

    rel = PartnerRelation(
        partner_id=partner.id,
        owner_type="business",
        owner_id=sample_business.id,
        relation_type=PartnerRelationType.PROCUREMENT
    )
    db_session.add(rel)
    db_session.flush()

    mock_vc = {
        "id": 9997,
        "type": VCType.RETURN,
        "business_id": sample_business.id,
        "supply_chain_id": None,
        "return_direction": ReturnDirection.CUSTOMER_TO_US,
        "elements": {"total_amount": 500}
    }
    parties = get_suggested_cashflow_parties(db_session, mock_vc, cf_type=CashFlowType.REFUND)
    # payee 应为合作方
    assert parties[2] == AccountOwnerType.PARTNER, f"Expected PARTNER, got {parties[2]}"
    assert parties[3] == partner.id, f"Expected partner.id={partner.id}, got {parties[3]}"


if __name__ == "__main__":
    pytest.main([__file__])
