from sqlalchemy.orm import Session
from sqlalchemy import func
import sqlalchemy.orm.attributes as _attributes
from models import VirtualContract, TimeRule, Business, SupplyChain, EquipmentInventory, Point, MaterialInventory
from models import CashFlow, FinancialJournal, CashFlowLedger, SystemEvent
from logic.constants import (
    VCType, VCStatus, SubjectStatus, CashStatus, TimeRuleRelatedType,
    TimeRuleStatus, BusinessStatus, SKUType, SystemEventType, SystemAggregateType,
    OperationalStatus, ReturnDirection
)
from logic.time_rules import RuleManager
from logic.offset_manager import apply_offset_to_vc
from logic.events.dispatcher import emit_event
from api.middleware.error_handler import raise_not_found_error, BusinessError
from .schemas import (
    CreateProcurementVCSchema, CreateStockProcurementVCSchema, CreateMatProcurementVCSchema,
    CreateMaterialSupplyVCSchema, CreateReturnVCSchema, AllocateInventorySchema,
    UpdateVCSchema, DeleteVCSchema, VCElementSchema
)
from logic.base import ActionResult
from datetime import datetime


# =============================================================================
# 辅助函数：点位查询（商业逻辑）
# =============================================================================

# 默认总仓库ID
DEFAULT_WAREHOUSE_ID = 1


def _record_vc_created_log(session: Session, vc: VirtualContract):
    """VC创建时记录初始状态日志（status=执行），同时更新status_timestamp"""
    vc.update_status(vc.status, is_initial=True)


def _get_supplier_warehouse(session: Session, supplier_id: int) -> int | None:
    """
    根据供应商ID找供应商仓库 Point.id
    规则：Point.type=供应商仓 且 Point.supplier_id=supplier_id
    返回 None 表示未找到
    """
    pt = session.query(Point).filter(
        Point.supplier_id == supplier_id,
        Point.type == "供应商仓"
    ).first()
    return pt.id if pt else None


def _get_our_warehouses(session: Session) -> list[int]:
    """
    获取我们所有的仓库（type=自有仓）的ID列表
    """
    pts = session.query(Point).filter(Point.type == "自有仓").all()
    return [pt.id for pt in pts]


def _get_supplier_warehouses(session: Session, supplier_id: int) -> list[int]:
    """
    获取指定供应商的仓库（type=供应商仓 且 supplier_id）的ID列表
    """
    pts = session.query(Point).filter(
        Point.supplier_id == supplier_id,
        Point.type == "供应商仓"
    ).all()
    return [pt.id for pt in pts]


def _get_customer_warehouses(session: Session, customer_id: int = None) -> list[int]:
    """
    获取所有客户仓库的ID列表，或指定客户的仓库
    """
    if customer_id is not None:
        pts = session.query(Point).filter(
            Point.customer_id == customer_id,
            Point.type == "客户仓"
        ).all()
    else:
        pts = session.query(Point).filter(Point.type == "客户仓").all()
    return [pt.id for pt in pts]


def _get_customer_points(session: Session, customer_id: int) -> list[int]:
    """
    获取指定客户所有的点位（任意 type，只要 customer_id 匹配）
    用途：采购/供应/拨付的收货点范围
    """
    pts = session.query(Point).filter(Point.customer_id == customer_id).all()
    return [pt.id for pt in pts]


def _get_warehouses_with_sku_stock(session: Session, sku_id: int) -> list[int]:
    """
    物料供应/库存拨付专用：查询所有存有该SKU物料库存的仓库ID
    从 MaterialInventory 批次行查询有库存的点位
    返回匹配到的 Point.id 列表
    """
    mat_invs = session.query(MaterialInventory).filter(
        MaterialInventory.sku_id == sku_id,
        MaterialInventory.qty > 0
    ).all()
    if not mat_invs:
        return []
    wh_ids = list({m.point_id for m in mat_invs if m.point_id})
    pts = session.query(Point).filter(Point.id.in_(wh_ids)).all()
    return [pt.id for pt in pts]


def _get_equipment_stock_points(session: Session, sku_id: int) -> list[int]:
    """
    库存拨付专用：查询所有存有该SKU设备库存的点位ID
    从 EquipmentInventory 查询 point_id（operational_status=STOCK 的记录）
    返回 Point.id 列表
    """
    eqs = session.query(EquipmentInventory).filter(
        EquipmentInventory.sku_id == sku_id,
        EquipmentInventory.operational_status == OperationalStatus.STOCK
    ).all()
    return list({eq.point_id for eq in eqs})


def _get_customer_points_with_sku(session: Session, customer_id: int, sku_id: int) -> list[int]:
    """
    退货4.1专用：查询指定客户下，所有存有该SKU设备的点位（不限type）
    从 EquipmentInventory 查询 point_id，筛选属于该客户任意类型的点位
    返回 Point.id 列表
    """
    # 查找该客户所有点位下有该 SKU 设备的点位ID
    pts = session.query(Point).filter(
        Point.customer_id == customer_id
    ).all()
    customer_point_ids = [pt.id for pt in pts]
    if not customer_point_ids:
        return []

    # 从 EquipmentInventory 找这些点位上有该 SKU 的设备
    from models import SKU
    eqs = session.query(EquipmentInventory).filter(
        EquipmentInventory.point_id.in_(customer_point_ids),
        EquipmentInventory.sku_id == sku_id
    ).all()
    point_ids_with_sku = list({eq.point_id for eq in eqs})
    return point_ids_with_sku


def _get_our_points_with_sku(session: Session, sku_id: int) -> list[int]:
    """
    退货4.2/4.3专用：查询我们有该SKU物料库存的点位
    从 MaterialInventory.stock_distribution 匹配
    返回 Point.id 列表
    """
    return _get_warehouses_with_sku_stock(session, sku_id)


def _elem_to_dict(elem: VCElementSchema) -> dict:
    """将 VCElementSchema 转为字典，用于存入 elements JSON"""
    d = {
        "id": elem.id,
        "shipping_point_id": elem.shipping_point_id,
        "receiving_point_id": elem.receiving_point_id,
        "sku_id": elem.sku_id,
        "qty": elem.qty,
        "price": elem.price,
        "deposit": elem.deposit,
        "subtotal": elem.subtotal,
        "sn_list": elem.sn_list,
        "addon_business_ids": elem.addon_business_ids,
        "batch_no": elem.batch_no,
    }
    return d


def _apply_addons_to_elements(session: Session, business_id: int, elements: list) -> list:
    """
    根据 business 探测当前有效的附加业务，对 elements 中的价格/押金进行绝对值覆盖，
    并在每个元素中标记 addon_business_ids。
    返回增强后的 elements 列表。

    原子化版本：每个 addon_business 记录 = 一个 SKU × 一个周期 × 一个覆盖值，
    不再解析 config JSON，直接按 sku_id + addon_type 精确匹配。
    """
    from logic.addon_business.queries import get_active_addons
    from logic.constants import AddonType

    active_addons = get_active_addons(session, business_id)
    if not active_addons:
        return elements

    # 按 (sku_id, addon_type) 索引（同一 SKU 可能同时有 PRICE_ADJUST 和 NEW_SKU）
    addon_index = {}  # {(sku_id, addon_type): addon}
    for a in active_addons:
        if a.sku_id is not None:
            key = (a.sku_id, a.addon_type)
            if key not in addon_index:  # 同一个 SKU + 类型只保留第一个（理论上不会有重复）
                addon_index[key] = a

    enhanced = []
    for elem in elements:
        elem = dict(elem)  # 复制，避免修改原始数据
        addon_ids = list(elem.get("addon_business_ids") or [])
        sku_id = int(elem["sku_id"])

        # 1. PRICE_ADJUST 覆盖
        pa_key = (sku_id, AddonType.PRICE_ADJUST)
        if pa_key in addon_index:
            a = addon_index[pa_key]
            if a.override_price is not None:
                elem["price"] = a.override_price
                elem["subtotal"] = round(elem["qty"] * elem["price"], 2)
            if a.override_deposit is not None:
                elem["deposit"] = a.override_deposit
            if a.id not in addon_ids:
                addon_ids.append(a.id)

        # 2. NEW_SKU 覆盖（NEW_SKU 同时作为 PRICE_ADJUST 生效，覆盖 price 和 deposit）
        ns_key = (sku_id, AddonType.NEW_SKU)
        if ns_key in addon_index:
            a = addon_index[ns_key]
            if a.override_price is not None:
                elem["price"] = a.override_price
                elem["subtotal"] = round(elem["qty"] * elem["price"], 2)
            if a.override_deposit is not None:
                elem["deposit"] = a.override_deposit
            if a.id not in addon_ids:
                addon_ids.append(a.id)

        elem["addon_business_ids"] = addon_ids
        enhanced.append(elem)

    return enhanced


