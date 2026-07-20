from typing import List, Dict, Optional, Any
from models import get_session, Business, ChannelCustomer, VirtualContract, SKU
from logic.constants import BusinessStatus
from logic.master import get_partner_relations

def get_business_list(
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """获取业务列表"""
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        query = session.query(Business).options(joinedload(Business.customer))
        if status:
            if isinstance(status, list):
                query = query.filter(Business.status.in_(status))
            else:
                query = query.filter(Business.status == status)
        if customer_id:
            query = query.filter(Business.customer_id == customer_id)
        
        businesses = query.order_by(Business.timestamp.desc()).limit(limit).all()

        result = []
        for biz in businesses:
            customer = biz.customer
            result.append({
                "id": biz.id,
                "customer_name": customer.name if customer else "未知客户",
                "status": biz.status,
                "status_label": _get_status_label(biz.status),
                "created_at": biz.timestamp.strftime("%Y-%m-%d") if biz.timestamp else "",
                "details": biz.details or {},
                "partners": get_partner_relations(
                    owner_type="business",
                    owner_id=biz.id,
                    active_only=True
                )
            })
        return result
    finally:
        session.close()

def get_business_detail(business_id: int) -> Optional[Dict[str, Any]]:
    """获取业务详细信息"""
    session = get_session()
    try:
        biz = session.query(Business).get(business_id)
        if not biz:
            return None

        customer = session.query(ChannelCustomer).get(biz.customer_id)
        contracts = session.query(VirtualContract).filter(VirtualContract.business_id == business_id).all()

        # pricing key 为 sku_id（数字字符串），直接透传
        pricing = biz.details.get("pricing", {}) if biz.details else {}

        return {
            "id": biz.id,
            "customer_id": customer.id if customer else None,
            "customer_name": customer.name if customer else "未知",
            "customer": {
                "id": customer.id if customer else None,
                "name": customer.name if customer else "未知",
                "info": customer.info if customer else ""
            },
            "status": biz.status,
            "status_label": _get_status_label(biz.status),
            "pricing": pricing,
            "payment_terms": biz.details.get("payment_terms", {}) if biz.details else {},
            "contracts": biz.details.get("contracts", []) if biz.details else [],
            "details": biz.details or {},
            "vc_list": [
                {
                    "id": c.id,
                    "type": c.type,
                    "status": c.status,
                    "total_amount": c.elements.get("total_amount", 0) if c.elements else 0
                }
                for c in contracts
            ],
            "created_at": biz.timestamp.strftime("%Y-%m-%d %H:%M") if biz.timestamp else "",
            "updated_at": "",
            "partners": get_partner_relations(
                owner_type="business",
                owner_id=biz.id,
                active_only=True
            )
        }
    finally:
        session.close()

def _get_status_label(status: str) -> str:
    """获取业务状态的中文标签"""
    status_map = {
        BusinessStatus.DRAFT: "前期接洽",
        BusinessStatus.EVALUATION: "业务评估",
        BusinessStatus.FEEDBACK: "客户反馈",
        BusinessStatus.LANDING: "合作落地",
        BusinessStatus.ACTIVE: "业务开展",
        BusinessStatus.PAUSED: "业务暂缓",
        BusinessStatus.TERMINATED: "业务终止",
        BusinessStatus.FINISHED: "业务完成",
    }
    return status_map.get(status, status)

def get_businesses_for_execution() -> List[Dict[str, Any]]:
    """获取正在执行/开展中的业务列表 (LANDING, ACTIVE)"""
    from logic.constants import BusinessStatus
    from sqlalchemy.orm import joinedload
    session = get_session()
    try:
        businesses = session.query(Business).options(
            joinedload(Business.customer)
        ).filter(
            Business.status.in_([BusinessStatus.LANDING, BusinessStatus.ACTIVE])
        ).all()

        return [
            {
                "id": b.id,
                "customer_id": b.customer_id,
                "customer_name": b.customer.name if b.customer else "未知",
                "status": b.status,
                "details": b.details
            }
            for b in businesses
        ]
    finally:
        session.close()
