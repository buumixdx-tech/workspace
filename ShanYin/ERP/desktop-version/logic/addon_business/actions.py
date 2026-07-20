from sqlalchemy.orm import Session
from models import AddonBusiness
from logic.base import ActionResult
from api.middleware.error_handler import raise_not_found_error, BusinessError
from logic.events.dispatcher import emit_event
from logic.constants import SystemEventType, SystemAggregateType, AddonType, AddonStatus
from .schemas import CreateAddonSchema, UpdateAddonSchema
from .queries import (
    check_addon_overlap,
    can_add_addon,
    get_addon_detail,
    sku_exists_in_business,
    get_original_price_and_deposit,
)


def create_addon_business_action(session: Session, payload: CreateAddonSchema) -> ActionResult:
    """
    创建附加业务（原子化版本）

    合法性校验链路：
    1. 业务前提：必须在 LANDING/ACTIVE
    2. addon_type 有效性
    3. SKU 必填（PRICE_ADJUST / NEW_SKU）
    4. SKU 存在性 → 决定合法 addon_type
       - 已存在：必须是 PRICE_ADJUST，且 override_price/deposit 必须与原价不同
       - 不存在：必须是 NEW_SKU，且 override_price/deposit 必须与原价不同
    5. 日期重叠检查（同业务 + 同 SKU，不区分类型）
    6. 创建记录
    """
    # 1. 业务前提
    can_add, err = can_add_addon(session, payload.business_id)
    if not can_add:
        return ActionResult(success=False, error=err)

    # 2. addon_type 有效性（目前仅支持 PRICE_ADJUST 和 NEW_SKU）
    valid_types = [AddonType.PRICE_ADJUST, AddonType.NEW_SKU]
    if payload.addon_type not in valid_types:
        return ActionResult(success=False, error=f"无效的 addon_type：{payload.addon_type}")

    # 3. SKU 必填
    if payload.addon_type in [AddonType.PRICE_ADJUST, AddonType.NEW_SKU]:
        if not payload.sku_id:
            return ActionResult(success=False, error=f"{payload.addon_type} 必须指定 sku_id")

    # 4. SKU 存在性判断 & addon_type 互斥规则
    exists = sku_exists_in_business(session, payload.business_id, payload.sku_id)
    if exists:
        # SKU 已存在 → 必须是 PRICE_ADJUST
        if payload.addon_type != AddonType.PRICE_ADJUST:
            return ActionResult(
                success=False,
                error=f"SKU {payload.sku_id} 已在该业务中存在，addon_type 必须为 PRICE_ADJUST"
            )
    else:
        # SKU 不存在 → 必须是 NEW_SKU
        if payload.addon_type != AddonType.NEW_SKU:
            return ActionResult(
                success=False,
                error=f"SKU {payload.sku_id} 在该业务中尚不存在，addon_type 必须为 NEW_SKU"
            )

    # 4.2 价格变化校验：override_price 或 override_deposit 至少有一个与原价不同
    orig_price, orig_deposit = get_original_price_and_deposit(
        session, payload.business_id, payload.sku_id
    )
    # orig_price 为 None 表示历史上没有该 SKU 的价格记录，任何新设置都算变化
    price_changed = (
        payload.override_price is not None
        and (orig_price is None or abs(payload.override_price - orig_price) > 0.001)
    )
    deposit_changed = (
        payload.override_deposit is not None
        and (orig_deposit is None or abs(payload.override_deposit - orig_deposit) > 0.001)
    )
    if not price_changed and not deposit_changed:
        return ActionResult(
            success=False,
            error=f"override_price 或 override_deposit 至少有一个必须与原价不同（原价 price={orig_price}, deposit={orig_deposit}）"
        )

    # 5. 日期有效性
    if payload.end_date is not None and payload.start_date >= payload.end_date:
        return ActionResult(success=False, error="开始日期必须早于结束日期")

    # 6. 日期重叠检查（同业务 + 同 SKU，不区分类型）
    has_overlap, conflict = check_addon_overlap(
        session,
        payload.business_id,
        payload.sku_id,
        payload.start_date,
        payload.end_date
    )
    if has_overlap:
        end_str = conflict.end_date.strftime('%Y-%m-%d') if conflict.end_date else '永久'
        return ActionResult(
            success=False,
            error=f"与已有同业务附加项(#{conflict.id})时间重叠："
                  f"{conflict.start_date.strftime('%Y-%m-%d')} ~ {end_str}"
        )

    # 7. 创建记录
    new_addon = AddonBusiness(
        business_id=payload.business_id,
        addon_type=payload.addon_type,
        status=AddonStatus.ACTIVE,
        sku_id=payload.sku_id,
        override_price=payload.override_price,
        override_deposit=payload.override_deposit,
        start_date=payload.start_date,
        end_date=payload.end_date,
        remark=payload.remark
    )
    session.add(new_addon)
    session.flush()

    emit_event(
        session,
        SystemEventType.ADDON_CREATED,
        SystemAggregateType.ADDON_BUSINESS,
        new_addon.id,
        {"business_id": payload.business_id, "addon_type": payload.addon_type, "sku_id": payload.sku_id}
    )

    session.commit()
    return ActionResult(success=True, data={"addon_id": new_addon.id}, message="附加项已创建")