def _get_point_name(session: Session, point_id: int) -> str:
    """根据点位ID获取点位名称"""
    if not point_id:
        return "默认点位"
    pt = session.query(Point).get(point_id)
    return pt.name if pt else f"点位{point_id}"


def _get_sku_name(session: Session, sku_id: int) -> str:
    """根据SKU ID获取SKU名称"""
    from models import SKU
    sku = session.query(SKU).get(sku_id)
    return sku.name if sku else f"SKU{sku_id}"


# =============================================================================
# VC Action 函数
# =============================================================================

def create_procurement_vc_action(session: Session, payload: CreateProcurementVCSchema, draft_rules: list = None) -> ActionResult:
    """设备采购执行单创建 Action（支持回滚）"""
    import os
    import json as _json
    from logic.finance.engine import VOUCHER_DIR
    try:
        biz = session.query(Business).get(payload.business_id)
        if not biz: return ActionResult(success=False, error="未找到关联业务项目")
        if biz.status not in [BusinessStatus.ACTIVE, BusinessStatus.LANDING]:
            return ActionResult(success=False, error=f"项目当前状态为 {biz.status}，不允许下达采购单")

        sc = None
        if payload.sc_id:
            sc = session.query(SupplyChain).get(payload.sc_id)
            if not sc: return ActionResult(success=False, error="未找到供应链协议")
            if sc.type != SKUType.EQUIPMENT:
                return ActionResult(success=False, error="该协议类型不属于设备供应，无法用于设备采购")

        if not biz.customer_id:
            return ActionResult(success=False, error="业务未关联客户，无法创建设备采购单")
        allowed_receiving = _get_customer_points(session, biz.customer_id)
        if not allowed_receiving:
            return ActionResult(success=False, error=f"客户 {biz.customer_id} 没有可用点位，请先配置")

        # ============ 记录创建前的最大 ID（用于后续捕获新建记录） ============
        from sqlalchemy import func
        max_vc_id_before = session.query(func.max(VirtualContract.id)).scalar() or 0
        max_tr_id_before = session.query(func.max(TimeRule.id)).scalar() or 0
        max_cf_id_before = session.query(func.max(CashFlow.id)).scalar() or 0
        max_fj_id_before = session.query(func.max(FinancialJournal.id)).scalar() or 0
        max_ev_id_before = session.query(func.max(SystemEvent.id)).scalar() or 0

        clean_elems = []
        for e in payload.elements:
            if e.receiving_point_id not in allowed_receiving:
                return ActionResult(success=False, error=f"收货点 {e.receiving_point_id} 不在客户仓库范围内")
            if sc:
                sp = _get_supplier_warehouse(session, sc.supplier_id)
                if not sp:
                    return ActionResult(success=False, error=f"未找到供应商仓库，请检查供应商 {sc.supplier_id} 的仓库配置")
            else:
                sp = None
            corrected = VCElementSchema(
                shipping_point_id=sp,
                receiving_point_id=e.receiving_point_id,
                sku_id=e.sku_id, qty=e.qty, price=e.price,
                deposit=e.deposit, subtotal=e.subtotal, sn_list=e.sn_list
            )
            clean_elems.append(_elem_to_dict(corrected))

        # 提取原始价格（在 _apply_addons 之前），用于同步到 details["pricing"]
        orig_pricing = {}
        for elem in clean_elems:
            sku_key = str(elem["sku_id"])
            if sku_key not in orig_pricing:
                orig_pricing[sku_key] = {"price": elem["price"], "deposit": elem["deposit"]}

        # 应用附加业务政策（价格覆盖 + 标记 addon_business_ids）
        clean_elems = _apply_addons_to_elements(session, payload.business_id, clean_elems)

        new_vc = VirtualContract(
            business_id=payload.business_id,
            supply_chain_id=sc.id if sc else None,
            type=VCType.EQUIPMENT_PROCUREMENT,
            elements={
                "items": clean_elems,
                "total_amount": payload.total_amt,
                "payment_terms": payload.payment
            },
            deposit_info={
                "should_receive": payload.total_deposit,
                "total_deposit": 0.0
            },
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE,
            description=payload.description
        )
        session.add(new_vc)
        session.flush()

        # Sync 原始价格到 business.details["pricing"]（producer）
        biz_pricing = dict(biz.details.get("pricing", {})) if biz.details else {}
        biz_pricing.update(orig_pricing)
        if not biz.details:
            biz.details = {}
        if biz_pricing != biz.details.get("pricing", {}):
            biz.details["pricing"] = biz_pricing
            _attributes.flag_modified(biz, "details")

        _record_vc_created_log(session, new_vc)
        RuleManager(session).sync_from_parent(TimeRuleRelatedType.VIRTUAL_CONTRACT, new_vc.id)
        if draft_rules:
            for r in draft_rules:
                session.add(TimeRule(
                    related_id=new_vc.id, related_type=TimeRuleRelatedType.VIRTUAL_CONTRACT,
                    party=r.get("party"), trigger_event=r.get("trigger_event"),
                    target_event=r.get("target_event"), offset=r.get("offset"),
                    unit=r.get("unit"), direction=r.get("direction"),
                    inherit=r.get("inherit", 0), status=r.get("status", TimeRuleStatus.ACTIVE),
                    timestamp=datetime.now()
                ))
        apply_offset_to_vc(session, new_vc)
        emit_event(session, SystemEventType.VC_CREATED, SystemAggregateType.VIRTUAL_CONTRACT, new_vc.id, {
            "type": new_vc.type, "business_id": new_vc.business_id, "total_amount": payload.total_amt
        })
        session.flush()

        # ============ 构建 snapshot_after：查询所有新建记录 ============
        from logic.transactions import serialize_model as _sm

        # VirtualContract
        snapshot_records = [{"class": "VirtualContract", "id": new_vc.id, "data": _sm(new_vc)}]

        # TimeRule（相关且 ID > max_tr_id_before）
        new_rules = session.query(TimeRule).filter(
            TimeRule.related_id == new_vc.id,
            TimeRule.related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT,
            TimeRule.id > max_tr_id_before
        ).all()
        for tr in new_rules:
            snapshot_records.append({"class": "TimeRule", "id": tr.id, "data": _sm(tr)})

        # CashFlow（ref_vc_id = new_vc.id 且 ID > max_cf_id_before）
        new_cfs = session.query(CashFlow).filter(
            CashFlow.virtual_contract_id == new_vc.id,
            CashFlow.id > max_cf_id_before
        ).all()
        for cf in new_cfs:
            snapshot_records.append({"class": "CashFlow", "id": cf.id, "data": _sm(cf)})

        # FinancialJournal（ref_vc_id = new_vc.id 且 ID > max_fj_id_before）
        new_fjs = session.query(FinancialJournal).filter(
            FinancialJournal.ref_vc_id == new_vc.id,
            FinancialJournal.id > max_fj_id_before
        ).all()
        for fj in new_fjs:
            snapshot_records.append({"class": "FinancialJournal", "id": fj.id, "data": _sm(fj)})
            if fj.cash_flow_record:
                snapshot_records.append({"class": "CashFlowLedger", "id": fj.cash_flow_record.id, "data": _sm(fj.cash_flow_record)})

        # SystemEvent（aggregate_id = new_vc.id 且 ID > max_ev_id_before）
        new_evs = session.query(SystemEvent).filter(
            SystemEvent.aggregate_id == new_vc.id,
            SystemEvent.aggregate_type == SystemAggregateType.VIRTUAL_CONTRACT,
            SystemEvent.id > max_ev_id_before
        ).all()
        for ev in new_evs:
            snapshot_records.append({"class": "SystemEvent", "id": ev.id, "data": _sm(ev)})

        # JSON 文件（可能有多个 CashFlow）
        snapshot_files = []
        for cf in new_cfs:
            voucher_path = os.path.join(VOUCHER_DIR, f"CashFlow_{cf.id}.json")
            if os.path.exists(voucher_path):
                with open(voucher_path, "r", encoding="utf-8") as f:
                    snapshot_files.append({"path": voucher_path, "content": _json.load(f)})

        snapshot_after = {"records": snapshot_records, "files": snapshot_files}

        from logic.transactions import create_operation_record
        involved_ids = [new_vc.id] + [tr.id for tr in new_rules] + [cf.id for cf in new_cfs] + [fj.id for fj in new_fjs]

        tx_id = create_operation_record(
            session,
            action_name="create_procurement_vc_action",
            ref_type="VirtualContract",
            ref_id=new_vc.id,
            ref_vc_id=new_vc.id,
            snapshot_before={},
            snapshot_after=snapshot_after,
            involved_ids=involved_ids,
        )

        session.commit()
        return ActionResult(success=True, data={"vc_id": new_vc.id}, message=f"设备采购单 VC-{new_vc.id} 创建成功")
    except Exception as e:
        session.rollback()
        if isinstance(e, BusinessError):
            raise
        return ActionResult(success=False, error=str(e))

