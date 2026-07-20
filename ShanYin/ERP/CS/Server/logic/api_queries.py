"""
API 层专用查询函数（Session-based）

本模块提供所有 API 路由需要的查询函数，遵循 CQRS 模式。
所有函数接受 session 参数，不自行管理 session 生命周期。
"""

import json
from typing import Any, Dict, List, Optional
from sqlalchemy import func, and_, or_, exists, text
from sqlalchemy.orm import Session, selectinload

from models import (
    ChannelCustomer, Point, Supplier, SKU, ExternalPartner, BankAccount,
    Business, VirtualContract, VirtualContractStatusLog, CashFlow,
    Logistics, ExpressOrder, SupplyChain, SupplyChainItem,
    TimeRule, SystemEvent, MaterialInventory, EquipmentInventory,
    PartnerRelation, SKU as SKUModel, Point as PointModel,
    AddonBusiness,
)
from logic.constants import VCStatus
from logic.master import get_partner_relations


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
    # 获取归属名称
    owner_name = None
    owner_type = None
    if p.customer:
        owner_name = p.customer.name
        owner_type = "客户"
    elif p.supplier:
        owner_name = p.supplier.name
        owner_type = "供应商"
    return {"id": p.id, "name": p.name, "type": p.type, "address": p.address,
            "customer_id": p.customer_id, "supplier_id": p.supplier_id,
            "owner_name": owner_name, "owner_type": owner_type}


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
    info = getattr(a, 'account_info', None) or {}
    return {"id": a.id, "account_info": info, "owner_type": a.owner_type,
            "owner_id": a.owner_id, "is_default": getattr(a, 'is_default', None),
            "bank_name": info.get("银行名称", ""),
            "account_no": info.get("银行账号", ""),
            "owner_name": info.get("开户名称", "")}


# =============================================================================
# Business Queries
# =============================================================================

def list_businesses(session: Session, ids: Optional[List[int]] = None,
                    customer_id: Optional[int] = None, customer_ids: Optional[List[int]] = None,
                    status: Optional[str] = None, date_from: Optional[str] = None,
                    date_to: Optional[str] = None, customer_name_kw: Optional[str] = None,
                    sku_name_kw: Optional[str] = None,
                    page: int = 1, size: int = 50) -> Dict[str, Any]:
    q = session.query(Business).options(selectinload(Business.customer))
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
    if customer_name_kw:
        q = q.join(ChannelCustomer, Business.customer_id == ChannelCustomer.id).filter(
            ChannelCustomer.name.ilike(f"%{customer_name_kw}%"))
    if sku_name_kw:
        # 先找到名称匹配的 SKU IDs
        matching_sku_ids = [s.id for s in session.query(SKUModel).filter(
            SKUModel.name.ilike(f"%{sku_name_kw}%")
        ).all()]
        if not matching_sku_ids:
            q = q.filter(Business.id.in_([-1]))  # no match
        else:
            # 用 text() + json_each 检查 business.details['pricing'] 里是否有匹配的 SKU ID key
            sku_id_conditions = " OR ".join(
                f"business.details->'pricing'->>'{sid}' IS NOT NULL" for sid in matching_sku_ids
            )
            q = q.filter(
                Business.details.isnot(None),
                text(f"({sku_id_conditions})")
            )
    total = q.count()
    if size and size > 0:
        items = q.order_by(Business.id.desc()).offset((page - 1) * size).limit(size).all()
    else:
        items = q.order_by(Business.id.desc()).all()
    return {"items": [_business_to_dict(b) for b in items], "total": total, "page": page, "size": size}


def get_business(session: Session, bid: int) -> Optional[Dict[str, Any]]:
    biz = session.query(Business).options(selectinload(Business.customer)).get(bid)
    if not biz:
        return None
    vcs = session.query(VirtualContract).filter(VirtualContract.business_id == bid).all()
    data = _business_to_dict(biz)
    data["virtual_contracts"] = [{"id": c.id, "type": c.type, "status": c.status,
                                   "total_amount": (c.elements or {}).get("total_amount", 0) if c.elements else 0} for c in vcs]
    data["partners"] = get_partner_relations(
        owner_type="business",
        owner_id=bid,
        active_only=True
    )
    return data


def _business_to_dict(b: Business) -> Dict[str, Any]:
    if b is None:
        return {}
    return {"id": b.id, "customer_id": b.customer_id, "status": b.status,
            "details": b.details or {}, "created_at": b.timestamp.isoformat() if b.timestamp else None,
            "customer_name": b.customer.name if b.customer else None}


# =============================================================================
# Virtual Contract Queries
# =============================================================================

def list_vcs(session: Session, ids: Optional[List[int]] = None, business_id: Optional[int] = None,
             type: Optional[str] = None, status: Optional[str] = None,
             cash_status: Optional[str] = None, subject_status: Optional[str] = None,
             date_from: Optional[str] = None, date_to: Optional[str] = None,
             search: Optional[str] = None, has_logistics: Optional[bool] = None,
             page: int = 1, size: int = 50) -> Dict[str, Any]:
    # Get earliest VC_CREATED event per VC, including payload for transaction_date
    vc_created = session.query(
        SystemEvent.aggregate_id,
        func.min(SystemEvent.created_at).label('created_time')
    ).filter(
        SystemEvent.event_type == 'VC_CREATED',
        SystemEvent.aggregate_type == 'VirtualContract'
    ).group_by(SystemEvent.aggregate_id).subquery()

    vc_event = session.query(
        SystemEvent.payload
    ).filter(
        SystemEvent.event_type == 'VC_CREATED',
        SystemEvent.aggregate_type == 'VirtualContract',
        SystemEvent.aggregate_id == VirtualContract.id
    ).scalar_subquery()

    logistics_subq = session.query(
        Logistics.virtual_contract_id
    ).distinct().subquery()

    q = session.query(
        VirtualContract,
        vc_created.c.created_time,
        vc_event
    ).outerjoin(
        vc_created, VirtualContract.id == vc_created.c.aggregate_id
    ).outerjoin(
        logistics_subq, VirtualContract.id == logistics_subq.c.virtual_contract_id
    )

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
    if date_from:
        q = q.filter(func.date(vc_created.c.created_time) >= date_from)
    if date_to:
        q = q.filter(func.date(vc_created.c.created_time) <= date_to)
    if search:
        q = q.filter(VirtualContract.description.ilike(f"%{search}%"))
    if has_logistics is not None:
        if has_logistics:
            q = q.filter(logistics_subq.c.virtual_contract_id.isnot(None))
        else:
            q = q.filter(logistics_subq.c.virtual_contract_id.is_(None))
    total = q.count()
    items = q.order_by(VirtualContract.id.desc()).offset((page - 1) * size).limit(size).all()

    result = []
    for vc_row in items:
        vc = vc_row[0]
        created_at_val = vc_row[1]
        event_payload = vc_row[2]
        d = _vc_to_dict(vc, session)
        d["created_at"] = created_at_val.isoformat() if created_at_val else None
        tx_date = None
        if event_payload and isinstance(event_payload, dict):
            tx_date = event_payload.get('transaction_date')
        d["transaction_date"] = tx_date
        result.append(d)
    return {"items": result, "total": total, "page": page, "size": size}


