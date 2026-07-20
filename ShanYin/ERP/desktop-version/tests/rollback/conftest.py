"""
Rollback 测试专用配置
使用 in-memory SQLite，每个测试完全隔离
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from datetime import datetime
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base


# ============ Fixtures ============

@pytest.fixture(scope="function")
def engine():
    """In-memory engine，每个测试函数独立"""
    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture(scope="function")
def session(engine) -> Session:
    """每个测试独立的 session，测试结束后 rollback"""
    conn = engine.connect()
    trans = conn.begin()
    s = sessionmaker(bind=conn)()
    yield s
    s.close()
    trans.rollback()
    conn.close()


@pytest.fixture(scope="function")
def base_data(session):
    """
    Session 级最小基础数据（按需创建，不依赖特定表结构）。
    测试如果不需要某个实体就不创建。
    """
    from models import ChannelCustomer, Supplier, SKU, Business

    customer = ChannelCustomer(name="测试客户", info="测试")
    supplier = Supplier(name="测试供应商", category="设备", address="测试地址")
    sku = SKU(
        supplier_id=None,  # 先建 supplier 再填
        name="测试SKU",
        type_level1="设备",
        type_level2="主机",
        model="TEST-001",
        description="测试"
    )
    session.add_all([customer, supplier, sku])
    session.flush()

    sku.supplier_id = supplier.id

    business = Business(customer_id=customer.id, status="业务开展", details={})
    session.add(business)
    session.flush()

    return AttrDict(
        customer=customer,
        supplier=supplier,
        sku=sku,
        business=business,
    )


class AttrDict(dict):
    """支持 dot 访问的 dict"""
    def __getattr__(self, key):
        return self[key]


# ============ 辅助：快速创建实体 ============

def create_vc(session, business_id, flush=True, **overrides):
    """创建最小可用 VirtualContract

    Args:
        flush: 是否立即 flush（默认 True）。测试 snapshot 时传 False，
               然后在调用 serialize_objs 之前手动 flush。
    """
    from models import VirtualContract
    defaults = dict(
        business_id=business_id,
        type="设备采购",
        elements={"elements": [], "total_amount": 0.0},
        deposit_info={"should_receive": 0.0, "total_deposit": 0.0},
        status="执行",
        subject_status="执行",
        cash_status="执行",
    )
    defaults.update(overrides)
    vc = VirtualContract(**defaults)
    session.add(vc)
    if flush:
        session.flush()
    return vc


def create_logistics(session, vc_id, flush=True, **overrides):
    """创建 Logistics"""
    from models import Logistics
    defaults = dict(virtual_contract_id=vc_id, status="待发货", finance_triggered=False)
    defaults.update(overrides)
    log = Logistics(**defaults)
    session.add(log)
    if flush:
        session.flush()
    return log


def create_express_order(session, logistics_id, flush=True, **overrides):
    """创建 ExpressOrder"""
    from models import ExpressOrder
    defaults = dict(
        logistics_id=logistics_id,
        tracking_number="SF123456",
        items={"items": []},
        address_info={"address": "测试地址"},
        status="待发货",
    )
    defaults.update(overrides)
    eo = ExpressOrder(**defaults)
    session.add(eo)
    if flush:
        session.flush()
    return eo


def create_finance_account(session, flush=True, **overrides):
    """创建 FinanceAccount"""
    from models import FinanceAccount
    defaults = dict(
        category="资产",
        level1_name="银行存款",
        level2_name="测试账户",
        direction="借",
    )
    defaults.update(overrides)
    fa = FinanceAccount(**defaults)
    session.add(fa)
    if flush:
        session.flush()
    return fa


def create_financial_journal(session, account_id, flush=True, **overrides):
    """创建 FinancialJournal"""
    from models import FinancialJournal
    defaults = dict(
        voucher_no="VOU-001",
        account_id=account_id,
        debit=0.0,
        credit=0.0,
        ref_type="CashFlow",
        ref_id=1,
        transaction_date=datetime.now(),
    )
    defaults.update(overrides)
    fj = FinancialJournal(**defaults)
    session.add(fj)
    if flush:
        session.flush()
    return fj


def create_cash_flow(session, vc_id, flush=True, **overrides):
    """创建 CashFlow"""
    from models import CashFlow
    defaults = dict(
        virtual_contract_id=vc_id,
        type="预付",
        amount=1000.0,
        finance_triggered=False,
    )
    defaults.update(overrides)
    cf = CashFlow(**defaults)
    session.add(cf)
    if flush:
        session.flush()
    return cf