def create_material_supply_vc_action(session: Session, payload: CreateMaterialSupplyVCSchema, draft_rules: list = None) -> ActionResult:
    """物料供应执行单创建 Action（支持回滚）"""
    import os
    import json as _json
    from logic.finance.engine import VOUCHER_DIR
    try:
        biz = session.query(Business).get(payload.business_id)
        if not biz: return ActionResult(success=False, error="未找到关联业务项目")
        if biz.status not in [BusinessStatus.ACTIVE, BusinessStatus.LANDING]:
            return ActionResult(success=False, error=f"项目尚未正式开展 (当前状态: {biz.status})，无法进行物料供应")

        from logic.services import validate_inventory_availability

        if not biz.customer_id:
            return ActionResult(success=False, error="业务未关联客户，无法创建物料供应单")

        # ============ 记录创建前的最大 ID（用于后续捕获新建记录） ============
        max_vc_id_before = session.query(func.max(VirtualContract.id)).scalar() or 0
        max_tr_id_before = session.query(func.max(TimeRule.id)).scalar() or 0
        max_cf_id_before = session.query(func.max(CashFlow.id)).scalar() or 0
        max_fj_id_before = session.query(func.max(FinancialJournal.id)).scalar() or 0
        max_ev_id_before = session.query(func.max(SystemEvent.id)).scalar() or 0

        # 商业逻辑
        # shipping_point_id：用户选择，范围=有该SKU库存的所有仓库
        # receiving_point_id：用户选择，范围=客户所有点位（运营点位+仓库）
        allowed_shipping_by_sku = {}
        allowed_receiving = _get_customer_points(session, biz.customer_id)
        if not allowed_receiving:
            return ActionResult(success=False, error=f"客户 {biz.customer_id} 没有可用点位，请先配置")

        check_items = []
        clean_elems = []
        for e in payload.elements:
            # 校验收货点
            if e.receiving_point_id not in allowed_receiving:
                return ActionResult(success=False, error=f"收货点 {e.receiving_point_id} 不在客户运营点位范围内")

            # 校验/获取该SKU的可用发货仓库
            if e.sku_id not in allowed_shipping_by_sku:
                allowed_shipping_by_sku[e.sku_id] = set(_get_warehouses_with_sku_stock(session, e.sku_id))
            allowed_sp = allowed_shipping_by_sku[e.sku_id]
            if not allowed_sp:
                return ActionResult(success=False, error=f"SKU {e.sku_id} 在任何仓库都没有库存，无法供应")
            if e.shipping_point_id not in allowed_sp:
                return ActionResult(success=False, error=f"发货点 {e.shipping_point_id} 没有 SKU {e.sku_id} 的库存")

            corrected = VCElementSchema(
                shipping_point_id=e.shipping_point_id,
                receiving_point_id=e.receiving_point_id,
                sku_id=e.sku_id, qty=e.qty, price=e.price,
                deposit=e.deposit, subtotal=e.subtotal, sn_list=e.sn_list,
                batch_no=e.batch_no
            )
            clean_elems.append(_elem_to_dict(corrected))
            check_items.append((_get_sku_name(session, e.sku_id), _get_point_name(session, e.shipping_point_id), e.qty))

        # 应用附加业务政策（价格覆盖 + 标记 addon_business_ids）
        clean_elems = _apply_addons_to_elements(session, payload.business_id, clean_elems)

        is_ok, over_stock = validate_inventory_availability(session, check_items)
        if not is_ok:
            return ActionResult(success=False, error=f"库存严重不足: {' | '.join(over_stock)}")
        payment_terms = (biz.details or {}).get("payment_terms", {})
        new_vc = VirtualContract(
            business_id=payload.business_id,
            type=VCType.MATERIAL_SUPPLY,
            elements={
                "items": clean_elems,
                "total_amount": payload.total_amt,
                "payment_terms": payment_terms
            },
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE,
            description=payload.description
        )
        session.add(new_vc)
        session.flush()
        _record_vc_created_log(session, new_vc)
        RuleManager(session).sync_from_parent(TimeRuleRelatedType.VIRTUAL_CONTRACT, new_vc.id)
        if draft_rules:
            for r in draft_rules:
                session.add(TimeRule(
                    related_id=new_vc.id, related_type=TimeRuleRelatedType.VIRTUAL_CONTRACT,
                    party=r.get("party"), trigger_event=r.get("trigger_event"),
                    target_event=r.get("target_event"), offset=r.get("offset"),
                    unit=r.get("unit"), direction=r.get("direction"),
                    inherit=r.get("inherit", 0), status=r.get("status", TimeRuleStatus.ACTIVE),
                    timestamp=datetime.now()
                ))
        apply_offset_to_vc(session, new_vc)
        emit_event(session, SystemEventType.VC_CREATED, SystemAggregateType.VIRTUAL_CONTRACT, new_vc.id, {
            "type": new_vc.type, "business_id": new_vc.business_id, "total_amount": payload.total_amt
        })
        session.flush()

        # ============ 构建 snapshot_after：查询所有新建记录 ============
        from logic.transactions import serialize_model as _sm

        snapshot_records = [{"class": "VirtualContract", "id": new_vc.id, "data": _sm(new_vc)}]

        new_rules = session.query(TimeRule).filter(
            TimeRule.related_id == new_vc.id,
            TimeRule.related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT,
            TimeRule.id > max_tr_id_before
        ).all()
        for tr in new_rules:
            snapshot_records.append({"class": "TimeRule", "id": tr.id, "data": _sm(tr)})

        new_cfs = session.query(CashFlow).filter(
            CashFlow.virtual_contract_id == new_vc.id,
            CashFlow.id > max_cf_id_before
        ).all()
        for cf in new_cfs:
            snapshot_records.append({"class": "CashFlow", "id": cf.id, "data": _sm(cf)})

        new_fjs = session.query(FinancialJournal).filter(
            FinancialJournal.ref_vc_id == new_vc.id,
            FinancialJournal.id > max_fj_id_before
        ).all()
        for fj in new_fjs:
            snapshot_records.append({"class": "FinancialJournal", "id": fj.id, "data": _sm(fj)})
            if fj.cash_flow_record:
                snapshot_records.append({"class": "CashFlowLedger", "id": fj.cash_flow_record.id, "data": _sm(fj.cash_flow_record)})

        new_evs = session.query(SystemEvent).filter(
            SystemEvent.aggregate_id == new_vc.id,
            SystemEvent.aggregate_type == SystemAggregateType.VIRTUAL_CONTRACT,
            SystemEvent.id > max_ev_id_before
        ).all()
        for ev in new_evs:
            snapshot_records.append({"class": "SystemEvent", "id": ev.id, "data": _sm(ev)})

        snapshot_files = []
        for cf in new_cfs:
            voucher_path = os.path.join(VOUCHER_DIR, f"CashFlow_{cf.id}.json")
            if os.path.exists(voucher_path):
                with open(voucher_path, "r", encoding="utf-8") as f:
                    snapshot_files.append({"path": voucher_path, "content": _json.load(f)})

        snapshot_after = {"records": snapshot_records, "files": snapshot_files}

        from logic.transactions import create_operation_record
        involved_ids = [new_vc.id] + [tr.id for tr in new_rules] + [cf.id for cf in new_cfs] + [fj.id for fj in new_fjs]

        tx_id = create_operation_record(
            session,
            action_name="create_material_supply_vc_action",
            ref_type="VirtualContract",
            ref_id=new_vc.id,
            ref_vc_id=new_vc.id,
            snapshot_before={},
            snapshot_after=snapshot_after,
            involved_ids=involved_ids,
        )

        session.commit()
        return ActionResult(success=True, data={"vc_id": new_vc.id}, message=f"物料供应单 VC-{new_vc.id} 创建成功")
    except Exception as e:
        session.rollback()
        if isinstance(e, BusinessError):
            raise
        return ActionResult(success=False, error=str(e))

