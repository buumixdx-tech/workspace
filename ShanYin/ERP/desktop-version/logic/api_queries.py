"""
API 层专用查询函数（Session-based）

本模块提供所有 API 路由需要的查询函数，遵循 CQRS 模式。
所有函数接受 session 参数，不自行管理 session 生命周期。
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import func, and_, or_, exists
from sqlalchemy.orm import Session, selectinload

from models import (
    ChannelCustomer, Point, Supplier, SKU, ExternalPartner, BankAccount,
    Business, VirtualContract, VirtualContractStatusLog, CashFlow,
    Logistics, ExpressOrder, SupplyChain, SupplyChainItem,
    TimeRule, SystemEvent, MaterialInventory, EquipmentInventory,
    PartnerRelation, SKU as SKUModel, Point as PointModel,
)
from logic.constants import VCStatus


# =============================================================================
# Master Data Queries
# =============================================================================

def list_customers(session: Session, ids: Optional[List[int]] = None,
                   search: Optional[str] = None, page: int = 1, size: int = 50
                   ) -> Dict[str, Any]:
    q = session.query(ChannelCustomer)
    if ids:
        q = q.filter(ChannelCustomer.id.in_(ids))
    if search:
        q = q.filter(ChannelCustomer.name.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(ChannelCustomer.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_customer_to_dict(c) for c in items], "total": total, "page": page, "size": size}


def get_customer(session: Session, cid: int) -> Optional[Dict[str, Any]]:
    obj = session.query(ChannelCustomer).get(cid)
    return _customer_to_dict(obj) if obj else None


def suggest_customers(session: Session, q: str, limit: int = 10) -> List[Dict[str, Any]]:
    items = session.query(ChannelCustomer).filter(
        ChannelCustomer.name.ilike(f"%{q}%")
    ).order_by(ChannelCustomer.id.desc()).limit(limit).all()
    return [{"id": c.id, "name": c.name} for c in items]


def _customer_to_dict(c: ChannelCustomer) -> Dict[str, Any]:
    if c is None:
        return {}
    return {"id": c.id, "name": c.name, "info": c.info or {}, "status": getattr(c, 'status', None)}


def list_points(session: Session, ids: Optional[List[int]] = None,
                customer_id: Optional[int] = None, supplier_id: Optional[int] = None,
                type: Optional[str] = None, search: Optional[str] = None,
                page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(Point)
    if ids:
        q = q.filter(Point.id.in_(ids))
    if customer_id is not None:
        q = q.filter(Point.customer_id == customer_id)
    if supplier_id is not None:
        q = q.filter(Point.supplier_id == supplier_id)
    if type:
        q = q.filter(Point.type == type)
    if search:
        q = q.filter(or_(Point.name.ilike(f"%{search}%"), Point.address.ilike(f"%{search}%")))
    total = q.count()
    items = q.order_by(Point.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_point_to_dict(p) for p in items], "total": total, "page": page, "size": size}


def get_point(session: Session, pid: int) -> Optional[Dict[str, Any]]:
    obj = session.query(Point).get(pid)
    return _point_to_dict(obj) if obj else None


def suggest_points(session: Session, q: str, limit: int = 10) -> List[Dict[str, Any]]:
    items = session.query(Point).filter(Point.name.ilike(f"%{q}%")).order_by(Point.id.desc()).limit(limit).all()
    return [{"id": p.id, "name": p.name, "type": p.type} for p in items]


def _point_to_dict(p: Point) -> Dict[str, Any]:
    if p is None:
        return {}
    return {"id": p.id, "name": p.name, "type": p.type, "address": p.address,
            "customer_id": p.customer_id, "supplier_id": p.supplier_id}


def list_suppliers(session: Session, ids: Optional[List[int]] = None,
                   category: Optional[str] = None, search: Optional[str] = None,
                   page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(Supplier)
    if ids:
        q = q.filter(Supplier.id.in_(ids))
    if category:
        q = q.filter(Supplier.category == category)
    if search:
        q = q.filter(or_(Supplier.name.ilike(f"%{search}%"), Supplier.address.ilike(f"%{search}%")))
    total = q.count()
    items = q.order_by(Supplier.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_supplier_to_dict(s) for s in items], "total": total, "page": page, "size": size}


def get_supplier(session: Session, sid: int) -> Optional[Dict[str, Any]]:
    obj = session.query(Supplier).get(sid)
    return _supplier_to_dict(obj) if obj else None


def suggest_suppliers(session: Session, q: str, category: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    qry = session.query(Supplier).filter(or_(Supplier.name.ilike(f"%{q}%"), Supplier.address.ilike(f"%{q}%")))
    if category:
        qry = qry.filter(Supplier.category == category)
    items = qry.order_by(Supplier.id.desc()).limit(limit).all()
    return [{"id": s.id, "name": s.name, "category": s.category} for s in items]


def _supplier_to_dict(s: Supplier) -> Dict[str, Any]:
    if s is None:
        return {}
    return {"id": s.id, "name": s.name, "category": s.category, "address": s.address,
            "info": getattr(s, 'info', None) or getattr(s, 'contact_info', None) or {}}


def list_skus(session: Session, ids: Optional[List[int]] = None, supplier_id: Optional[int] = None,
              type_level1: Optional[str] = None, search: Optional[str] = None,
              page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(SKU)
    if ids:
        q = q.filter(SKU.id.in_(ids))
    if supplier_id is not None:
        q = q.filter(SKU.supplier_id == supplier_id)
    if type_level1:
        q = q.filter(SKU.type_level1 == type_level1)
    if search:
        q = q.filter(SKU.name.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(SKU.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_sku_to_dict(s) for s in items], "total": total, "page": page, "size": size}


def get_sku(session: Session, sku_id: int) -> Optional[Dict[str, Any]]:
    obj = session.query(SKU).get(sku_id)
    return _sku_to_dict(obj) if obj else None


def suggest_skus(session: Session, q: str, type_level1: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    qry = session.query(SKU).filter(SKU.name.ilike(f"%{q}%"))
    if type_level1:
        qry = qry.filter(SKU.type_level1 == type_level1)
    items = qry.order_by(SKU.id.desc()).limit(limit).all()
    return [{"id": s.id, "name": s.name, "type_level1": s.type_level1} for s in items]


def _sku_to_dict(s: SKU) -> Dict[str, Any]:
    if s is None:
        return {}
    return {"id": s.id, "name": s.name, "type_level1": s.type_level1, "type_level2": getattr(s, 'type_level2', None),
            "model": getattr(s, 'model', None), "params": s.params or {}, "supplier_id": s.supplier_id}


def list_partners(session: Session, ids: Optional[List[int]] = None,
                  type: Optional[str] = None, search: Optional[str] = None,
                  page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(ExternalPartner)
    if ids:
        q = q.filter(ExternalPartner.id.in_(ids))
    if type:
        q = q.filter(ExternalPartner.type == type)
    if search:
        q = q.filter(or_(ExternalPartner.name.ilike(f"%{search}%"), ExternalPartner.address.ilike(f"%{search}%")))
    total = q.count()
    items = q.order_by(ExternalPartner.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_partner_to_dict(p) for p in items], "total": total, "page": page, "size": size}


def get_partner(session: Session, pid: int) -> Optional[Dict[str, Any]]:
    obj = session.query(ExternalPartner).get(pid)
    return _partner_to_dict(obj) if obj else None


def suggest_partners(session: Session, q: str, type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    qry = session.query(ExternalPartner).filter(or_(ExternalPartner.name.ilike(f"%{q}%"), ExternalPartner.address.ilike(f"%{q}%")))
    if type:
        qry = qry.filter(ExternalPartner.type == type)
    items = qry.order_by(ExternalPartner.id.desc()).limit(limit).all()
    return [{"id": p.id, "name": p.name, "type": p.type} for p in items]


def _partner_to_dict(p: ExternalPartner) -> Dict[str, Any]:
    if p is None:
        return {}
    return {"id": p.id, "name": p.name, "type": p.type, "address": p.address,
            "contact_info": getattr(p, 'contact_info', None), "content": getattr(p, 'content', None)}


def list_bank_accounts(session: Session, ids: Optional[List[int]] = None,
                       owner_type: Optional[str] = None, owner_id: Optional[int] = None,
                       search: Optional[str] = None, page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(BankAccount)
    if ids:
        q = q.filter(BankAccount.id.in_(ids))
    if owner_type:
        q = q.filter(BankAccount.owner_type == owner_type)
        if owner_type != 'ourselves' and owner_id is not None:
            q = q.filter(BankAccount.owner_id == owner_id)
    elif owner_id is not None:
        q = q.filter(BankAccount.owner_id == owner_id)
    if search:
        q = q.filter(BankAccount.account_info.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(BankAccount.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_bank_account_to_dict(a) for a in items], "total": total, "page": page, "size": size}


def get_bank_account(session: Session, account_id: int) -> Optional[Dict[str, Any]]:
    obj = session.query(BankAccount).get(account_id)
    return _bank_account_to_dict(obj) if obj else None


def suggest_bank_accounts(session: Session, q: str, owner_type: Optional[str] = None,
                          owner_id: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
    qry = session.query(BankAccount).filter(BankAccount.account_info.ilike(f"%{q}%"))
    if owner_type:
        qry = qry.filter(BankAccount.owner_type == owner_type)
    if owner_id is not None:
        qry = qry.filter(BankAccount.owner_id == owner_id)
    items = qry.order_by(BankAccount.id.desc()).limit(limit).all()
    return [{"id": a.id, "account_info": a.account_info, "owner_type": a.owner_type, "owner_id": a.owner_id} for a in items]


def _bank_account_to_dict(a: BankAccount) -> Dict[str, Any]:
    if a is None:
        return {}
    return {"id": a.id, "account_info": getattr(a, 'account_info', None), "owner_type": a.owner_type,
            "owner_id": a.owner_id, "is_default": getattr(a, 'is_default', None)}


# =============================================================================
# Business Queries
# =============================================================================

def list_businesses(session: Session, ids: Optional[List[int]] = None,
                    customer_id: Optional[int] = None, customer_ids: Optional[List[int]] = None,
                    status: Optional[str] = None, date_from: Optional[str] = None,
                    date_to: Optional[str] = None, search: Optional[str] = None,
                    page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(Business)
    if ids:
        q = q.filter(Business.id.in_(ids))
    if customer_id is not None:
        q = q.filter(Business.customer_id == customer_id)
    if customer_ids:
        q = q.filter(Business.customer_id.in_(customer_ids))
    if status:
        q = q.filter(Business.status == status)
    if date_from:
        q = q.filter(Business.timestamp >= date_from)
    if date_to:
        q = q.filter(Business.timestamp <= date_to)
    if search:
        q = q.join(ChannelCustomer, Business.customer_id == ChannelCustomer.id).filter(
            ChannelCustomer.name.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(Business.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_business_to_dict(b) for b in items], "total": total, "page": page, "size": size}


def get_business(session: Session, bid: int) -> Optional[Dict[str, Any]]:
    biz = session.query(Business).get(bid)
    if not biz:
        return None
    vcs = session.query(VirtualContract).filter(VirtualContract.business_id == bid).all()
    data = _business_to_dict(biz)
    data["virtual_contracts"] = [{"id": c.id, "type": c.type, "status": c.status,
                                   "total_amount": (c.elements or {}).get("total_amount", 0) if c.elements else 0} for c in vcs]
    return data


def _business_to_dict(b: Business) -> Dict[str, Any]:
    if b is None:
        return {}
    return {"id": b.id, "customer_id": b.customer_id, "status": b.status,
            "details": b.details or {}, "timestamp": b.timestamp.isoformat() if b.timestamp else None}


# =============================================================================
# Virtual Contract Queries
# =============================================================================

def list_vcs(session: Session, ids: Optional[List[int]] = None, business_id: Optional[int] = None,
             type: Optional[str] = None, status: Optional[str] = None,
             cash_status: Optional[str] = None, subject_status: Optional[str] = None,
             date_from: Optional[str] = None, date_to: Optional[str] = None,
             search: Optional[str] = None, page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(VirtualContract)
    if ids:
        q = q.filter(VirtualContract.id.in_(ids))
    if business_id is not None:
        q = q.filter(VirtualContract.business_id == business_id)
    if type:
        q = q.filter(VirtualContract.type == type)
    if status:
        q = q.filter(VirtualContract.status == status)
    if cash_status:
        q = q.filter(VirtualContract.cash_status == cash_status)
    if subject_status:
        q = q.filter(VirtualContract.subject_status == subject_status)
    if date_from or date_to:
        created_log = session.query(
            VirtualContractStatusLog.vc_id,
            func.min(VirtualContractStatusLog.timestamp).label('created_time')
        ).filter(
            VirtualContractStatusLog.category == 'status',
            VirtualContractStatusLog.status_name == VCStatus.EXE
        ).group_by(VirtualContractStatusLog.vc_id).subquery()
        q = q.join(created_log, VirtualContract.id == created_log.c.vc_id)
        if date_from:
            q = q.filter(func.date(created_log.c.created_time) >= date_from)
        if date_to:
            q = q.filter(func.date(created_log.c.created_time) <= date_to)
    if search:
        q = q.filter(VirtualContract.description.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(VirtualContract.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_vc_to_dict(v) for v in items], "total": total, "page": page, "size": size}


def get_vc(session: Session, vc_id: int) -> Optional[Dict[str, Any]]:
    vc = session.query(VirtualContract).options(
        selectinload(VirtualContract.status_logs),
        selectinload(VirtualContract.logistics),
        selectinload(VirtualContract.cash_flows),
    ).get(vc_id)
    if not vc:
        return None
    data = _vc_to_dict(vc)
    data["status_logs"] = [{"id": l.id, "category": l.category, "status_name": l.status_name,
                              "timestamp": l.timestamp.isoformat() if l.timestamp else None} for l in vc.status_logs]
    data["logistics"] = [{"id": l.id, "status": l.status, "timestamp": l.timestamp.isoformat() if l.timestamp else None} for l in vc.logistics]
    data["cash_flows"] = [{"id": c.id, "type": c.type, "amount": c.amount,
                             "transaction_date": c.transaction_date.isoformat() if c.transaction_date else None} for c in vc.cash_flows]
    return data


def _vc_to_dict(v: VirtualContract) -> Dict[str, Any]:
    if v is None:
        return {}
    return {"id": v.id, "business_id": v.business_id, "type": v.type, "status": v.status,
            "cash_status": v.cash_status, "subject_status": v.subject_status,
            "description": v.description, "elements": v.elements or {},
            "deposit_info": v.deposit_info or {}, "supply_chain_id": v.supply_chain_id,
            "related_vc_id": v.related_vc_id,
            "status_timestamp": v.status_timestamp.isoformat() if v.status_timestamp else None}


# =============================================================================
# Logistics Queries
# =============================================================================

def list_logistics(session: Session, ids: Optional[List[int]] = None, vc_id: Optional[int] = None,
                   status: Optional[str] = None, date_from: Optional[str] = None,
                   date_to: Optional[str] = None, tracking_number: Optional[str] = None,
                   page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(Logistics)
    if ids:
        q = q.filter(Logistics.id.in_(ids))
    if vc_id is not None:
        q = q.filter(Logistics.virtual_contract_id == vc_id)
    if status:
        q = q.filter(Logistics.status == status)
    if date_from:
        q = q.filter(Logistics.timestamp >= date_from)
    if date_to:
        q = q.filter(Logistics.timestamp <= date_to)
    if tracking_number:
        subq = exists().where(
            and_(
                ExpressOrder.logistics_id == Logistics.id,
                ExpressOrder.tracking_number.ilike(f"%{tracking_number}%")
            )
        )
        q = q.filter(subq)
    total = q.count()
    items = q.order_by(Logistics.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_logistics_to_dict(l) for l in items], "total": total, "page": page, "size": size}


def get_logistics(session: Session, log_id: int) -> Optional[Dict[str, Any]]:
    log = session.query(Logistics).options(selectinload(Logistics.express_orders)).get(log_id)
    if not log:
        return None
    data = _logistics_to_dict(log)
    data["express_orders"] = [{"id": e.id, "tracking_number": e.tracking_number, "status": e.status,
                                 "address_info": e.address_info, "items": e.items} for e in log.express_orders]
    return data


def _logistics_to_dict(l: Logistics) -> Dict[str, Any]:
    if l is None:
        return {}
    return {"id": l.id, "virtual_contract_id": l.virtual_contract_id, "status": l.status,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None}


# =============================================================================
# Finance Queries
# =============================================================================

def list_cashflows(session: Session, ids: Optional[List[int]] = None,
                   vc_id: Optional[int] = None, vc_ids: Optional[List[int]] = None,
                   type: Optional[str] = None, payer_id: Optional[int] = None,
                   payee_id: Optional[int] = None, date_from: Optional[str] = None,
                   date_to: Optional[str] = None, amount_min: Optional[float] = None,
                   amount_max: Optional[float] = None, page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(CashFlow)
    if ids:
        q = q.filter(CashFlow.id.in_(ids))
    if vc_id is not None:
        q = q.filter(CashFlow.virtual_contract_id == vc_id)
    if vc_ids:
        q = q.filter(CashFlow.virtual_contract_id.in_(vc_ids))
    if type:
        q = q.filter(CashFlow.type == type)
    if payer_id is not None:
        q = q.filter(CashFlow.payer_account_id == payer_id)
    if payee_id is not None:
        q = q.filter(CashFlow.payee_account_id == payee_id)
    if date_from:
        q = q.filter(CashFlow.transaction_date >= date_from)
    if date_to:
        q = q.filter(CashFlow.transaction_date <= date_to)
    if amount_min is not None:
        q = q.filter(CashFlow.amount >= amount_min)
    if amount_max is not None:
        q = q.filter(CashFlow.amount <= amount_max)
    total = q.count()
    items = q.order_by(CashFlow.transaction_date.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_cashflow_to_dict(c) for c in items], "total": total, "page": page, "size": size}


def get_cashflow(session: Session, cf_id: int) -> Optional[Dict[str, Any]]:
    obj = session.query(CashFlow).get(cf_id)
    return _cashflow_to_dict(obj) if obj else None


def _cashflow_to_dict(c: CashFlow) -> Dict[str, Any]:
    if c is None:
        return {}
    return {"id": c.id, "virtual_contract_id": c.virtual_contract_id, "type": c.type,
            "amount": c.amount, "payer_account_id": c.payer_account_id,
            "payee_account_id": c.payee_account_id,
            "transaction_date": c.transaction_date.isoformat() if c.transaction_date else None,
            "description": c.description}


# =============================================================================
# Supply Chain Queries
# =============================================================================

def list_supply_chains(session: Session, ids: Optional[List[int]] = None,
                       supplier_id: Optional[int] = None, supplier_ids: Optional[List[int]] = None,
                       status: Optional[str] = None, type: Optional[str] = None,
                       date_from: Optional[str] = None, date_to: Optional[str] = None,
                       search: Optional[str] = None, page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(SupplyChain)
    if ids:
        q = q.filter(SupplyChain.id.in_(ids))
    if supplier_id is not None:
        q = q.filter(SupplyChain.supplier_id == supplier_id)
    if supplier_ids:
        q = q.filter(SupplyChain.supplier_id.in_(supplier_ids))
    if status:
        q = q.filter(SupplyChain.status == status)
    if type:
        q = q.filter(SupplyChain.type == type)
    if date_from or date_to:
        created_event = session.query(
            SystemEvent.aggregate_id,
            func.min(SystemEvent.created_at).label('created_time')
        ).filter(
            SystemEvent.event_type == 'SUPPLY_CHAIN_CREATED',
            SystemEvent.aggregate_type == 'SUPPLY_CHAIN'
        ).group_by(SystemEvent.aggregate_id).subquery()
        q = q.join(created_event, SupplyChain.id == created_event.c.aggregate_id)
        if date_from:
            q = q.filter(func.date(created_event.c.created_time) >= date_from)
        if date_to:
            q = q.filter(func.date(created_event.c.created_time) <= date_to)
    if search:
        q = q.join(Supplier, SupplyChain.supplier_id == Supplier.id).filter(
            Supplier.name.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(SupplyChain.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_sc_to_dict(s) for s in items], "total": total, "page": page, "size": size}


def get_supply_chain(session: Session, sc_id: int) -> Optional[Dict[str, Any]]:
    sc = session.query(SupplyChain).get(sc_id)
    if not sc:
        return None
    data = _sc_to_dict(sc)
    items = session.query(SupplyChainItem).filter(SupplyChainItem.supply_chain_id == sc_id).all()
    data["items"] = [{"id": i.id, "sku_id": i.sku_id, "price": i.price} for i in items]
    return data


def _sc_to_dict(s: SupplyChain) -> Dict[str, Any]:
    if s is None:
        return {}
    return {"id": s.id, "supplier_id": s.supplier_id, "type": s.type, "status": s.status,
            "payment_terms": s.payment_terms or {},
            "contract_id": s.contract_id}


# =============================================================================
# Time Rule Queries
# =============================================================================

def list_rules(session: Session, ids: Optional[List[int]] = None, related_id: Optional[int] = None,
               related_type: Optional[str] = None, status: Optional[str] = None,
               date_from: Optional[str] = None, date_to: Optional[str] = None,
               page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(TimeRule)
    if ids:
        q = q.filter(TimeRule.id.in_(ids))
    if related_id is not None:
        q = q.filter(TimeRule.related_id == related_id)
    if related_type:
        q = q.filter(TimeRule.related_type == related_type)
    if status:
        q = q.filter(TimeRule.status == status)
    if date_from:
        q = q.filter(TimeRule.created_at >= date_from)
    if date_to:
        q = q.filter(TimeRule.created_at <= date_to)
    total = q.count()
    items = q.order_by(TimeRule.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_rule_to_dict(r) for r in items], "total": total, "page": page, "size": size}


def get_rule(session: Session, rule_id: int) -> Optional[Dict[str, Any]]:
    obj = session.query(TimeRule).get(rule_id)
    return _rule_to_dict(obj) if obj else None


def _rule_to_dict(r: TimeRule) -> Dict[str, Any]:
    if r is None:
        return {}
    return {"id": r.id, "related_id": r.related_id, "related_type": r.related_type,
            "party": r.party, "trigger_event": r.trigger_event, "target_event": r.target_event,
            "offset": r.offset, "unit": r.unit, "direction": r.direction,
            "status": r.status, "flag_time": r.flag_time.isoformat() if r.flag_time else None,
            "created_at": r.created_at.isoformat() if r.created_at else None}


# =============================================================================
# Inventory Queries
# =============================================================================

def list_equipment(session: Session, vc_id: Optional[int] = None, point_id: Optional[int] = None,
                  sku_id: Optional[int] = None, operational_status: Optional[str] = None,
                  device_status: Optional[str] = None, sn: Optional[str] = None,
                  deposit_amount_min: Optional[float] = None, deposit_amount_max: Optional[float] = None,
                  page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(EquipmentInventory)
    if vc_id is not None:
        q = q.filter(EquipmentInventory.virtual_contract_id == vc_id)
    if point_id is not None:
        q = q.filter(EquipmentInventory.point_id == point_id)
    if sku_id is not None:
        q = q.filter(EquipmentInventory.sku_id == sku_id)
    if operational_status:
        q = q.filter(EquipmentInventory.operational_status == operational_status)
    if device_status:
        q = q.filter(EquipmentInventory.device_status == device_status)
    if sn:
        q = q.filter(EquipmentInventory.sn.ilike(f"%{sn}%"))
    if deposit_amount_min is not None:
        q = q.filter(EquipmentInventory.deposit_amount >= deposit_amount_min)
    if deposit_amount_max is not None:
        q = q.filter(EquipmentInventory.deposit_amount <= deposit_amount_max)
    total = q.count()
    items = q.order_by(EquipmentInventory.id.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_equipment_to_dict(e) for e in items], "total": total, "page": page, "size": size}


def _equipment_to_dict(e: EquipmentInventory) -> Dict[str, Any]:
    if e is None:
        return {}
    return {"id": e.id, "vc_id": e.virtual_contract_id, "point_id": e.point_id,
            "sku_id": e.sku_id, "sn": e.sn, "operational_status": e.operational_status,
            "device_status": e.device_status, "deposit_amount": e.deposit_amount}


def list_material(session: Session, sku_id: Optional[int] = None,
                  warehouse_point_id: Optional[int] = None,
                  page: int = 1, size: int = 50) -> Dict[str, Any]:
    """物料库存查询，支持数据库级分页。"""
    # 先构建基础查询
    q = session.query(MaterialInventory).filter(MaterialInventory.qty > 0)
    if sku_id is not None:
        q = q.filter(MaterialInventory.sku_id == sku_id)
    if warehouse_point_id is not None:
        q = q.filter(MaterialInventory.point_id == warehouse_point_id)

    # 总数（分页前）
    total = q.count()

    # 数据库级分页
    items = q.order_by(MaterialInventory.id.desc()).offset((page - 1) * size).limit(size).all()

    # 收集需要关联的 sku_id / point_id
    s_ids = list(set(i.sku_id for i in items if i.sku_id))
    p_ids = list(set(i.point_id for i in items if i.point_id))
    sku_map = {s.id: s for s in session.query(SKUModel).filter(SKUModel.id.in_(s_ids)).all()} if s_ids else {}
    pt_map = {p.id: p for p in session.query(PointModel).filter(PointModel.id.in_(p_ids)).all()} if p_ids else {}

    result = []
    for b in items:
        sku = sku_map.get(b.sku_id)
        pt = pt_map.get(b.point_id)
        result.append({
            "id": b.id,
            "sku_id": b.sku_id,
            "sku_name": sku.name if sku else "未知",
            "batch_no": b.batch_no,
            "warehouse_point_id": b.point_id,
            "warehouse_point_name": pt.name if pt else f"点位{b.point_id}",
            "quantity": b.qty,
            "average_price": float(sku.params.get("average_price", 0.0)) if sku and sku.params else 0.0,
            "vc_id": b.latest_purchase_vc_id
        })
    return {"items": result, "total": total, "page": page, "size": size}


# =============================================================================
# Partner Relations Queries
# =============================================================================

def list_partner_relations(session: Session, partner_id: Optional[int] = None,
                           owner_type: Optional[str] = None, owner_id: Optional[int] = None,
                           relation_type: Optional[str] = None) -> Dict[str, Any]:
    q = session.query(PartnerRelation)
    if partner_id is not None:
        q = q.filter(PartnerRelation.partner_id == partner_id)
    if owner_type is not None:
        q = q.filter(PartnerRelation.owner_type == owner_type)
    if owner_id is not None:
        q = q.filter(PartnerRelation.owner_id == owner_id)
    if relation_type is not None:
        q = q.filter(PartnerRelation.relation_type == relation_type)
    items = q.order_by(PartnerRelation.id.desc()).all()
    # 批量加载合作方名称
    p_ids = list(set(r.partner_id for r in items if r.partner_id))
    p_map = {p.id: p.name for p in session.query(ExternalPartner).filter(ExternalPartner.id.in_(p_ids)).all()} if p_ids else {}
    result = [{"id": r.id, "partner_id": r.partner_id,
                "partner_name": p_map.get(r.partner_id, ""),
                "owner_type": r.owner_type, "owner_id": r.owner_id,
                "relation_type": r.relation_type,
                "remark": r.remark,
                "established_at": r.established_at.isoformat() if r.established_at else None,
                "ended_at": r.ended_at.isoformat() if r.ended_at else None} for r in items]
    return {"items": result, "total": len(result), "page": 1, "size": len(result)}


# =============================================================================
# Events Queries
# =============================================================================

def list_recent_events(session: Session, limit: int = 50, since_id: int = 0) -> Dict[str, Any]:
    events = session.query(SystemEvent).filter(
        SystemEvent.id > since_id
    ).order_by(SystemEvent.id.desc()).limit(limit).all()
    items = [{
        "id": e.id, "event_type": e.event_type, "aggregate_type": e.aggregate_type,
        "aggregate_id": e.aggregate_id, "payload": e.payload,
        "created_at": e.created_at.isoformat() if e.created_at else None
    } for e in reversed(events)]
    return {"items": items, "latest_id": events[0].id if events else since_id}


def mark_events_pushed(session: Session, event_ids: List[int]) -> None:
    if event_ids:
        session.query(SystemEvent).filter(SystemEvent.id.in_(event_ids)).update(
            {"pushed_to_ai": True}, synchronize_session=False
        )