def list_vcs_for_overview(session: Session,
                          vc_id: Optional[int] = None,
                          vc_type: Optional[str] = None,
                          vc_status: Optional[str] = None,
                          vc_subject_status: Optional[str] = None,
                          vc_cash_status: Optional[str] = None,
                          business_id: Optional[int] = None,
                          business_customer_name_kw: Optional[str] = None,
                          supply_chain_id: Optional[int] = None,
                          supply_chain_supplier_name_kw: Optional[str] = None,
                          sku_id: Optional[int] = None,
                          sku_name_kw: Optional[str] = None,
                          shipping_point_id: Optional[int] = None,
                          shipping_point_name_kw: Optional[str] = None,
                          receiving_point_id: Optional[int] = None,
                          receiving_point_name_kw: Optional[str] = None,
                          tracking_number: Optional[str] = None,
                          batch_no: Optional[str] = None,
                          vc_date_from: Optional[str] = None,
                          vc_date_to: Optional[str] = None,
                          page: int = 1, size: int = 50) -> Dict[str, Any]:
    from sqlalchemy import cast, String, Integer

    q = session.query(VirtualContract)

    conditions = []

    if vc_id:
        conditions.append(VirtualContract.id == vc_id)
    if vc_type:
        conditions.append(VirtualContract.type == vc_type)
    if vc_status:
        conditions.append(VirtualContract.status == vc_status)
    if vc_subject_status:
        conditions.append(VirtualContract.subject_status == vc_subject_status)
    if vc_cash_status:
        conditions.append(VirtualContract.cash_status == vc_cash_status)

    if business_id:
        conditions.append(VirtualContract.business_id == business_id)
    if business_customer_name_kw:
        conditions.append(
            exists().where(
                VirtualContract.business_id == Business.id,
                Business.customer_id == ChannelCustomer.id,
                ChannelCustomer.name.ilike(f"%{business_customer_name_kw}%")
            )
        )

    if supply_chain_id:
        conditions.append(VirtualContract.supply_chain_id == supply_chain_id)
    if supply_chain_supplier_name_kw:
        conditions.append(
            exists().where(
                VirtualContract.supply_chain_id == SupplyChain.id,
                SupplyChain.supplier_id == Supplier.id,
                Supplier.name.ilike(f"%{supply_chain_supplier_name_kw}%")
            )
        )

    # elements JSON: {"elements": [{"shipping_point_id": ..., "receiving_point_id": ..., "sku_id": ...}]}
    if sku_id:
        conditions.append(
            cast(VirtualContract.elements, String).ilike(f'%\"sku_id\": {sku_id}%')
        )
    if sku_name_kw:
        from sqlalchemy import text
        ids = session.execute(
            text("""
                SELECT DISTINCT v.id FROM virtual_contracts v
                JOIN json_each(v.elements, '$.elements') elem
                JOIN skus s ON s.id = CAST(elem.value->>'$.sku_id' AS INTEGER)
                WHERE s.name LIKE :name
            """),
            {'name': f'%{sku_name_kw}%'}
        ).scalars().all()
        conditions.append(VirtualContract.id.in_(ids))
    if shipping_point_id:
        conditions.append(
            cast(VirtualContract.elements, String).ilike(f'%\"shipping_point_id\": {shipping_point_id}%')
        )
    if shipping_point_name_kw:
        from sqlalchemy import text
        ids = session.execute(
            text("""
                SELECT DISTINCT v.id FROM virtual_contracts v
                JOIN json_each(v.elements, '$.elements') elem
                JOIN points p ON p.id = CAST(elem.value->>'$.shipping_point_id' AS INTEGER)
                WHERE p.name LIKE :name
            """),
            {'name': f'%{shipping_point_name_kw}%'}
        ).scalars().all()
        conditions.append(VirtualContract.id.in_(ids))
    if receiving_point_id:
        conditions.append(
            cast(VirtualContract.elements, String).ilike(f'%\"receiving_point_id\": {receiving_point_id}%')
        )
    if receiving_point_name_kw:
        from sqlalchemy import text
        ids = session.execute(
            text("""
                SELECT DISTINCT v.id FROM virtual_contracts v
                JOIN json_each(v.elements, '$.elements') elem
                JOIN points p ON p.id = CAST(elem.value->>'$.receiving_point_id' AS INTEGER)
                WHERE p.name LIKE :name
            """),
            {'name': f'%{receiving_point_name_kw}%'}
        ).scalars().all()
        conditions.append(VirtualContract.id.in_(ids))

    if batch_no:
        conditions.append(
            cast(VirtualContract.elements, String).ilike(f'%"batch_no": "{batch_no}%')
        )

    if tracking_number:
        conditions.append(
            exists().where(
                Logistics.virtual_contract_id == VirtualContract.id,
                ExpressOrder.logistics_id == Logistics.id,
                ExpressOrder.tracking_number.ilike(f"%{tracking_number}%")
            )
        )

    # 按 VC 业务发生日期过滤
    if vc_date_from:
        conditions.append(VirtualContract.transaction_date >= vc_date_from)
    if vc_date_to:
        conditions.append(VirtualContract.transaction_date <= vc_date_to)

    if conditions:
        q = q.filter(and_(*conditions))

    total = q.count()
    items = q.order_by(VirtualContract.id.desc()).offset((page - 1) * size).limit(size).all()

    result = []
    for vc in items:
        d = _vc_to_dict(vc, session)
        d["transaction_date"] = str(vc.transaction_date) if vc.transaction_date else None
        result.append(d)
    return {"items": result, "total": total, "page": page, "size": size}