def create_return_vc_action(session: Session, payload: CreateReturnVCSchema, draft_rules: list = None) -> ActionResult:
    """退货执行单创建 Action（支持回滚）

    物料退货按批次维度校验：
    - 从 get_returnable_items 获取每个批次的跨VC汇总可退量
    - 校验 payload.elements 中每个 element 的 qty <= 可退量
    - 向供应商退货时 deposit_amount 必须为 0
    - elements 中附加 source_vc_ids、original_qty（系统内部字段）
    - 不调用 apply_offset_to_vc（退货VC不自动核销）
    """
    import os
    import json as _json
    from logic.finance.engine import VOUCHER_DIR
    try:
        target_vc = session.query(VirtualContract).get(payload.target_vc_id)
        if not target_vc:
            return ActionResult(success=False, error="未找到目标虚拟合同")

        if target_vc.subject_status not in [SubjectStatus.EXE, SubjectStatus.FINISH]:
            return ActionResult(success=False, error=f"原单标的状态为 {target_vc.subject_status}，此时无法发起退货")

        # -------------------------------------------------------
        # 批次维度可退量查询
        # -------------------------------------------------------
        from logic.services import get_returnable_items
        allowed_items = get_returnable_items(session, target_vc.id, payload.return_direction)

        # 构建 allowed_map: key = (sku_id, batch_no), value = 可退量
        allowed_map = {}
        source_vc_ids_map = {}   # key = (sku_id, batch_no) -> list of source_vc_ids
        original_qty_map = {}    # key = (sku_id, batch_no) -> original_qty
        for ai in allowed_items:
            key = (ai['sku_id'], ai.get('batch_no'))
            allowed_map[key] = allowed_map.get(key, 0) + ai['qty']
            if ai.get('source_vc_ids'):
                source_vc_ids_map[key] = ai['source_vc_ids']
            if 'original_qty' in ai:
                original_qty_map[key] = original_qty_map.get(key, 0) + ai['original_qty']

        # -------------------------------------------------------
        # 批次维度越界校验
        # -------------------------------------------------------
        for ri in payload.elements:
            key = (ri.sku_id, ri.batch_no)
            avail = allowed_map.get(key, 0)
            if ri.qty > avail:
                bn = ri.batch_no or '-'
                return ActionResult(success=False, error=f"退货越界: SKU {ri.sku_id} 批次 {bn} 申请退货 {ri.qty}，而最大可退仅 {avail}")

        # 向供应商退货时，押金必须为 0
        if payload.return_direction == ReturnDirection.US_TO_SUPPLIER and payload.deposit_amount > 0:
            return ActionResult(success=False, error="向供应商退货时 deposit_amount 必须为 0")

        # -------------------------------------------------------
        # 商业逻辑：确定退货收货点
        # -------------------------------------------------------
        target_type = target_vc.type
        is_equipment_target = target_type in (VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT)
        is_mat_target = target_type == VCType.MATERIAL_PROCUREMENT

        rp_target = None  # 退货目的地（收货点）
        if payload.return_direction == ReturnDirection.US_TO_SUPPLIER:
            if is_equipment_target:
                if target_vc.supply_chain_id:
                    sc = session.query(SupplyChain).get(target_vc.supply_chain_id)
                    if sc:
                        rp_target = _get_supplier_warehouse(session, sc.supplier_id)
            elif is_mat_target:
                if target_vc.supply_chain_id:
                    sc = session.query(SupplyChain).get(target_vc.supply_chain_id)
                    if sc:
                        rp_target = _get_supplier_warehouse(session, sc.supplier_id)
            if not rp_target:
                return ActionResult(success=False, error="无法确定退货目的地供应商仓库")
        else:
            # 客户退回：我方仓库
            rp_target = DEFAULT_WAREHOUSE_ID

        # -------------------------------------------------------
        # 构建 clean_elems，附加 source_vc_ids / original_qty
        # -------------------------------------------------------
        clean_elems = []
        for e in payload.elements:
            key = (e.sku_id, e.batch_no)
            src_vcs = source_vc_ids_map.get(key, [target_vc.id])
            orig_qty = original_qty_map.get(key, e.qty)

            corrected = VCElementSchema(
                shipping_point_id=e.shipping_point_id,
                receiving_point_id=rp_target,
                sku_id=e.sku_id,
                batch_no=e.batch_no,
                qty=e.qty,
                price=e.price,
                deposit=e.deposit,
                subtotal=e.subtotal,
                sn_list=e.sn_list,
                addon_business_ids=e.addon_business_ids,
                # 系统内部字段（extra=allow）
                source_vc_ids=src_vcs,
                original_qty=orig_qty,
            )
            elem_dict = _elem_to_dict(corrected)
            # 确保系统内部字段被存入
            elem_dict['source_vc_ids'] = src_vcs
            elem_dict['original_qty'] = orig_qty
            clean_elems.append(elem_dict)

        # 应用附加业务政策
        clean_elems = _apply_addons_to_elements(session, target_vc.business_id, clean_elems)

        # ============ 记录创建前的最大 ID ============
        max_vc_id_before = session.query(func.max(VirtualContract.id)).scalar() or 0
        max_tr_id_before = session.query(func.max(TimeRule.id)).scalar() or 0
        max_cf_id_before = session.query(func.max(CashFlow.id)).scalar() or 0
        max_fj_id_before = session.query(func.max(FinancialJournal.id)).scalar() or 0
        max_ev_id_before = session.query(func.max(SystemEvent.id)).scalar() or 0

        new_vc = VirtualContract(
            related_vc_id=payload.target_vc_id,
            business_id=target_vc.business_id,
            supply_chain_id=target_vc.supply_chain_id,
            type=VCType.RETURN,
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE if payload.total_refund > 0 else CashStatus.FINISH,
            description=payload.description,
            return_direction=payload.return_direction,
            elements={
                "items": clean_elems,
                "goods_amount": payload.goods_amount,
                "deposit_amount": payload.deposit_amount,
                "total_refund": payload.total_refund,
                "total_amount": payload.total_refund,
                "reason": payload.reason,
                "logistics_cost": payload.logistics_cost,
                "logistics_bearer": payload.logistics_bearer,
            },
            deposit_info={"should_receive": payload.deposit_amount, "total_deposit": 0.0},
        )
        session.add(new_vc)
        session.flush()
        _record_vc_created_log(session, new_vc)
        RuleManager(session).sync_from_parent(TimeRuleRelatedType.VIRTUAL_CONTRACT, new_vc.id)
        if draft_rules:
            for r in draft_rules:
                session.add(TimeRule(
                    related_id=new_vc.id,
                    related_type=TimeRuleRelatedType.VIRTUAL_CONTRACT,
                    party=r.get("party"),
                    trigger_event=r.get("trigger_event"),
                    target_event=r.get("target_event"),
                    offset=r.get("offset"),
                    unit=r.get("unit"),
                    direction=r.get("direction"),
                    inherit=r.get("inherit", 0),
                    status=r.get("status", TimeRuleStatus.ACTIVE),
                    timestamp=datetime.now()
                ))
        # 注意：不调用 apply_offset_to_vc，退货VC不自动核销
        emit_event(session, SystemEventType.VC_CREATED, SystemAggregateType.VIRTUAL_CONTRACT, new_vc.id, {
            "type": new_vc.type,
            "business_id": new_vc.business_id,
            "related_vc_id": new_vc.related_vc_id,
            "total_refund": payload.total_refund,
        })
        session.flush()

        # ============ 构建 snapshot_after ============
        from logic.transactions import serialize_model as _sm

        snapshot_records = [{"class": "VirtualContract", "id": new_vc.id, "data": _sm(new_vc)}]

        new_rules = session.query(TimeRule).filter(
            TimeRule.related_id == new_vc.id,
            TimeRule.related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT,
            TimeRule.id > max_tr_id_before
        ).all()
        for tr in new_rules:
            snapshot_records.append({"class": "TimeRule", "id": tr.id, "data": _sm(tr)})

        new_cfs = session.query(CashFlow).filter(
            CashFlow.virtual_contract_id == new_vc.id,
            CashFlow.id > max_cf_id_before
        ).all()
        for cf in new_cfs:
            snapshot_records.append({"class": "CashFlow", "id": cf.id, "data": _sm(cf)})

        new_fjs = session.query(FinancialJournal).filter(
            FinancialJournal.ref_vc_id == new_vc.id,
            FinancialJournal.id > max_fj_id_before
        ).all()
        for fj in new_fjs:
            snapshot_records.append({"class": "FinancialJournal", "id": fj.id, "data": _sm(fj)})
            if fj.cash_flow_record:
                snapshot_records.append({"class": "CashFlowLedger", "id": fj.cash_flow_record.id, "data": _sm(fj.cash_flow_record)})

        new_evs = session.query(SystemEvent).filter(
            SystemEvent.aggregate_id == new_vc.id,
            SystemEvent.aggregate_type == SystemAggregateType.VIRTUAL_CONTRACT,
            SystemEvent.id > max_ev_id_before
        ).all()
        for ev in new_evs:
            snapshot_records.append({"class": "SystemEvent", "id": ev.id, "data": _sm(ev)})

        snapshot_files = []
        for cf in new_cfs:
            voucher_path = os.path.join(VOUCHER_DIR, f"CashFlow_{cf.id}.json")
            if os.path.exists(voucher_path):
                with open(voucher_path, "r", encoding="utf-8") as f:
                    snapshot_files.append({"path": voucher_path, "content": _json.load(f)})

        snapshot_after = {"records": snapshot_records, "files": snapshot_files}

        from logic.transactions import create_operation_record
        involved_ids = [new_vc.id] + [tr.id for tr in new_rules] + [cf.id for cf in new_cfs] + [fj.id for fj in new_fjs]

        tx_id = create_operation_record(
            session,
            action_name="create_return_vc_action",
            ref_type="VirtualContract",
            ref_id=new_vc.id,
            ref_vc_id=new_vc.id,
            snapshot_before={},
            snapshot_after=snapshot_after,
            involved_ids=involved_ids,
        )

        session.commit()
        return ActionResult(success=True, data={"vc_id": new_vc.id}, message=f"退货单 VC-{new_vc.id} 创建成功")
    except Exception as e:
        session.rollback()
        if isinstance(e, BusinessError):
            raise
        return ActionResult(success=False, error=str(e))



