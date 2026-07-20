from typing import List, Dict, Optional, Any
from models import get_session, VirtualContract, Business, ChannelCustomer, TimeRule, VirtualContractStatusLog, CashFlow
from logic.constants import VCType, VCStatus, TimeRuleRelatedType
from sqlalchemy import func


def _batch_get_latest_log_ts(session, vc_ids: List[int]) -> Dict[int, Any]:
    """批量获取多个 VC 的最新状态日志时间戳，返回 {vc_id: latest_datetime}"""
    if not vc_ids:
        return {}
    results = session.query(
        VirtualContractStatusLog.vc_id,
        func.max(VirtualContractStatusLog.timestamp)
    ).filter(
        VirtualContractStatusLog.vc_id.in_(vc_ids)
    ).group_by(VirtualContractStatusLog.vc_id).all()
    return {vid: ts for vid, ts in results}


def _get_single_latest_log_ts(session, vc_id: int) -> str:
    """获取单个 VC 最新状态日志时间戳，返回格式化字符串"""
    ts = session.query(func.max(VirtualContractStatusLog.timestamp)).filter(
        VirtualContractStatusLog.vc_id == vc_id
    ).scalar()
    return ts.strftime("%Y-%m-%d %H:%M") if ts else ""

def get_vc_list(
    business_id: Optional[int] = None,
    vc_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """获取虚拟合同列表"""
    session = get_session()
    try:
        query = session.query(VirtualContract)
        if business_id:
            query = query.filter(VirtualContract.business_id == business_id)
        if vc_type:
            query = query.filter(VirtualContract.type == vc_type)
        if status:
            query = query.filter(VirtualContract.status == status)

        contracts = query.order_by(VirtualContract.id.desc()).limit(limit).all()

        # 批量预加载 business、customer 和最新日志时间戳，消除 N+1
        biz_ids = list(set(vc.business_id for vc in contracts if vc.business_id))
        biz_map = {b.id: b for b in session.query(Business).filter(Business.id.in_(biz_ids)).all()} if biz_ids else {}
        cust_ids = list(set(b.customer_id for b in biz_map.values() if b.customer_id))
        cust_map = {c.id: c for c in session.query(ChannelCustomer).filter(ChannelCustomer.id.in_(cust_ids)).all()} if cust_ids else {}
        latest_ts_map = _batch_get_latest_log_ts(session, [vc.id for vc in contracts])

        result = []
        for vc in contracts:
            biz = biz_map.get(vc.business_id)
            customer = cust_map.get(biz.customer_id) if biz else None
            latest_ts = latest_ts_map.get(vc.id)
            result.append({
                "id": vc.id,
                "type": vc.type,
                "type_label": _get_vc_type_label(vc.type),
                "status": vc.status,
                "status_label": _get_vc_status_label(vc.status),
                "customer_name": customer.name if customer else "未知",
                "total_amount": vc.elements.get("total_amount", 0) if vc.elements else 0,
                "created_at": latest_ts.strftime("%Y-%m-%d") if latest_ts else ""
            })
        return result
    finally:
        session.close()

def get_vc_detail(vc_id: int) -> Optional[Dict[str, Any]]:
    """获取虚拟合同详情"""
    session = get_session()
    try:
        vc = session.query(VirtualContract).get(vc_id)
        if not vc: return None
        return {
            "id": vc.id,
            "type": vc.type,
            "status": vc.status,
            "subject_status": vc.subject_status,
            "cash_status": vc.cash_status,
            "elements": vc.elements,
            "deposit_info": vc.deposit_info,
            "description": vc.description,
            "business_id": vc.business_id,
            "supply_chain_id": vc.supply_chain_id,
            "related_vc_id": vc.related_vc_id
        }
    finally:
        session.close()

def get_time_rules_for_vc(vc_id: int) -> List[Dict[str, Any]]:
    """获取虚拟合同关联的时间规则"""
    session = get_session()
    try:
        from logic.constants import TimeRuleStatus
        rules = session.query(TimeRule).filter(
            TimeRule.related_id == vc_id,
            TimeRule.related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT,
            TimeRule.status != TimeRuleStatus.INACTIVE
        ).all()
        return [
            {
                "id": r.id,
                "party": r.party,
                "trigger_event": r.trigger_event,
                "target_event": r.target_event,
                "offset": r.offset,
                "unit": r.unit,
                "direction": r.direction,
                "status": r.status,
                "flag_time": r.flag_time.strftime("%Y-%m-%d %H:%M") if r.flag_time else None
            }
            for r in rules
        ]
    finally:
        session.close()

def _get_vc_type_label(vc_type: str) -> str:
    """获取虚拟合同类型的中文标签"""
    type_map = {
        VCType.EQUIPMENT_PROCUREMENT: "设备采购",
        VCType.STOCK_PROCUREMENT: "设备采购(库存)",
        VCType.INVENTORY_ALLOCATION: "库存拨付",
        VCType.MATERIAL_PROCUREMENT: "物料采购",
        VCType.MATERIAL_SUPPLY: "物料供应",
        VCType.RETURN: "退货",
    }
    return type_map.get(vc_type, vc_type)


def get_vc_status_logs(vc_id: int) -> List[Dict[str, Any]]:
    """获取虚拟合同的状态变更日志"""
    session = get_session()
    try:
        logs = session.query(VirtualContractStatusLog).filter(
            VirtualContractStatusLog.vc_id == vc_id
        ).order_by(VirtualContractStatusLog.timestamp.asc()).all()
        return [
            {
                "category": l.category,
                "status_name": l.status_name,
                "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M")
            }
            for l in logs
        ]
    finally:
        session.close()