def get_vc(session: Session, vc_id: int) -> Optional[Dict[str, Any]]:
    from models import Logistics
    vc = session.query(VirtualContract).options(
        selectinload(VirtualContract.status_logs),
        selectinload(VirtualContract.logistics).selectinload(Logistics.express_orders),
        selectinload(VirtualContract.cash_flows),
    ).get(vc_id)
    if not vc:
        return None
    data = _vc_to_dict(vc, session)
    data["status_logs"] = [{"id": l.id, "category": l.category, "status_name": l.status_name,
                              "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                              "transaction_date": str(l.transaction_date) if l.transaction_date else None} for l in vc.status_logs]

    # Enrich business_name and supply_chain_name
    from models import Business, SupplyChain, Supplier, ChannelCustomer
    if vc.business_id:
        biz = session.query(Business).get(vc.business_id)
        if biz:
            customer = session.query(ChannelCustomer).get(biz.customer_id)
            data["business_name"] = customer.name if customer else None
        else:
            data["business_name"] = None
    else:
        data["business_name"] = None

    if vc.supply_chain_id:
        sc = session.query(SupplyChain).get(vc.supply_chain_id)
        if sc:
            supplier = session.query(Supplier).get(sc.supplier_id)
            data["supply_chain_name"] = supplier.name if supplier else None
        else:
            data["supply_chain_name"] = None
    else:
        data["supply_chain_name"] = None

    # Enrich elements with SKU names
    elements = data.get("elements", {})
    if isinstance(elements, dict):
        elem_list = elements.get("items", []) or elements.get("elements", [])
    else:
        elem_list = []
    if elem_list:
        sku_ids = list(set(e.get("sku_id") for e in elem_list if e.get("sku_id")))
        sku_map = {s.id: s.name for s in session.query(SKUModel).filter(SKUModel.id.in_(sku_ids)).all()} if sku_ids else {}
        for e in elem_list:
            e["sku_name"] = sku_map.get(e.get("sku_id"), f"SKU-{e.get('sku_id')}")

    data["logistics"] = [
        {
            "id": l.id,
            "virtual_contract_id": l.virtual_contract_id,
            "status": l.status,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "express_orders": [
                {
                    "id": o.id,
                    "tracking_number": o.tracking_number,
                    "status": o.status,
                    "items": o.items,
                    "address_info": o.address_info,
                }
                for o in l.express_orders
            ],
        }
        for l in vc.logistics
    ]
    data["cash_flows"] = [{"id": c.id, "type": c.type, "amount": c.amount,
                             "transaction_date": c.transaction_date.isoformat() if c.transaction_date else None} for c in vc.cash_flows]
    return data


def _get_supplier_name(session: Session, supply_chain_id: Optional[int]) -> Optional[str]:
    """根据supply_chain_id获取供应商名称"""
    if not supply_chain_id:
        return None
    sc = session.query(SupplyChain).get(supply_chain_id)
    if sc and sc.supplier_id:
        supplier = session.query(Supplier).get(sc.supplier_id)
        return supplier.name if supplier else None
    return None


def _get_customer_name(session: Session, business_id: Optional[int]) -> Optional[str]:
    """根据business_id获取客户名称"""
    if not business_id:
        return None
    biz = session.query(Business).get(business_id)
    if biz and biz.customer_id:
        cust = session.query(ChannelCustomer).get(biz.customer_id)
        return cust.name if cust else None
    return None


def _get_counterparty(session: Session, vc: VirtualContract) -> str:
    """根据VC类型返回交易对手"""
    vc_type = vc.type
    if vc_type == '设备采购':
        # 供应商 + 客户
        supplier = _get_supplier_name(session, vc.supply_chain_id)
        customer = _get_customer_name(session, vc.business_id)
        parts = [p for p in [supplier, customer] if p]
        return '\n'.join(parts) if parts else '-'
    elif vc_type in ('库存采购', '物料采购'):
        # 供应商
        name = _get_supplier_name(session, vc.supply_chain_id)
        return name or '-'
    elif vc_type in ('物料供应', '库存拨付'):
        # 客户
        name = _get_customer_name(session, vc.business_id)
        return name or '-'
    elif vc_type == '退货':
        # 查原VC的交易对手，根据return_direction决定
        if vc.related_vc_id:
            orig_vc = session.query(VirtualContract).get(vc.related_vc_id)
            if orig_vc:
                if vc.return_direction == 'CUSTOMER_TO_US':
                    return _get_customer_name(session, orig_vc.business_id) or '-'
                elif vc.return_direction == 'US_TO_SUPPLIER':
                    return _get_supplier_name(session, orig_vc.supply_chain_id) or '-'
        return '-'
    return '-'


def _enrich_elements_with_sku_names(elements: Dict[str, Any], session: Session) -> None:
    """Enrich elements with SKU names in-place"""
    # 新数据用 items key，旧数据用 elements key
    if isinstance(elements, dict):
        elem_list = elements.get('items', []) or elements.get('elements', [])
    else:
        elem_list = []
    if elem_list:
        sku_ids = list(set(e.get("sku_id") for e in elem_list if e.get("sku_id")))
        sku_map = {s.id: s.name for s in session.query(SKUModel).filter(SKUModel.id.in_(sku_ids)).all()} if sku_ids else {}
        for e in elem_list:
            e["sku_name"] = sku_map.get(e.get("sku_id"), f"SKU-{e.get('sku_id')}")


def _get_elements_description(vc: VirtualContract) -> str:
    """从elements生成标的描述"""
    elements = vc.elements or {}
    # 新数据用 items key，旧数据用 elements key
    if isinstance(elements, dict):
        items = elements.get('items', []) or elements.get('elements', [])
    else:
        items = []
    if not items:
        return '-'

    lines = []
    for elem in items:
        sku_name = elem.get('sku_name', f'SKU-{elem.get("sku_id")}')
        qty = elem.get('qty', 0)
        batch_no = elem.get('batch_no')
        if batch_no:
            line = f"{sku_name}（{batch_no}）× {qty}"
        else:
            line = f"{sku_name} × {qty}"
        lines.append(line)
    return '\n'.join(lines) if lines else '-'



def _transform_deposit_info(deposit_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Transform deposit_info for API response: rename should_receive -> expected_deposit"""
    if not deposit_info:
        return {}
    result = dict(deposit_info)
    if "should_receive" in result:
        result["expected_deposit"] = result.pop("should_receive")
    return result


def _vc_to_dict(v: VirtualContract, session: Optional[Session] = None) -> Dict[str, Any]:
    if v is None:
        return {}

    elements = v.elements.copy() if v.elements else {}
    # 如果有session，先 enrich elements 中的 SKU 名称，再生成描述
    if session:
        _enrich_elements_with_sku_names(elements, session)

    description = _get_elements_description_from_elements(elements)

    result = {
        "id": v.id, "business_id": v.business_id, "type": v.type, "status": v.status,
        "cash_status": v.cash_status, "subject_status": v.subject_status,
        "description": description, "elements": elements,
        "deposit_info": _transform_deposit_info(v.deposit_info), "supply_chain_id": v.supply_chain_id,
        "related_vc_id": v.related_vc_id,
        "total_amount": elements.get("total_amount", 0) if elements else 0,
        "status_timestamp": v.status_timestamp.isoformat() if v.status_timestamp else None
    }

    # 如果有session，补充交易对手
    if session:
        result["counterparty"] = _get_counterparty(session, v)

    return result


def _get_elements_description_from_elements(elements: Dict[str, Any]) -> str:
    """从已 enriched 的 elements 生成标的描述"""
    # 新数据用 items key，旧数据用 elements key
    if isinstance(elements, dict):
        items = elements.get('items', []) or elements.get('elements', [])
    else:
        items = []
    if not items:
        return '-'

    lines = []
    for elem in items:
        sku_name = elem.get('sku_name', f'SKU-{elem.get("sku_id")}')
        qty = int(elem.get('qty', 0))
        batch_no = elem.get('batch_no')
        if batch_no:
            line = f"{sku_name}（{batch_no}）× {qty}"
        else:
            line = f"{sku_name} × {qty}"
        lines.append(line)
    return '\n'.join(lines) if lines else '-'


# =============================================================================
# Logistics Queries
# =============================================================================

def list_logistics(session: Session, ids: Optional[List[int]] = None, vc_id: Optional[int] = None,
                   status: Optional[str] = None, date_from: Optional[str] = None,
                   date_to: Optional[str] = None, tracking_number: Optional[str] = None,
                   page: int = 1, size: int = 20) -> Dict[str, Any]:
    # Subquery: get LOGISTICS_PLAN_CREATED event payload per logistics
    log_event_subq = session.query(
        SystemEvent.payload
    ).filter(
        SystemEvent.event_type == 'LOGISTICS_PLAN_CREATED',
        SystemEvent.aggregate_type == 'Logistics',
        SystemEvent.aggregate_id == Logistics.id
    ).scalar_subquery()

    q = session.query(
        Logistics,
        log_event_subq
    ).options(selectinload(Logistics.express_orders))
    if ids:
        q = q.filter(Logistics.id.in_(ids))
    if vc_id is not None:
        q = q.filter(Logistics.virtual_contract_id == vc_id)
    if status:
        if status == '待处理':
            q = q.filter(Logistics.status.in_(['待发货', '在途', '签收']))
        else:
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
    result = []
    for row in items:
        l = row[0]
        event_payload = row[1]
        d = _logistics_to_dict(l)
        tx_date = None
        if event_payload and isinstance(event_payload, dict):
            tx_date = event_payload.get('transaction_date')
        d["transaction_date"] = tx_date
        result.append(d)
    return {"items": result, "total": total, "page": page, "size": size}


def get_logistics(session: Session, log_id: int) -> Optional[Dict[str, Any]]:
    log = session.query(Logistics).options(selectinload(Logistics.express_orders)).get(log_id)
    if not log:
        return None
    data = _logistics_to_dict(log)
    # Load transaction_date from LOGISTICS_PLAN_CREATED event
    evt = session.query(SystemEvent).filter(
        SystemEvent.event_type == 'LOGISTICS_PLAN_CREATED',
        SystemEvent.aggregate_type == 'LOGISTICS',
        SystemEvent.aggregate_id == log_id
    ).first()
    if evt and evt.payload and isinstance(evt.payload, dict):
        data["transaction_date"] = evt.payload.get('transaction_date')
    # 收集 express_orders items 中的 sku_id 用于批量查询 SKU 名称
    all_sku_ids = set()
    for e in log.express_orders:
        raw_items = e.items
        if isinstance(raw_items, str):
            try: raw_items = json.loads(raw_items)
            except: raw_items = []
        for it in (raw_items or []):
            sid = it.get("sku_id") if isinstance(it, dict) else None
            if sid:
                all_sku_ids.add(sid)
    sku_map = {s.id: s.name for s in session.query(SKU).filter(SKU.id.in_(all_sku_ids)).all()} if all_sku_ids else {}

    def enrich_items(raw_items):
        items_list = raw_items
        if isinstance(items_list, str):
            try: items_list = json.loads(items_list)
            except: items_list = []
        result = []
        for it in (items_list or []):
            item = dict(it) if isinstance(it, dict) else {}
            sid = item.get("sku_id")
            if sid and not item.get("sku_name"):
                item["sku_name"] = sku_map.get(sid, f"SKU-{sid}")
            result.append(item)
        return result

    data["express_orders"] = [{"id": e.id, "tracking_number": e.tracking_number, "status": e.status,
                                 "address_info": e.address_info, "items": enrich_items(e.items)} for e in log.express_orders]
    # Load VC detail for elements and vc_type
    vc = session.query(VirtualContract).get(log.virtual_contract_id)
    if vc:
        data["vc_type"] = vc.type
        # elements stored as {"elements": [...], "total_amount": ..., "payment_terms": ...}
        elements = (vc.elements or {}).get("items", []) if isinstance(vc.elements, dict) else []
        # Enrich with SKU and Point names
        if elements:
            sku_ids = set(e.get("sku_id") for e in elements if e.get("sku_id"))
            rp_ids = set(e.get("receiving_point_id") for e in elements if e.get("receiving_point_id"))
            sp_ids = set(e.get("shipping_point_id") for e in elements if e.get("shipping_point_id"))
            sku_names = {s.id: s.name for s in session.query(SKU).filter(SKU.id.in_(sku_ids)).all()} if sku_ids else {}
            rp_names = {p.id: p.name for p in session.query(Point).filter(Point.id.in_(rp_ids)).all()} if rp_ids else {}
            sp_names = {p.id: p.name for p in session.query(Point).filter(Point.id.in_(sp_ids)).all()} if sp_ids else {}
            for e in elements:
                e["sku_name"] = sku_names.get(e.get("sku_id"), f"SKU-{e.get('sku_id')}")
                e["receiving_point_name"] = rp_names.get(e.get("receiving_point_id"), f"点位-{e.get('receiving_point_id')}")
                e["shipping_point_name"] = sp_names.get(e.get("shipping_point_id"), f"点位-{e.get('shipping_point_id')}")
        data["elements"] = elements
    return data


def _logistics_to_dict(l: Logistics) -> Dict[str, Any]:
    if l is None:
        return {}
    return {"id": l.id, "virtual_contract_id": l.virtual_contract_id, "status": l.status,
            "created_at": l.timestamp.isoformat() if l.timestamp else None,
            "express_orders_count": len(l.express_orders) if l.express_orders else 0}


# =============================================================================
# Express Order Global Query (Tab 2)
# =============================================================================

def list_express_orders_global(session: Session,
                               ids: Optional[List[int]] = None,
                               tracking_number: Optional[str] = None,
                               status: Optional[str] = None,
                               date_from: Optional[str] = None,
                               date_to: Optional[str] = None,
                               sku_id: Optional[int] = None,
                               sku_name_kw: Optional[str] = None,
                               shipping_point_id: Optional[int] = None,
                               shipping_point_name_kw: Optional[str] = None,
                               receiving_point_id: Optional[int] = None,
                               receiving_point_name_kw: Optional[str] = None,
                               vc_id: Optional[int] = None,
                               vc_type: Optional[str] = None,
                               vc_status_type: Optional[str] = None,
                               vc_status_value: Optional[str] = None,
                               subject_status: Optional[str] = None,
                               business_id: Optional[int] = None,
                               business_customer_name_kw: Optional[str] = None,
                               supply_chain_id: Optional[int] = None,
                               supply_chain_supplier_name_kw: Optional[str] = None,
                               page: int = 1, size: int = 20) -> Dict[str, Any]:
    from sqlalchemy import exists, and_, cast, Integer, String

    q = session.query(ExpressOrder).outerjoin(
        Logistics, ExpressOrder.logistics_id == Logistics.id
    ).outerjoin(
        VirtualContract, Logistics.virtual_contract_id == VirtualContract.id
    )

    conditions = []

    if ids:
        conditions.append(ExpressOrder.id.in_(ids))
    if tracking_number:
        conditions.append(ExpressOrder.tracking_number.ilike(f"%{tracking_number}%"))
    if status:
        conditions.append(ExpressOrder.status == status)
    if date_from:
        conditions.append(ExpressOrder.timestamp >= date_from)
    if date_to:
        conditions.append(ExpressOrder.timestamp <= date_to)

    if sku_id:
        # items is stored as JSON array [{"sku_id": 2, ...}], cast produces JSON double-quote format
        conditions.append(cast(ExpressOrder.items, String).ilike(f'%\"sku_id\": {sku_id}%'))
    if sku_name_kw:
        conditions.append(cast(ExpressOrder.items, String).ilike(f"%{sku_name_kw}%"))

    if shipping_point_id:
        conditions.append(ExpressOrder.address_info.op('->>')('发货点位Id').cast(Integer) == shipping_point_id)
    if shipping_point_name_kw:
        conditions.append(ExpressOrder.address_info.op('->>')('发货点位名称').ilike(f"%{shipping_point_name_kw}%"))
    if receiving_point_id:
        conditions.append(ExpressOrder.address_info.op('->>')('收货点位Id').cast(Integer) == receiving_point_id)
    if receiving_point_name_kw:
        conditions.append(ExpressOrder.address_info.op('->>')('收货点位名称').ilike(f"%{receiving_point_name_kw}%"))

    if vc_id:
        conditions.append(Logistics.virtual_contract_id == vc_id)
    if vc_type:
        conditions.append(VirtualContract.type == vc_type)
    if vc_status_type and vc_status_value:
        if vc_status_type == '主状态':
            conditions.append(VirtualContract.status == vc_status_value)
        elif vc_status_type == '合同状态':
            conditions.append(VirtualContract.subject_status == vc_status_value)
    if subject_status:
        conditions.append(VirtualContract.subject_status == subject_status)

    if business_id:
        conditions.append(VirtualContract.business_id == business_id)
    if business_customer_name_kw:
        conditions.append(
            exists().where(
                VirtualContract.business_id == Business.id,
                Business.customer_id == ChannelCustomer.id,
                ChannelCustomer.name.ilike(f"%{business_customer_name_kw}%")
            )
        )

    if supply_chain_id:
        conditions.append(VirtualContract.supply_chain_id == supply_chain_id)
    if supply_chain_supplier_name_kw:
        conditions.append(
            exists().where(
                VirtualContract.supply_chain_id == SupplyChain.id,
                SupplyChain.supplier_id == Supplier.id,
                Supplier.name.ilike(f"%{supply_chain_supplier_name_kw}%")
            )
        )

    for cond in conditions:
        q = q.filter(cond)

    total = q.count()
    items = q.order_by(ExpressOrder.id.desc()).offset((page - 1) * size).limit(size).all()

    # Batch query EXPRESS_ORDER_CREATED events for transaction_date
    eo_ids = [e.id for e in items]
    eo_event_map = {}
    if eo_ids:
        events = session.query(SystemEvent).filter(
            SystemEvent.event_type == 'EXPRESS_ORDER_CREATED',
            SystemEvent.aggregate_type == 'EXPRESS_ORDER',
            SystemEvent.aggregate_id.in_(eo_ids)
        ).all()
        for ev in events:
            if ev.payload and isinstance(ev.payload, dict):
                eo_event_map[ev.aggregate_id] = ev.payload.get('transaction_date')

    # Enrich
    result = []
    for e in items:
        log = session.query(Logistics).get(e.logistics_id)
        vc = session.query(VirtualContract).get(log.virtual_contract_id) if log else None

        sku_ids = set()
        sp_ids = set()
        rp_ids = set()
        if e.items:
            for item in (e.items if isinstance(e.items, list) else []):
                if isinstance(item, dict) and item.get('sku_id'):
                    sku_ids.add(item['sku_id'])
        if isinstance(e.address_info, dict):
            sp_id = e.address_info.get('发货点位Id')
            rp_id = e.address_info.get('收货点位Id')
            if sp_id:
                sp_ids.add(sp_id)
            if rp_id:
                rp_ids.add(rp_id)

        sku_map = {s.id: s.name for s in session.query(SKU).filter(SKU.id.in_(sku_ids)).all()} if sku_ids else {}
        sp_map = {p.id: p.name for p in session.query(Point).filter(Point.id.in_(sp_ids)).all()} if sp_ids else {}
        rp_map = {p.id: p.name for p in session.query(Point).filter(Point.id.in_(rp_ids)).all()} if rp_ids else {}

        enriched_items = []
        for item in (e.items if isinstance(e.items, list) else []):
            if isinstance(item, dict):
                enriched_items.append({
                    **item,
                    'sku_name': sku_map.get(item.get('sku_id'), item.get('sku_name', f"SKU-{item.get('sku_id')}")),
                })

        result.append({
            'id': e.id,
            'tracking_number': e.tracking_number,
            'status': e.status,
            'created_at': e.timestamp.isoformat() if e.timestamp else None,
            'transaction_date': eo_event_map.get(e.id),
            'logistics_id': e.logistics_id,
            'items': enriched_items,
            'address_info': e.address_info,
            'vc_id': vc.id if vc else None,
            'vc_type': vc.type if vc else None,
            'vc_subject_status': vc.subject_status if vc else None,
        })

    return {"items": result, "total": total, "page": page, "size": size}


# =============================================================================
# Logistics Global Query (Tab 3)
# =============================================================================

def list_logistics_global(session: Session,
                          ids: Optional[List[int]] = None,
                          status: Optional[str] = None,
                          date_from: Optional[str] = None,
                          date_to: Optional[str] = None,
                          tracking_number: Optional[str] = None,
                          express_order_id: Optional[int] = None,
                          sku_id: Optional[int] = None,
                          sku_name_kw: Optional[str] = None,
                          shipping_point_id: Optional[int] = None,
                          shipping_point_name_kw: Optional[str] = None,
                          receiving_point_id: Optional[int] = None,
                          receiving_point_name_kw: Optional[str] = None,
                          vc_id: Optional[int] = None,
                          vc_type: Optional[str] = None,
                          vc_status_type: Optional[str] = None,
                          vc_status_value: Optional[str] = None,
                          subject_status: Optional[str] = None,
                          business_id: Optional[int] = None,
                          business_customer_name_kw: Optional[str] = None,
                          supply_chain_id: Optional[int] = None,
                          supply_chain_supplier_name_kw: Optional[str] = None,
                          page: int = 1, size: int = 20) -> Dict[str, Any]:
    from sqlalchemy import exists, cast, Integer, String

    # Subquery: get LOGISTICS_PLAN_CREATED event payload per logistics
    log_event_subq = session.query(
        SystemEvent.payload
    ).filter(
        SystemEvent.event_type == 'LOGISTICS_PLAN_CREATED',
        SystemEvent.aggregate_type == 'Logistics',
        SystemEvent.aggregate_id == Logistics.id
    ).scalar_subquery()

    q = session.query(
        Logistics,
        log_event_subq
    ).outerjoin(
        VirtualContract, Logistics.virtual_contract_id == VirtualContract.id
    )

    conditions = []

    if ids:
        conditions.append(Logistics.id.in_(ids))
    if status:
        conditions.append(Logistics.status == status)
    if date_from:
        conditions.append(Logistics.timestamp >= date_from)
    if date_to:
        conditions.append(Logistics.timestamp <= date_to)

    if tracking_number:
        conditions.append(
            exists().where(
                ExpressOrder.logistics_id == Logistics.id,
                ExpressOrder.tracking_number.ilike(f"%{tracking_number}%")
            )
        )
    if express_order_id:
        conditions.append(
            exists().where(
                ExpressOrder.logistics_id == Logistics.id,
                ExpressOrder.id == express_order_id
            )
        )

    if sku_id:
        # items is JSON array, use cast to text for array elements
        conditions.append(
            exists().where(
                ExpressOrder.logistics_id == Logistics.id,
                cast(ExpressOrder.items, String).ilike(f'%\"sku_id\": {sku_id}%')
            )
        )
    if sku_name_kw:
        conditions.append(
            exists().where(
                ExpressOrder.logistics_id == Logistics.id,
                cast(ExpressOrder.items, String).ilike(f"%{sku_name_kw}%")
            )
        )

    if shipping_point_id:
        conditions.append(
            exists().where(
                ExpressOrder.logistics_id == Logistics.id,
                ExpressOrder.address_info.op('->>')('发货点位Id').cast(Integer) == shipping_point_id
            )
        )
    if shipping_point_name_kw:
        conditions.append(
            exists().where(
                ExpressOrder.logistics_id == Logistics.id,
                ExpressOrder.address_info.op('->>')('发货点位名称').ilike(f"%{shipping_point_name_kw}%")
            )
        )
    if receiving_point_id:
        conditions.append(
            exists().where(
                ExpressOrder.logistics_id == Logistics.id,
                ExpressOrder.address_info.op('->>')('收货点位Id').cast(Integer) == receiving_point_id
            )
        )
    if receiving_point_name_kw:
        conditions.append(
            exists().where(
                ExpressOrder.logistics_id == Logistics.id,
                ExpressOrder.address_info.op('->>')('收货点位名称').ilike(f"%{receiving_point_name_kw}%")
            )
        )

    if vc_id:
        conditions.append(Logistics.virtual_contract_id == vc_id)
    if vc_type:
        conditions.append(VirtualContract.type == vc_type)
    if vc_status_type and vc_status_value:
        if vc_status_type == '主状态':
            conditions.append(VirtualContract.status == vc_status_value)
        elif vc_status_type == '合同状态':
            conditions.append(VirtualContract.subject_status == vc_status_value)
    if subject_status:
        conditions.append(VirtualContract.subject_status == subject_status)

    if business_id:
        conditions.append(VirtualContract.business_id == business_id)
    if business_customer_name_kw:
        conditions.append(
            exists().where(
                VirtualContract.business_id == Business.id,
                Business.customer_id == ChannelCustomer.id,
                ChannelCustomer.name.ilike(f"%{business_customer_name_kw}%")
            )
        )

    if supply_chain_id:
        conditions.append(VirtualContract.supply_chain_id == supply_chain_id)
    if supply_chain_supplier_name_kw:
        conditions.append(
            exists().where(
                VirtualContract.supply_chain_id == SupplyChain.id,
                SupplyChain.supplier_id == Supplier.id,
                Supplier.name.ilike(f"%{supply_chain_supplier_name_kw}%")
            )
        )

    for cond in conditions:
        q = q.filter(cond)

    total = q.count()
    items = q.order_by(Logistics.id.desc()).offset((page - 1) * size).limit(size).all()

    # Enrich with VC type
    vc_ids = list(set(l[0].virtual_contract_id for l in items if l[0].virtual_contract_id))
    vc_map = {vc.id: vc for vc in session.query(VirtualContract).filter(VirtualContract.id.in_(vc_ids)).all()} if vc_ids else {}

    result = []
    for row in items:
        l = row[0]
        event_payload = row[1]
        vc = vc_map.get(l.virtual_contract_id)
        tx_date = None
        if event_payload and isinstance(event_payload, dict):
            tx_date = event_payload.get('transaction_date')
        result.append({
            'id': l.id,
            'virtual_contract_id': l.virtual_contract_id,
            'status': l.status,
            'created_at': l.timestamp.isoformat() if l.timestamp else None,
            'transaction_date': tx_date,
            'express_orders_count': len(l.express_orders) if l.express_orders else 0,
            'vc_type': vc.type if vc else None,
        })

    return {"items": result, "total": total, "page": page, "size": size}


# =============================================================================
# Finance Queries
# =============================================================================

def list_cashflows(session: Session, ids: Optional[List[int]] = None,
                   vc_id: Optional[int] = None, vc_ids: Optional[List[int]] = None,
                   type: Optional[str] = None, payer_id: Optional[int] = None,
                   payee_id: Optional[int] = None, date_from: Optional[str] = None,
                   date_to: Optional[str] = None, amount_min: Optional[float] = None,
                   amount_max: Optional[float] = None, page: int = 1, size: int = 50,
                   # Extended search params
                   business_ids: Optional[List[int]] = None,
                   sc_ids: Optional[List[int]] = None,
                   customer_kw: Optional[str] = None,
                   supplier_kw: Optional[str] = None,
                   payer_name_kw: Optional[str] = None,
                   payee_name_kw: Optional[str] = None) -> Dict[str, Any]:
    from sqlalchemy.orm import joinedload
    from sqlalchemy import or_, exists

    q = session.query(CashFlow).options(
        joinedload(CashFlow.payer_account),
        joinedload(CashFlow.payee_account)
    )

    # Build filter conditions
    conditions = []

    if ids:
        conditions.append(CashFlow.id.in_(ids))
    if vc_id is not None:
        conditions.append(CashFlow.virtual_contract_id == vc_id)
    if vc_ids:
        conditions.append(CashFlow.virtual_contract_id.in_(vc_ids))
    if type:
        conditions.append(CashFlow.type == type)
    if payer_id is not None:
        conditions.append(CashFlow.payer_account_id == payer_id)
    if payee_id is not None:
        conditions.append(CashFlow.payee_account_id == payee_id)
    if date_from:
        conditions.append(CashFlow.transaction_date >= date_from)
    if date_to:
        conditions.append(CashFlow.transaction_date <= date_to)
    if amount_min is not None:
        conditions.append(CashFlow.amount >= amount_min)
    if amount_max is not None:
        conditions.append(CashFlow.amount <= amount_max)

    # Cross-table filters using exists subqueries
    if business_ids:
        conditions.append(
            exists().where(
                VirtualContract.id == CashFlow.virtual_contract_id,
                VirtualContract.business_id.in_(business_ids)
            )
        )
    if sc_ids:
        conditions.append(
            exists().where(
                VirtualContract.id == CashFlow.virtual_contract_id,
                VirtualContract.supply_chain_id.in_(sc_ids)
            )
        )
    if customer_kw:
        conditions.append(
            exists().where(
                VirtualContract.id == CashFlow.virtual_contract_id,
                VirtualContract.business_id == Business.id,
                Business.customer_id == ChannelCustomer.id,
                ChannelCustomer.name.ilike(f'%{customer_kw}%')
            )
        )
    if supplier_kw:
        conditions.append(
            exists().where(
                VirtualContract.id == CashFlow.virtual_contract_id,
                VirtualContract.supply_chain_id == SupplyChain.id,
                SupplyChain.supplier_id == Supplier.id,
                Supplier.name.ilike(f'%{supplier_kw}%')
            )
        )
    if payer_name_kw:
        conditions.append(CashFlow.payer_account_name.ilike(f'%{payer_name_kw}%'))
    if payee_name_kw:
        conditions.append(CashFlow.payee_account_name.ilike(f'%{payee_name_kw}%'))

    for cond in conditions:
        q = q.filter(cond)

    total = q.count()
    items = q.order_by(CashFlow.transaction_date.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [_cashflow_to_dict(c) for c in items], "total": total, "page": page, "size": size}


def get_cashflow(session: Session, cf_id: int) -> Optional[Dict[str, Any]]:
    obj = session.query(CashFlow).get(cf_id)
    return _cashflow_to_dict(obj) if obj else None


def _cashflow_to_dict(c: CashFlow) -> Dict[str, Any]:
    if c is None:
        return {}
    payer_acc = c.payer_account
    payee_acc = c.payee_account
    payer_info = payer_acc.account_info if payer_acc and payer_acc.account_info else {}
    payee_info = payee_acc.account_info if payee_acc and payee_acc.account_info else {}
    vc = c.virtual_contract
    return {"id": c.id, "virtual_contract_id": c.virtual_contract_id,
            "vc_type": vc.type if vc else None,
            "type": c.type,
            "amount": c.amount, "payer_account_id": c.payer_account_id,
            "payee_account_id": c.payee_account_id,
            "payer_owner_type": payer_acc.owner_type if payer_acc else None,
            "payee_owner_type": payee_acc.owner_type if payee_acc else None,
            "payer_account_name": payer_info.get("开户名称") or payer_info.get("bank_name") or payer_info.get("bank") or None,
            "payee_account_name": payee_info.get("开户名称") or payee_info.get("bank_name") or payee_info.get("bank") or None,
            "transaction_date": c.transaction_date.isoformat() if c.transaction_date else None,
            "description": c.description}


# =============================================================================
# Supply Chain Queries
# =============================================================================

def list_supply_chains(session: Session, ids: Optional[List[int]] = None,
                       supplier_id: Optional[int] = None, supplier_ids: Optional[List[int]] = None,
                       status: Optional[str] = None, type: Optional[str] = None,
                       date_from: Optional[str] = None, date_to: Optional[str] = None,
                       supplier_name_kw: Optional[str] = None,
                       sku_name_kw: Optional[str] = None,
                       page: int = 1, size: int = 50) -> Dict[str, Any]:
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
    if supplier_name_kw:
        q = q.join(Supplier, SupplyChain.supplier_id == Supplier.id).filter(
            Supplier.name.ilike(f"%{supplier_name_kw}%"))
    if sku_name_kw:
        q = q.join(SupplyChainItem, SupplyChain.id == SupplyChainItem.supply_chain_id)
        q = q.join(SKU, SupplyChainItem.sku_id == SKU.id)
        q = q.filter(SKU.name.ilike(f"%{sku_name_kw}%"))
    total = q.count()
    if size and size > 0:
        items = q.order_by(SupplyChain.id.desc()).offset((page - 1) * size).limit(size).all()
    else:
        items = q.order_by(SupplyChain.id.desc()).all()
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
    result = {
        "id": s.id,
        "supplier_id": s.supplier_id,
        "supplier_name": s.supplier.name if s.supplier else None,
        "type": s.type,
        "payment_terms": s.payment_terms or {},
        "contract_id": s.contract_id,
    }
    # Add items with SKU names
    if s.items:
        result["items"] = [{
            "sku_id": item.sku_id,
            "sku_name": item.sku.name if item.sku else f"SKU-{item.sku_id}",
            "price": item.price,
            "is_floating": item.is_floating,
        } for item in s.items]
    else:
        result["items"] = []
    return result


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
        q = q.filter(TimeRule.timestamp >= date_from)
    if date_to:
        q = q.filter(TimeRule.timestamp <= date_to)
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
            "inherit": r.inherit, "party": r.party,
            "trigger_event": r.trigger_event, "trigger_time": r.trigger_time.isoformat() if r.trigger_time else None,
            "tge_param1": r.tge_param1, "tge_param2": r.tge_param2,
            "target_event": r.target_event, "target_time": r.target_time.isoformat() if r.target_time else None,
            "tae_param1": r.tae_param1, "tae_param2": r.tae_param2,
            "offset": r.offset, "unit": r.unit, "direction": r.direction,
            "flag_time": r.flag_time.isoformat() if r.flag_time else None,
            "warning": r.warning, "result": r.result,
            "status": r.status,
            "created_at": r.timestamp.isoformat() if r.timestamp else None,
            "updated_at": r.endstamp.isoformat() if r.endstamp else None}


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

    # 批量加载 SKU 和 Point 名称
    s_ids = list(set(e.sku_id for e in items if e.sku_id))
    p_ids = list(set(e.point_id for e in items if e.point_id))
    sku_map = {s.id: s.name for s in session.query(SKUModel).filter(SKUModel.id.in_(s_ids)).all()} if s_ids else {}
    pt_map = {p.id: p.name for p in session.query(PointModel).filter(PointModel.id.in_(p_ids)).all()} if p_ids else {}

    return {"items": [_equipment_to_dict(e, sku_map, pt_map) for e in items], "total": total, "page": page, "size": size}


def _equipment_to_dict(e: EquipmentInventory, sku_map: Dict[int, str] = None, pt_map: Dict[int, str] = None) -> Dict[str, Any]:
    if e is None:
        return {}
    # 中文状态值转英文（客户端期望英文枚举）
    op_status_map = {"库存": "IN_STOCK", "运营": "IN_OPERATION", "处置": "DISPOSAL"}
    dev_status_map = {"正常": "NORMAL", "维修": "MAINTENANCE", "损坏": "DAMAGED", "故障": "FAULT", "维护": "MAINTENANCE", "锁机": "LOCKED"}
    return {"id": e.id, "vc_id": e.virtual_contract_id, "point_id": e.point_id,
            "sku_id": e.sku_id, "sku_name": (sku_map or {}).get(e.sku_id) or "未知",
            "point_name": (pt_map or {}).get(e.point_id) or f"点位{e.point_id}",
            "sn": e.sn, "operational_status": op_status_map.get(e.operational_status, e.operational_status or "IN_STOCK"),
            "device_status": dev_status_map.get(e.device_status, e.device_status or "NORMAL"), "deposit_amount": e.deposit_amount}


def list_material(session: Session, sku_id: Optional[int] = None,
                  warehouse_point_id: Optional[int] = None,
                  batch_no: Optional[str] = None,
                  production_date_from: Optional[str] = None,
                  production_date_to: Optional[str] = None,
                  status: Optional[str] = None,
                  page: int = 1, size: int = 50) -> Dict[str, Any]:
    """物料库存查询，支持数据库级分页。"""
    # 先构建基础查询
    q = session.query(MaterialInventory).filter(MaterialInventory.qty > 0)
    if sku_id is not None:
        q = q.filter(MaterialInventory.sku_id == sku_id)
    if warehouse_point_id is not None:
        q = q.filter(MaterialInventory.point_id == warehouse_point_id)
    if batch_no:
        q = q.filter(MaterialInventory.batch_no == batch_no)
    if production_date_from:
        q = q.filter(MaterialInventory.production_date >= production_date_from)
    if production_date_to:
        q = q.filter(MaterialInventory.production_date <= production_date_to)

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
            "vc_id": b.latest_purchase_vc_id,
            "production_date": b.production_date,
            "expiration_date": b.expiration_date,
            "certificate_file": b.certificate_file,
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

def list_recent_events(session: Session, page: int = 1, size: int = 20,
                         event_type: str = None, aggregate_type: str = None) -> Dict[str, Any]:
    q = session.query(SystemEvent)
    if event_type:
        q = q.filter(SystemEvent.event_type == event_type)
    if aggregate_type:
        q = q.filter(SystemEvent.aggregate_type == aggregate_type)
    total = q.count()
    events = q.order_by(SystemEvent.id.desc()).offset((page - 1) * size).limit(size).all()
    items = [{
        "id": e.id, "event_type": e.event_type, "aggregate_type": e.aggregate_type,
        "aggregate_id": e.aggregate_id, "payload": e.payload,
        "created_at": e.created_at.isoformat() if e.created_at else None
    } for e in events]
    return {"items": items, "total": total, "page": page, "size": size}


def mark_events_pushed(session: Session, event_ids: List[int]) -> None:
    if event_ids:
        session.query(SystemEvent).filter(SystemEvent.id.in_(event_ids)).update(
            {"pushed_to_ai": True}, synchronize_session=False
        )


# =============================================================================
# Addon Business Global Query
# =============================================================================

def list_addons_global(session: Session,
                       business_id: Optional[int] = None,
                       customer_name_kw: Optional[str] = None,
                       sku_name_kw: Optional[str] = None,
                       status: Optional[str] = None,
                       page: int = 1, size: int = 20) -> Dict[str, Any]:
    q = session.query(AddonBusiness).join(
        Business, AddonBusiness.business_id == Business.id
    ).outerjoin(
        ChannelCustomer, Business.customer_id == ChannelCustomer.id
    )

    if business_id is not None:
        q = q.filter(AddonBusiness.business_id == business_id)
    if customer_name_kw:
        q = q.filter(ChannelCustomer.name.ilike(f"%{customer_name_kw}%"))
    if sku_name_kw:
        q = q.join(SKUModel, AddonBusiness.sku_id == SKUModel.id).filter(
            SKUModel.name.ilike(f"%{sku_name_kw}%")
        )
    if status:
        q = q.filter(AddonBusiness.status == status)

    total = q.count()
    items = q.order_by(AddonBusiness.id.desc()).offset((page - 1) * size).limit(size).all()

    # Batch-enrich sku_name
    sku_ids = list(set(a.sku_id for a in items if a.sku_id))
    sku_map = {s.id: s.name for s in session.query(SKUModel).filter(SKUModel.id.in_(sku_ids)).all()} if sku_ids else {}

    result = []
    for a in items:
        result.append({
            "id": a.id,
            "business_id": a.business_id,
            "business_name": a.business.name if a.business else None,
            "customer_name": a.business.customer.name if a.business and a.business.customer else None,
            "addon_type": a.addon_type,
            "status": a.status,
            "sku_id": a.sku_id,
            "sku_name": sku_map.get(a.sku_id, f"SKU-{a.sku_id}") if a.sku_id else None,
            "override_price": a.override_price,
            "override_deposit": a.override_deposit,
            "start_date": a.start_date.isoformat() if a.start_date else None,
            "end_date": a.end_date.isoformat() if a.end_date else None,
            "remark": a.remark,
        })

    return {"items": result, "total": total, "page": page, "size": size}