def update_vc_action(session: Session, payload: UpdateVCSchema) -> ActionResult:
    """底层 VC 数据修正 Action（支持回滚）"""
    try:
        vc = session.query(VirtualContract).get(payload.id)
        if not vc: raise_not_found_error("虚拟合同", str(payload.id))

        # snapshot_before：捕获修改前的值（UPDATE 类型）
        from logic.transactions import serialize_model
        snapshot_before = {"records": [{"class": "VirtualContract", "id": vc.id, "data": serialize_model(vc)}]}

        session.begin_nested()

        if payload.description is not None:
            vc.description = payload.description
        if payload.elements is not None:
            vc.elements = payload.elements
        if payload.deposit_info is not None:
            vc.deposit_info = payload.deposit_info

        # emit_event 内部 flush 后 SystemEvent 不在 session.new 中，用返回值引用它
        system_event = emit_event(session, SystemEventType.VC_UPDATED, SystemAggregateType.VIRTUAL_CONTRACT, vc.id, {"desc": vc.description})

        # snapshot_after：修改后的 VC + SystemEvent（flush 后 session.new 已清，用 serialize_model）
        from logic.transactions import serialize_model as _sm
        snapshot_after = {"records": [
            {"class": "VirtualContract", "id": vc.id, "data": _sm(vc)},
            {"class": "SystemEvent", "id": system_event.id, "data": _sm(system_event)},
        ]}

        from logic.transactions import create_operation_record
        tx_id = create_operation_record(
            session,
            action_name="update_vc_action",
            ref_type="VirtualContract",
            ref_id=vc.id,
            ref_vc_id=vc.id,
            snapshot_before=snapshot_before,
            involved_ids=[vc.id],
        )

        session.commit()
        return ActionResult(success=True, message="底层数据已更新")
    except Exception as e:
        session.rollback()
        if isinstance(e, BusinessError):
            raise
        return ActionResult(success=False, error=str(e))