def get_vc_cash_flows(vc_id: int) -> List[Dict[str, Any]]:
    """获取虚拟合同关联的资金流水"""
    session = get_session()
    try:
        cfs = session.query(CashFlow).filter(
            CashFlow.virtual_contract_id == vc_id
        ).order_by(CashFlow.transaction_date.desc()).all()
        return [
            {
                "date": cf.transaction_date.strftime("%Y-%m-%d") if cf.transaction_date else "未知",
                "type": cf.type,
                "amount": cf.amount,
                "description": cf.description
            }
            for cf in cfs
        ]
    finally:
        session.close()

def _get_vc_status_label(status: str) -> str:
    """获取虚拟合同状态的中文标签"""
    status_map = {
        VCStatus.EXE: "执行",
        VCStatus.FINISH: "完成",
        VCStatus.TERMINATED: "终止",
        VCStatus.CANCELLED: "取消",
    }
    return status_map.get(status, status)


def get_virtual_contracts_for_return(
    vc_types: List[str],
    statuses: List[str],
    subject_statuses: List[str]
) -> List[Dict[str, Any]]:
    """获取可退货的虚拟合同列表"""
    session = get_session()
    try:
        contracts = session.query(VirtualContract).filter(
            VirtualContract.type.in_(vc_types),
            VirtualContract.status.in_(statuses),
            VirtualContract.subject_status.in_(subject_statuses)
        ).all()

        latest_ts_map = _batch_get_latest_log_ts(session, [c.id for c in contracts])
        return [
            {
                "id": c.id,
                "type": c.type,
                "status": c.status,
                "subject_status": c.subject_status,
                "cash_status": c.cash_status,
                "description": c.description,
                "elements": c.elements,
                "business_id": c.business_id,
                "supply_chain_id": c.supply_chain_id,
                "created_at": latest_ts_map.get(c.id).strftime("%Y-%m-%d %H:%M") if latest_ts_map.get(c.id) else ""
            }
            for c in contracts
        ]
    finally:
        session.close()


def get_vc_detail_with_logs(vc_id: int) -> Optional[Dict[str, Any]]:
    """获取虚拟合同详情（包含日志）"""
    session = get_session()
    try:
        vc = session.query(VirtualContract).get(vc_id)
        if not vc:
            return None

        logs = session.query(VirtualContractStatusLog).filter(
            VirtualContractStatusLog.vc_id == vc_id
        ).order_by(VirtualContractStatusLog.timestamp.asc()).all()

        return {
            "vc": {
                "id": vc.id,
                "type": vc.type,
                "status": vc.status,
                "subject_status": vc.subject_status,
                "cash_status": vc.cash_status,
                "description": vc.description,
                "elements": vc.elements,
                "deposit_info": vc.deposit_info
            },
            "logs": [
                {
                    "id": l.id,
                    "vc_id": l.vc_id,
                    "category": l.category,
                    "status_name": l.status_name,
                    "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M") if l.timestamp else ""
                }
                for l in logs
            ]
        }
    finally:
        session.close()