def update_addon_business_action(session: Session, payload: UpdateAddonSchema) -> ActionResult:
    """
    更新附加业务（原子化版本，仅允许修改日期、覆盖值、status、remark）
    addon_type 和 sku_id 不允许修改。
    更新 override_price/override_deposit 时，需校验与原价的差异。
    更新日期时需校验重叠。
    """
    addon = get_addon_detail(session, payload.addon_id)
    if not addon:
        return ActionResult(success=False, error="附加项不存在")

    # 日期重叠校验（用新日期覆盖旧日期）
    if payload.start_date or payload.end_date is not None:
        new_start = payload.start_date or addon.start_date
        new_end = payload.end_date if payload.end_date is not None else addon.end_date
        if new_end is not None and new_start >= new_end:
            return ActionResult(success=False, error="开始日期必须早于结束日期")

        has_overlap, conflict = check_addon_overlap(
            session,
            addon.business_id,
            addon.sku_id,
            new_start,
            new_end,
            exclude_id=addon.id
        )
        if has_overlap:
            return ActionResult(
                success=False,
                error=f"与已有同业务附加项(#{conflict.id})时间重叠"
            )
        addon.start_date = new_start
        addon.end_date = new_end

    # 价格变化校验（如果更新了覆盖值，需校验是否真的变化了）
    # 变化判断：与当前生效值（addon.override 或 原价）比较，而非与原价比较
    check_price = payload.override_price is not None
    check_deposit = payload.override_deposit is not None
    if check_price or check_deposit:
        orig_price, orig_deposit = get_original_price_and_deposit(
            session, addon.business_id, addon.sku_id
        )
        # 当前生效值 = addon当前override（若有），否则=原价
        effective_price = addon.override_price if addon.override_price is not None else orig_price
        effective_deposit = addon.override_deposit if addon.override_deposit is not None else orig_deposit

        price_changed = (
            check_price
            and (effective_price is None or abs(payload.override_price - effective_price) > 0.001)
        )
        deposit_changed = (
            check_deposit
            and (effective_deposit is None or abs(payload.override_deposit - effective_deposit) > 0.001)
        )
        if not price_changed and not deposit_changed:
            return ActionResult(
                success=False,
                error=f"override_price 或 override_deposit 至少有一个必须与当前生效值不同（当前 price={effective_price}, deposit={effective_deposit}）"
            )

    # 直接字段更新
    if payload.override_price is not None:
        addon.override_price = payload.override_price
    if payload.override_deposit is not None:
        addon.override_deposit = payload.override_deposit
    if payload.status is not None:
        addon.status = payload.status
    if payload.remark is not None:
        addon.remark = payload.remark

    emit_event(
        session,
        SystemEventType.ADDON_UPDATED,
        SystemAggregateType.ADDON_BUSINESS,
        addon.id,
        {}
    )

    session.commit()
    return ActionResult(success=True, message="附加项已更新")


def deactivate_addon_business_action(session: Session, addon_id: int) -> ActionResult:
    """软删除/失效附加业务"""
    addon = get_addon_detail(session, addon_id)
    if not addon:
        raise_not_found_error("附加政策", str(addon_id))

    addon.status = AddonStatus.INACTIVE

    emit_event(
        session,
        SystemEventType.ADDON_DEACTIVATED,
        SystemAggregateType.ADDON_BUSINESS,
        addon_id,
        {"status": AddonStatus.INACTIVE}
    )

    session.commit()
    return ActionResult(success=True, message="附加项已失效")