def delete_vc_action(session: Session, payload: DeleteVCSchema) -> ActionResult:
    """物理删除 VC Action (含级联清理，支持回滚)"""
    try:
        from models import Logistics, CashFlow, FinancialJournal, TimeRule, EquipmentInventory
        from logic.transactions import serialize_model

        vc_id = payload.id
        vc = session.query(VirtualContract).get(vc_id)
        if not vc: raise_not_found_error("虚拟合同", str(vc_id))

        # FK 完整性检查：检查是否有下游引用阻止删除
        cf_count = session.query(CashFlow).filter(CashFlow.virtual_contract_id == vc_id).count()
        if cf_count > 0:
            return ActionResult(success=False, error=f"该合同存在 {cf_count} 条资金流水，无法直接删除，请先删除关联资金流水")

        fj_count = session.query(FinancialJournal).filter(
            FinancialJournal.ref_type == "VirtualContract",
            FinancialJournal.ref_id == vc_id
        ).count()
        if fj_count > 0:
            return ActionResult(success=False, error=f"该合同存在 {fj_count} 条财务凭证，无法直接删除")

        ei_count = session.query(EquipmentInventory).filter(EquipmentInventory.virtual_contract_id == vc_id).count()
        if ei_count > 0:
            return ActionResult(success=False, error=f"该合同关联了 {ei_count} 条设备库存记录，无法直接删除")

        # snapshot_before：捕获 VC + Logistics（删除前的完整状态）
        snapshot_before = {"records": [
            {"class": "VirtualContract", "id": vc.id, "data": serialize_model(vc)},
        ]}
        logistics_list = session.query(Logistics).filter(Logistics.virtual_contract_id == vc_id).all()
        for log in logistics_list:
            snapshot_before["records"].append({"class": "Logistics", "id": log.id, "data": serialize_model(log)})

        session.begin_nested()

        session.query(Logistics).filter(Logistics.virtual_contract_id == vc_id).delete()
        session.delete(vc)

        system_event = emit_event(session, SystemEventType.VC_DELETED, SystemAggregateType.VIRTUAL_CONTRACT, vc_id)

        # snapshot_after：空（删除操作无新记录，SystemEvent 已在 snapshot_before 中）
        snapshot_after = {}

        from logic.transactions import create_operation_record
        tx_id = create_operation_record(
            session,
            action_name="delete_vc_action",
            ref_type="VirtualContract",
            ref_id=vc_id,
            ref_vc_id=vc_id,
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            involved_ids=[vc_id] + [log.id for log in logistics_list],
        )

        session.commit()
        return ActionResult(success=True, message="该虚拟合同已从系统中完全移除")
    except Exception as e:
        session.rollback()
        if isinstance(e, BusinessError):
            raise
        return ActionResult(success=False, error=str(e))

def create_mat_procurement_vc_action(session: Session, payload: CreateMatProcurementVCSchema, draft_rules: list = None) -> ActionResult:
    """物料采购执行单创建 Action（支持回滚）"""
    import os
    import json as _json
    from logic.finance.engine import VOUCHER_DIR
    try:
        sc = session.query(SupplyChain).get(payload.sc_id)
        if not sc or sc.type != SKUType.MATERIAL:
            return ActionResult(success=False, error="无效的物料供应链协议")

        # ============ 记录创建前的最大 ID ============
        max_vc_id_before = session.query(func.max(VirtualContract.id)).scalar() or 0
        max_tr_id_before = session.query(func.max(TimeRule.id)).scalar() or 0
        max_cf_id_before = session.query(func.max(CashFlow.id)).scalar() or 0
        max_fj_id_before = session.query(func.max(FinancialJournal.id)).scalar() or 0
        max_ev_id_before = session.query(func.max(SystemEvent.id)).scalar() or 0

        # 商业逻辑
        # shipping_point_id = 供应商仓库（由sc.supplier_id确定）
        # receiving_point_id = 用户选择，范围=我们仓库+供应商仓库+客户仓库
        sp = _get_supplier_warehouse(session, sc.supplier_id)
        if not sp:
            return ActionResult(success=False, error=f"未找到供应商 {sc.supplier_id} 的仓库配置")

        our_wh_ids = _get_our_warehouses(session)
        supplier_wh_ids = _get_supplier_warehouses(session, sc.supplier_id)
        customer_wh_ids = _get_customer_warehouses(session)
        allowed_receiving = list(set(our_wh_ids + supplier_wh_ids + customer_wh_ids))
        if not allowed_receiving:
            return ActionResult(success=False, error="没有可用的收货仓库")

        clean_elems = []
        for e in payload.elements:
            if e.receiving_point_id not in allowed_receiving:
                return ActionResult(success=False, error=f"收货点 {e.receiving_point_id} 不在允许的仓库范围内（我们仓库+供应商仓库+客户仓库）")

            corrected = VCElementSchema(
                shipping_point_id=sp,
                receiving_point_id=e.receiving_point_id,
                sku_id=e.sku_id, qty=e.qty, price=e.price,
                deposit=e.deposit, subtotal=e.subtotal, sn_list=e.sn_list,
                batch_no=e.batch_no
            )
            clean_elems.append(_elem_to_dict(corrected))
        new_vc = VirtualContract(
            supply_chain_id=payload.sc_id,
            type=VCType.MATERIAL_PROCUREMENT,
            elements={
                "items": clean_elems,
                "total_amount": payload.total_amt,
                "payment_terms": payload.payment
            },
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE,
            description=payload.description or f"物料采购: {len(clean_elems)}项物料"
        )
        session.add(new_vc)
        session.flush()
        _record_vc_created_log(session, new_vc)
        RuleManager(session).sync_from_parent(TimeRuleRelatedType.VIRTUAL_CONTRACT, new_vc.id)
        if draft_rules:
            for r in draft_rules:
                session.add(TimeRule(
                    related_id=new_vc.id, related_type=TimeRuleRelatedType.VIRTUAL_CONTRACT,
                    party=r.get("party"), trigger_event=r.get("trigger_event"),
                    target_event=r.get("target_event"), offset=r.get("offset"),
                    unit=r.get("unit"), direction=r.get("direction"),
                    inherit=r.get("inherit", 0), status=r.get("status", TimeRuleStatus.ACTIVE),
                    timestamp=datetime.now()
                ))
        apply_offset_to_vc(session, new_vc)
        emit_event(session, SystemEventType.VC_CREATED, SystemAggregateType.VIRTUAL_CONTRACT, new_vc.id, {"type": new_vc.type, "total_amount": payload.total_amt})
        session.flush()

        # ============ 构建 snapshot_after ============
        from logic.transactions import serialize_model as _sm

        snapshot_records = [{"class": "VirtualContract", "id": new_vc.id, "data": _sm(new_vc)}]

        new_rules = session.query(TimeRule).filter(
            TimeRule.related_id == new_vc.id,
            TimeRule.related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT,
            TimeRule.id > max_tr_id_before
        ).all()
        for tr in new_rules:
            snapshot_records.append({"class": "TimeRule", "id": tr.id, "data": _sm(tr)})

        new_cfs = session.query(CashFlow).filter(
            CashFlow.virtual_contract_id == new_vc.id,
            CashFlow.id > max_cf_id_before
        ).all()
        for cf in new_cfs:
            snapshot_records.append({"class": "CashFlow", "id": cf.id, "data": _sm(cf)})

        new_fjs = session.query(FinancialJournal).filter(
            FinancialJournal.ref_vc_id == new_vc.id,
            FinancialJournal.id > max_fj_id_before
        ).all()
        for fj in new_fjs:
            snapshot_records.append({"class": "FinancialJournal", "id": fj.id, "data": _sm(fj)})
            if fj.cash_flow_record:
                snapshot_records.append({"class": "CashFlowLedger", "id": fj.cash_flow_record.id, "data": _sm(fj.cash_flow_record)})

        new_evs = session.query(SystemEvent).filter(
            SystemEvent.aggregate_id == new_vc.id,
            SystemEvent.aggregate_type == SystemAggregateType.VIRTUAL_CONTRACT,
            SystemEvent.id > max_ev_id_before
        ).all()
        for ev in new_evs:
            snapshot_records.append({"class": "SystemEvent", "id": ev.id, "data": _sm(ev)})

        snapshot_files = []
        for cf in new_cfs:
            voucher_path = os.path.join(VOUCHER_DIR, f"CashFlow_{cf.id}.json")
            if os.path.exists(voucher_path):
                with open(voucher_path, "r", encoding="utf-8") as f:
                    snapshot_files.append({"path": voucher_path, "content": _json.load(f)})

        snapshot_after = {"records": snapshot_records, "files": snapshot_files}

        from logic.transactions import create_operation_record
        involved_ids = [new_vc.id] + [tr.id for tr in new_rules] + [cf.id for cf in new_cfs] + [fj.id for fj in new_fjs]

        tx_id = create_operation_record(
            session,
            action_name="create_mat_procurement_vc_action",
            ref_type="VirtualContract",
            ref_id=new_vc.id,
            ref_vc_id=new_vc.id,
            snapshot_before={},
            snapshot_after=snapshot_after,
            involved_ids=involved_ids,
        )

        session.commit()
        return ActionResult(success=True, data={"vc_id": new_vc.id}, message=f"物料采购单 VC-{new_vc.id} 创建成功")
    except Exception as e:
        session.rollback()
        if isinstance(e, BusinessError):
            raise
        return ActionResult(success=False, error=str(e))