def get_vc_list_for_overview(
    status_list: Optional[List[str]] = None,
    subject_status_list: Optional[List[str]] = None,
    cash_status_list: Optional[List[str]] = None,
    type_list: Optional[List[str]] = None,
    exclude_subject_status: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """获取虚拟合同列表（用于合同概览）"""
    session = get_session()
    try:
        query = session.query(VirtualContract)

        if status_list:
            query = query.filter(VirtualContract.status.in_(status_list))
        if subject_status_list:
            query = query.filter(VirtualContract.subject_status.in_(subject_status_list))
        if cash_status_list:
            query = query.filter(VirtualContract.cash_status.in_(cash_status_list))
        if type_list:
            query = query.filter(VirtualContract.type.in_(type_list))
        if exclude_subject_status:
            query = query.filter(VirtualContract.subject_status.notin_(exclude_subject_status))

        contracts = query.order_by(VirtualContract.id.desc()).all()
        latest_ts_map = _batch_get_latest_log_ts(session, [c.id for c in contracts])
        return [
            {
                "id": c.id,
                "type": c.type,
                "status": c.status,
                "subject_status": c.subject_status,
                "cash_status": c.cash_status,
                "description": c.description,
                "elements": c.elements,
                "business_id": c.business_id,
                "created_at": latest_ts_map.get(c.id).strftime("%Y-%m-%d %H:%M") if latest_ts_map.get(c.id) else ""
            }
            for c in contracts
        ]
    finally:
        session.close()


def get_returnable_vcs(
    vc_types: List[str],
    statuses: List[str],
    subject_statuses: List[str]
) -> List[Dict[str, Any]]:
    """获取可退货的虚拟合同列表"""
    return get_virtual_contracts_for_return(vc_types, statuses, subject_statuses)


def get_vc_full_detail(vc_id: int) -> Optional[Dict[str, Any]]:
    """获取虚拟合同完整详情（包含业务、供应链信息）"""
    from models import Business, SupplyChain
    session = get_session()
    try:
        vc = session.query(VirtualContract).get(vc_id)
        if not vc:
            return None

        biz_info = None
        if vc.business_id:
            biz = session.query(Business).get(vc.business_id)
            if biz:
                customer = session.query(ChannelCustomer).get(biz.customer_id) if biz.customer_id else None
                biz_info = {
                    "id": biz.id,
                    "customer_name": customer.name if customer else "未知",
                    "status": biz.status
                }

        sc_info = None
        if vc.supply_chain_id:
            sc = session.query(SupplyChain).get(vc.supply_chain_id)
            if sc:
                from models import Supplier
                supplier = session.query(Supplier).get(sc.supplier_id) if sc.supplier_id else None
                sc_info = {
                    "id": sc.id,
                    "supplier_name": supplier.name if supplier else "未知",
                    "type": sc.type
                }

        return {
            "id": vc.id,
            "type": vc.type,
            "status": vc.status,
            "subject_status": vc.subject_status,
            "cash_status": vc.cash_status,
            "description": vc.description,
            "elements": vc.elements,
            "deposit_info": vc.deposit_info,
            "business": biz_info,
            "supply_chain": sc_info,
            "related_vc_id": vc.related_vc_id,
            "created_at": _get_single_latest_log_ts(session, vc.id)
        }
    finally:
        session.close()


def get_vc_by_id(vc_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取虚拟合同详情
    """
    session = get_session()
    try:
        vc = session.query(VirtualContract).get(vc_id)
        if not vc:
            return None
        return {
            "id": vc.id,
            "type": vc.type,
            "status": vc.status,
            "subject_status": vc.subject_status,
            "cash_status": vc.cash_status,
            "description": vc.description,
            "elements": vc.elements,
            "business_id": vc.business_id,
            "supply_chain_id": vc.supply_chain_id,
            "created_at": _get_single_latest_log_ts(session, vc_id)
        }
    finally:
        session.close()


def get_vc_count_by_business(business_id: int) -> int:
    """
    获取指定业务下的虚拟合同数量
    """
    session = get_session()
    try:
        return session.query(VirtualContract).filter(VirtualContract.business_id == business_id).count()
    finally:
        session.close()


# =============================================================================
# VC 各场景有效点位查询（供 UI 层下拉框使用）
# =============================================================================

from models import Business, SupplyChain, VirtualContract, Point, MaterialInventory, EquipmentInventory
from logic.constants import ReturnDirection


def get_valid_receiving_points_for_procurement(session, business_id: int) -> list[dict]:
    """
    设备采购：收货点 = 客户所有点位（不限 type）
    """
    biz = session.query(Business).get(business_id)
    if not biz or not biz.customer_id:
        return []
    pts = session.query(Point).filter(Point.customer_id == biz.customer_id).all()
    return [{"id": p.id, "name": p.name, "type": p.type or ""} for p in pts]


def get_valid_receiving_points_for_mat_procurement(session, sc_id: int) -> list[dict]:
    """
    物料采购/库存采购：收货点 = 我们仓库 + 供应商仓库 + 客户仓库
    """
    sc = session.query(SupplyChain).get(sc_id)
    our = session.query(Point).filter(Point.type == "自有仓").all()
    supplier_pts = []
    customer_pts = session.query(Point).filter(Point.type == "客户仓").all()
    if sc:
        supplier_pts = session.query(Point).filter(
            Point.supplier_id == sc.supplier_id,
            Point.type == "供应商仓"
        ).all()
    pts = our + supplier_pts + customer_pts
    return [{"id": p.id, "name": p.name, "type": p.type or ""} for p in pts]


def get_valid_shipping_points_for_mat_procurement(session, sc_id: int) -> list[dict]:
    """
    物料采购/库存采购：发货点 = 供应商仓库（由供应链的 supplier_id 确定）
    """
    sc = session.query(SupplyChain).get(sc_id)
    if not sc:
        return []
    pts = session.query(Point).filter(
        Point.supplier_id == sc.supplier_id,
        Point.type == "供应商仓"
    ).all()
    return [{"id": p.id, "name": p.name, "type": p.type or ""} for p in pts]


def get_valid_receiving_points_for_material_supply(session, business_id: int) -> list[dict]:
    """
    物料供应：收货点 = 客户所有点位（不限 type）
    """
    return get_valid_receiving_points_for_procurement(session, business_id)


def get_valid_shipping_points_for_material_supply(session, sku_id: int) -> list[dict]:
    """
    物料供应：发货点 = 有该 SKU 物料库存的仓库
    从 MaterialInventory 批次行查询有库存的点位及其数量
    """
    mat_invs = session.query(MaterialInventory).filter(
        MaterialInventory.sku_id == sku_id,
        MaterialInventory.qty > 0
    ).all()
    if not mat_invs:
        return []
    # 聚合所有点位ID和库存量（同一SKU可能存在于多个仓库）
    point_qty = {}  # point_id -> total qty
    for mat_inv in mat_invs:
        if mat_inv.point_id:
            point_qty[mat_inv.point_id] = point_qty.get(mat_inv.point_id, 0) + mat_inv.qty
    if not point_qty:
        return []
    pts = session.query(Point).filter(Point.id.in_(point_qty.keys())).all()
    return [{"id": p.id, "name": p.name, "type": p.type or "", "qty": point_qty.get(p.id, 0)} for p in pts]


def get_valid_receiving_points_for_allocation(session, business_id: int) -> list[dict]:
    """
    库存拨付：收货点 = 客户所有点位（不限 type）
    """
    return get_valid_receiving_points_for_procurement(session, business_id)


def get_valid_shipping_points_for_allocation(session, sku_id: int) -> list[dict]:
    """
    库存拨付：发货点 = 有该 SKU 设备库存的点位（来自 EquipmentInventory）
    """
    eqs = session.query(EquipmentInventory).filter(
        EquipmentInventory.sku_id == sku_id,
        EquipmentInventory.operational_status == "库存"
    ).all()
    point_ids = list({eq.point_id for eq in eqs})
    if not point_ids:
        return []
    pts = session.query(Point).filter(Point.id.in_(point_ids)).all()
    return [{"id": p.id, "name": p.name, "type": p.type or ""} for p in pts]


def get_valid_shipping_points_for_return_equipment(session, target_vc_id: int) -> list[dict]:
    """
    退货-设备采购：发货点 = 目标VC关联客户下，有该SKU设备的点位（不限 type）
    """
    target_vc = session.query(VirtualContract).get(target_vc_id)
    if not target_vc or not target_vc.business_id:
        return []
    biz = session.query(Business).get(target_vc.business_id)
    if not biz or not biz.customer_id:
        return []
    cust_pts = session.query(Point).filter(Point.customer_id == biz.customer_id).all()
    cust_point_ids = [p.id for p in cust_pts]
    if not cust_point_ids:
        return []
    elements = target_vc.elements or {}
    sku_ids = [e["sku_id"] for e in elements.get("items", [])]
    if not sku_ids:
        return []
    eqs = session.query(EquipmentInventory).filter(
        EquipmentInventory.sku_id.in_(sku_ids),
        EquipmentInventory.point_id.in_(cust_point_ids)
    ).all()
    valid_pt_ids = list({eq.point_id for eq in eqs})
    pts = session.query(Point).filter(Point.id.in_(valid_pt_ids)).all()
    return [{"id": p.id, "name": p.name, "type": p.type or ""} for p in pts]


def get_valid_shipping_points_for_return_mat(session, sku_id: int) -> list[dict]:
    """
    退货-物料采购/库存采购：发货点 = 我们有该 SKU 物料库存的点位
    """
    return get_valid_shipping_points_for_material_supply(session, sku_id)


def get_valid_receiving_points_for_return(session, target_vc_id: int, return_direction: str) -> list[dict]:
    """
    退货收货点：
    - CUSTOMER_TO_US → 我们的仓 + 客户仓；默认我们仓ID最小
    - US_TO_SUPPLIER → 我们的仓 + 供应商仓；默认供应商仓
    """
    target_vc = session.query(VirtualContract).get(target_vc_id)

    if return_direction == ReturnDirection.CUSTOMER_TO_US:
        # 物料供应退货：可退给我们仓 或 客户仓
        our_pts = session.query(Point).filter(Point.type == "自有仓").all()
        # 找客户仓（从 target_vc.business.customer_id）
        cust_pts = []
        if target_vc and target_vc.business_id:
            biz = session.query(Business).get(target_vc.business_id)
            if biz and biz.customer_id:
                cust_pts = session.query(Point).filter(
                    Point.customer_id == biz.customer_id
                ).all()
        all_pts = our_pts + cust_pts
        # 默认：我们仓ID最小
        all_pts.sort(key=lambda p: (p.type != "自有仓", p.id))
    else:
        # 物料采购退货：可退给我们仓 或 供应商仓
        our_pts = session.query(Point).filter(Point.type == "自有仓").all()
        supplier_pts = []
        if target_vc and target_vc.supply_chain_id:
            sc = session.query(SupplyChain).get(target_vc.supply_chain_id)
            if sc:
                supplier_pts = session.query(Point).filter(
                    Point.supplier_id == sc.supplier_id,
                    Point.type == "供应商仓"
                ).all()
        all_pts = our_pts + supplier_pts
        # 默认：供应商仓优先
        all_pts.sort(key=lambda p: (p.type != "供应商仓", p.id))

    return [{"id": p.id, "name": p.name, "type": p.type or ""} for p in all_pts]


# =============================================================================
# 物料供应提案生成
# =============================================================================

def get_latest_supply_batches_by_sku(session, business_id: int) -> dict[tuple, str]:
    """
    查询某业务下每个 SKU 最近一次物料供应的批次号。
    返回 {(sku_id, receiving_point_id): last_batch_no}，无历史则 value 为 None。
    只查询有 batch_no 且非空的记录。
    """
    vcs = session.query(VirtualContract).filter(
        VirtualContract.business_id == business_id,
        VirtualContract.type == VCType.MATERIAL_SUPPLY
    ).order_by(VirtualContract.status_timestamp.desc()).all()

    result = {}  # (sku_id, receiving_point_id) -> last_batch_no
    for vc in vcs:
        elems = (vc.elements or {}).get("items", [])
        for e in elems:
            sid = e.get("sku_id")
            rp = e.get("receiving_point_id")
            bn = e.get("batch_no")
            if sid and rp and bn:
                key = (sid, rp)
                if key not in result:
                    result[key] = bn  # 第一条就是最新的（倒序）
    return result


def get_available_batches_by_sku(session, sku_id: int, min_batch_no: str = None) -> list[dict]:
    """
    查询某 SKU 所有可用批次行（qty > 0）。
    可选过滤：只返回 batch_no >= min_batch_no 的批次（满足新鲜度要求）。
    返回 list[dict]，每项含 batch_no, point_id, point_name, point_type, qty。
    """
    query = session.query(MaterialInventory).filter(
        MaterialInventory.sku_id == sku_id,
        MaterialInventory.qty > 0
    )
    rows = query.all()

    point_ids = list(set(r.point_id for r in rows if r.point_id))
    point_map = {}
    if point_ids:
        pts = session.query(Point).filter(Point.id.in_(point_ids)).all()
        point_map = {p.id: p for p in pts}

    result = []
    for r in rows:
        bn = r.batch_no
        if min_batch_no and bn and bn < min_batch_no:
            continue
        pt = point_map.get(r.point_id)
        pt_type = pt.type or "" if pt else ""
        result.append({
            "batch_no": bn,
            "point_id": r.point_id,
            "point_name": pt.name if pt else f"点位{r.point_id}",
            "point_type": pt_type,
            "qty": r.qty,
        })
    return result
