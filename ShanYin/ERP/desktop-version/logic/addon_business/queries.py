from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from models import AddonBusiness, Business
from logic.constants import AddonType, AddonStatus, BusinessStatus


def sku_exists_in_business(session: Session, business_id: int, sku_id: int) -> bool:
    """
    判断某 SKU 是否已在该业务的定价配置中存在。
    判断依据：business.details["pricing"] 的 key（严格使用 sku_id）。
    """
    biz = session.query(Business).get(business_id)
    if not biz:
        return False

    pricing = biz.details.get("pricing", {}) if biz.details else {}
    return str(sku_id) in pricing


def get_original_price_and_deposit(session: Session, business_id: int, sku_id: int) -> Tuple[Optional[float], Optional[float]]:
    """
    获取 SKU 在业务中的原价和原押金。
    严格从 business.details["pricing"] 取，不 fallback 到 VC elements。
    Returns (price, deposit)。查不到返回 (None, None)。
    """
    biz = session.query(Business).get(business_id)
    if not biz:
        return None, None

    pricing = biz.details.get("pricing", {}) if biz.details else {}
    sku_key = str(sku_id)
    if sku_key in pricing:
        p = pricing[sku_key]
        return p.get("price"), p.get("deposit")

    return None, None


def check_addon_overlap(
    session: Session,
    business_id: int,
    sku_id: Optional[int],
    start_date: datetime,
    end_date: Optional[datetime],
    exclude_id: Optional[int] = None
) -> Tuple[bool, Optional[AddonBusiness]]:
    """
    检查同业务 + 同 SKU 下是否有日期重叠的生效 addon（不区分 addon_type）。
    同 SKU 下 PRICE_ADJUST 和 NEW_SKU 互斥，因此只需按 SKU 维度检查重叠。
    end_date=None 表示永久有效。
    Overlap 判定:
      - 如果已有 addon 的 end_date 为 NULL（永久有效），则必定重叠
      - 否则：new.start < existing.end AND (new.end is NULL OR new.end > existing.start)
    Returns (has_overlap, conflicting_addon or None)
    """
    base_filter = [
        AddonBusiness.business_id == business_id,
        AddonBusiness.sku_id == sku_id,
        AddonBusiness.status == AddonStatus.ACTIVE,
    ]
    if exclude_id:
        base_filter.append(AddonBusiness.id != exclude_id)

    if end_date is None:
        # 新 addon 永久有效：只要已有 addon 是永久有效 OR 开始日期早于已有结束日期
        overlap_cond = or_(
            AddonBusiness.end_date.is_(None),
            start_date < AddonBusiness.end_date
        )
    else:
        # 两者都有限期
        overlap_cond = or_(
            AddonBusiness.end_date.is_(None),
            and_(
                start_date < AddonBusiness.end_date,
                end_date > AddonBusiness.start_date
            )
        )

    query = session.query(AddonBusiness).filter(*base_filter, overlap_cond)
    conflicting = query.first()
    return conflicting is not None, conflicting


def get_active_addons(session: Session, business_id: int, dt: Optional[datetime] = None) -> List[AddonBusiness]:
    """
    获取业务下当前时间点所有生效的原子 addon。
    dt=None 时使用当前时间。
    永久有效（end_date=NULL）的 addon 也被包含。
    """
    if dt is None:
        dt = datetime.now()
    return session.query(AddonBusiness).filter(
        AddonBusiness.business_id == business_id,
        AddonBusiness.status == AddonStatus.ACTIVE,
        AddonBusiness.start_date <= dt,
        or_(
            AddonBusiness.end_date >= dt,
            AddonBusiness.end_date.is_(None)
        )
    ).all()


def get_active_addons_by_type(
    session: Session,
    business_id: int,
    addon_type: str,
    dt: Optional[datetime] = None
) -> List[AddonBusiness]:
    """获取业务下指定类型的生效 addon"""
    if dt is None:
        dt = datetime.now()
    return session.query(AddonBusiness).filter(
        AddonBusiness.business_id == business_id,
        AddonBusiness.addon_type == addon_type,
        AddonBusiness.status == AddonStatus.ACTIVE,
        AddonBusiness.start_date <= dt,
        or_(
            AddonBusiness.end_date >= dt,
            AddonBusiness.end_date.is_(None)
        )
    ).all()


def get_addon_detail(session: Session, addon_id: int) -> Optional[AddonBusiness]:
    """获取单个 addon 详情"""
    return session.query(AddonBusiness).get(addon_id)


def get_business_addons(
    session: Session,
    business_id: int,
    include_expired: bool = False
) -> List[AddonBusiness]:
    """
    获取业务下所有 addon。
    include_expired=True 时包含已过期的（status=EXPIRED），否则只返回生效和失效的。
    """
    query = session.query(AddonBusiness).filter(
        AddonBusiness.business_id == business_id
    )
    if not include_expired:
        query = query.filter(AddonBusiness.status != AddonStatus.EXPIRED)
    return query.order_by(AddonBusiness.start_date.desc()).all()


def can_add_addon(session: Session, business_id: int) -> Tuple[bool, Optional[str]]:
    """
    检查业务是否允许添加 addon。
    前提：业务必须在 ACTIVE 阶段。
    """
    biz = session.query(Business).get(business_id)
    if not biz:
        return False, "业务不存在"
    if biz.status != BusinessStatus.ACTIVE:
        return False, f"业务当前阶段「{biz.status}」不允许添加附加项"
    return True, None