def create_stock_procurement_vc_action(session: Session, payload: CreateStockProcurementVCSchema, draft_rules: list = None) -> ActionResult:
    """库存采购执行单创建 Action（支持回滚）"""
    import os
    import json as _json
    from logic.finance.engine import VOUCHER_DIR
    try:
        sc = session.query(SupplyChain).get(payload.sc_id)
        if not sc or sc.type != SKUType.EQUIPMENT:
            return ActionResult(success=False, error="无效的设备供应链协议")

        # ============ 记录创建前的最大 ID ============
        max_vc_id_before = session.query(func.max(VirtualContract.id)).scalar() or 0
        max_tr_id_before = session.query(func.max(TimeRule.id)).scalar() or 0
        max_cf_id_before = session.query(func.max(CashFlow.id)).scalar() or 0
        max_fj_id_before = session.query(func.max(FinancialJournal.id)).scalar() or 0
        max_ev_id_before = session.query(func.max(SystemEvent.id)).scalar() or 0

        # 商业逻辑
        # shipping_point_id = 供应商仓库（由sc.supplier_id确定）
        # receiving_point_id = 用户选择，范围=我们仓库+供应商仓库+客户仓库
        sp = _get_supplier_warehouse(session, sc.supplier_id)
        if not sp:
            return ActionResult(success=False, error=f"未找到供应商 {sc.supplier_id} 的仓库配置")

        our_wh_ids = _get_our_warehouses(session)
        supplier_wh_ids = _get_supplier_warehouses(session, sc.supplier_id)
        customer_wh_ids = _get_customer_warehouses(session)
        allowed_receiving = list(set(our_wh_ids + supplier_wh_ids + customer_wh_ids))
        if not allowed_receiving:
            return ActionResult(success=False, error="没有可用的收货仓库")

        clean_elems = []
        for e in payload.elements:
            if e.receiving_point_id not in allowed_receiving:
                return ActionResult(success=False, error=f"收货点 {e.receiving_point_id} 不在允许的仓库范围内（我们仓库+供应商仓库+客户仓库）")

            corrected = VCElementSchema(
                shipping_point_id=sp,
                receiving_point_id=e.receiving_point_id,
                sku_id=e.sku_id, qty=e.qty, price=e.price,
                deposit=e.deposit, subtotal=e.subtotal, sn_list=e.sn_list
            )
            clean_elems.append(_elem_to_dict(corrected))
        new_vc = VirtualContract(
            business_id=None,
            supply_chain_id=payload.sc_id,
            type=VCType.STOCK_PROCUREMENT,
            elements={
                "items": clean_elems,
                "total_amount": payload.total_amt,
                "payment_terms": payload.payment
            },
            deposit_info={"should_receive": 0.0, "total_deposit": 0.0},
            status=VCStatus.EXE,
            subject_status=SubjectStatus.EXE,
            cash_status=CashStatus.EXE,
            description=payload.description or f"库存采购: {len(clean_elems)}项设备"
        )
        session.add(new_vc)
        session.flush()
        _record_vc_created_log(session, new_vc)
        RuleManager(session).sync_from_parent(TimeRuleRelatedType.VIRTUAL_CONTRACT, new_vc.id)
        if draft_rules:
            for r in draft_rules:
                session.add(TimeRule(
                    related_id=new_vc.id, related_type=TimeRuleRelatedType.VIRTUAL_CONTRACT,
                    party=r.get("party"), trigger_event=r.get("trigger_event"),
                    target_event=r.get("target_event"), offset=r.get("offset"),
                    unit=r.get("unit"), direction=r.get("direction"),
                    inherit=r.get("inherit", 0), status=r.get("status", TimeRuleStatus.ACTIVE),
                    timestamp=datetime.now()
                ))
        apply_offset_to_vc(session, new_vc)
        emit_event(session, SystemEventType.VC_CREATED, SystemAggregateType.VIRTUAL_CONTRACT, new_vc.id, {"type": new_vc.type, "total_amount": payload.total_amt})
        session.flush()

        # ============ 构建 snapshot_after ============
        from logic.transactions import serialize_model as _sm

        snapshot_records = [{"class": "VirtualContract", "id": new_vc.id, "data": _sm(new_vc)}]

        new_rules = session.query(TimeRule).filter(
            TimeRule.related_id == new_vc.id,
            TimeRule.related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT,
            TimeRule.id > max_tr_id_before
        ).all()
        for tr in new_rules:
            snapshot_records.append({"class": "TimeRule", "id": tr.id, "data": _sm(tr)})

        new_cfs = session.query(CashFlow).filter(
            CashFlow.virtual_contract_id == new_vc.id,
            CashFlow.id > max_cf_id_before
        ).all()
        for cf in new_cfs:
            snapshot_records.append({"class": "CashFlow", "id": cf.id, "data": _sm(cf)})

        new_fjs = session.query(FinancialJournal).filter(
            FinancialJournal.ref_vc_id == new_vc.id,
            FinancialJournal.id > max_fj_id_before
        ).all()
        for fj in new_fjs:
            snapshot_records.append({"class": "FinancialJournal", "id": fj.id, "data": _sm(fj)})
            if fj.cash_flow_record:
                snapshot_records.append({"class": "CashFlowLedger", "id": fj.cash_flow_record.id, "data": _sm(fj.cash_flow_record)})

        new_evs = session.query(SystemEvent).filter(
            SystemEvent.aggregate_id == new_vc.id,
            SystemEvent.aggregate_type == SystemAggregateType.VIRTUAL_CONTRACT,
            SystemEvent.id > max_ev_id_before
        ).all()
        for ev in new_evs:
            snapshot_records.append({"class": "SystemEvent", "id": ev.id, "data": _sm(ev)})

        snapshot_files = []
        for cf in new_cfs:
            voucher_path = os.path.join(VOUCHER_DIR, f"CashFlow_{cf.id}.json")
            if os.path.exists(voucher_path):
                with open(voucher_path, "r", encoding="utf-8") as f:
                    snapshot_files.append({"path": voucher_path, "content": _json.load(f)})

        snapshot_after = {"records": snapshot_records, "files": snapshot_files}

        from logic.transactions import create_operation_record
        involved_ids = [new_vc.id] + [tr.id for tr in new_rules] + [cf.id for cf in new_cfs] + [fj.id for fj in new_fjs]

        tx_id = create_operation_record(
            session,
            action_name="create_stock_procurement_vc_action",
            ref_type="VirtualContract",
            ref_id=new_vc.id,
            ref_vc_id=new_vc.id,
            snapshot_before={},
            snapshot_after=snapshot_after,
            involved_ids=involved_ids,
        )

        session.commit()
        return ActionResult(success=True, data={"vc_id": new_vc.id}, message=f"库存采购单 VC-{new_vc.id} 创建成功")
    except Exception as e:
        session.rollback()
        if isinstance(e, BusinessError):
            raise
        return ActionResult(success=False, error=str(e))

def create_inventory_allocation_action(session: Session, payload: AllocateInventorySchema) -> ActionResult:
    """库存拨付 Action（支持回滚）"""
    try:
        from logic.transactions import serialize_model

        biz = session.query(Business).get(payload.business_id)
        if not biz: return ActionResult(success=False, error="未找到关联业务项目")

        if not biz.customer_id:
            return ActionResult(success=False, error="业务未关联客户，无法创建库存拨付单")

        # 商业逻辑
        # shipping_point_id：用户选择，范围=有该SKU库存的所有点位（来自EquipmentInventory）
        # receiving_point_id：用户选择，范围=客户所有点位（运营点位+仓库）
        allowed_receiving = _get_customer_points(session, biz.customer_id)
        if not allowed_receiving:
            return ActionResult(success=False, error=f"客户 {biz.customer_id} 没有可用点位，请先配置")

        # 收集所有将被修改的 EquipmentInventory SN 和旧值（snapshot_before）
        all_sn_list = []
        for e in payload.elements:
            for eq_id in e.sn_list:
                all_sn_list.append(str(eq_id))

        # snapshot_before：所有将被修改的 EquipmentInventory 旧值
        snapshot_before = {"records": []}
        if all_sn_list:
            old_eqs = session.query(EquipmentInventory).filter(EquipmentInventory.sn.in_(all_sn_list)).all()
            for eq in old_eqs:
                snapshot_before["records"].append({"class": "EquipmentInventory", "id": eq.id, "data": serialize_model(eq)})

        allowed_shipping_by_sku = {}
        for e in payload.elements:
            # 校验收货点
            if e.receiving_point_id not in allowed_receiving:
                return ActionResult(success=False, error=f"收货点 {e.receiving_point_id} 不在客户运营点位范围内")

            # 校验发货点：设备必须已在库
            for eq_id in e.sn_list:
                eq = session.query(EquipmentInventory).filter(EquipmentInventory.sn == str(eq_id)).first()
                if not eq or eq.operational_status != OperationalStatus.STOCK:
                    return ActionResult(success=False, error=f"设备 SN={eq_id} 不在库或不存在")

            # 发货点范围：EquipmentInventory 中该 SKU 在库的点位
            if e.sku_id not in allowed_shipping_by_sku:
                allowed_shipping_by_sku[e.sku_id] = set(_get_equipment_stock_points(session, e.sku_id))
            allowed_sp = allowed_shipping_by_sku[e.sku_id]
            if e.shipping_point_id not in allowed_sp:
                return ActionResult(success=False, error=f"发货点 {e.shipping_point_id} 没有 SKU {e.sku_id} 的设备库存")

        # 验证目标点位存在
        target_point_ids = set(e.receiving_point_id for e in payload.elements)
        for p_id in target_point_ids:
            p = session.query(Point).get(p_id)
            if not p: return ActionResult(success=False, error=f"未找到目标点位 ID={p_id}")

        clean_elems = []
        for e in payload.elements:
            corrected = VCElementSchema(
                shipping_point_id=e.shipping_point_id,
                receiving_point_id=e.receiving_point_id,
                sku_id=e.sku_id, qty=e.qty, price=e.price,
                deposit=e.deposit, subtotal=e.subtotal, sn_list=e.sn_list,
                batch_no=e.batch_no
            )
            clean_elems.append(_elem_to_dict(corrected))

        # 应用附加业务政策（价格覆盖 + 标记 addon_business_ids）
        clean_elems = _apply_addons_to_elements(session, payload.business_id, clean_elems)

        # ============ 记录创建前的最大 ID ============
        max_vc_id_before = session.query(func.max(VirtualContract.id)).scalar() or 0
        max_ev_id_before = session.query(func.max(SystemEvent.id)).scalar() or 0

        new_vc = VirtualContract(
            business_id=payload.business_id,
            type=VCType.INVENTORY_ALLOCATION,
            elements={
                "items": clean_elems,
                "total_amount": 0.0
            },
            deposit_info={"should_receive": 0.0, "total_deposit": 0.0},
            status=VCStatus.EXE, subject_status=SubjectStatus.FINISH,
            cash_status=CashStatus.FINISH,
            description=payload.description or f"库存拨付: {sum(e.qty for e in payload.elements)}台设备"
        )
        session.add(new_vc)
        session.flush()
        _record_vc_created_log(session, new_vc)

        # 更新设备状态（批量查询避免 N+1）
        all_sn_ids = [eq_id for e in payload.elements for eq_id in e.sn_list]
        eq_map = {str(eq.sn): eq for eq in session.query(EquipmentInventory).filter(EquipmentInventory.sn.in_(all_sn_ids)).all()}
        for e in payload.elements:
            target_pt = e.receiving_point_id
            for eq_id in e.sn_list:
                eq = eq_map.get(str(eq_id))
                if eq:
                    eq.operational_status = OperationalStatus.OPERATING
                    eq.point_id = target_pt
                    eq.virtual_contract_id = new_vc.id

        emit_event(session, SystemEventType.VC_CREATED, SystemAggregateType.VIRTUAL_CONTRACT, new_vc.id, {"type": new_vc.type, "equipment_count": sum(e.qty for e in payload.elements)})
        session.flush()

        # ============ 构建 snapshot_after ============
        from logic.transactions import serialize_model as _sm

        snapshot_records = [{"class": "VirtualContract", "id": new_vc.id, "data": _sm(new_vc)}]

        # EquipmentInventory 新值（重新查询）
        if all_sn_list:
            new_eqs = session.query(EquipmentInventory).filter(EquipmentInventory.sn.in_(all_sn_list)).all()
            for eq in new_eqs:
                snapshot_records.append({"class": "EquipmentInventory", "id": eq.id, "data": _sm(eq)})

        # SystemEvent
        new_evs = session.query(SystemEvent).filter(SystemEvent.id > max_ev_id_before).all()
        for ev in new_evs:
            snapshot_records.append({"class": "SystemEvent", "id": ev.id, "data": _sm(ev)})

        snapshot_after = {"records": snapshot_records}

        from logic.transactions import create_operation_record
        involved_ids = [new_vc.id]
        if all_sn_list:
            eq_ids = [eq.id for eq in session.query(EquipmentInventory).filter(EquipmentInventory.sn.in_(all_sn_list)).all()]
            involved_ids += eq_ids

        tx_id = create_operation_record(
            session,
            action_name="create_inventory_allocation_action",
            ref_type="VirtualContract",
            ref_id=new_vc.id,
            ref_vc_id=new_vc.id,
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            involved_ids=involved_ids,
        )

        session.commit()
        return ActionResult(success=True, data={"vc_id": new_vc.id}, message=f"库存拨付完成")
    except Exception as e:
        session.rollback()
        if isinstance(e, BusinessError):
            raise
        return ActionResult(success=False, error=str(e))
