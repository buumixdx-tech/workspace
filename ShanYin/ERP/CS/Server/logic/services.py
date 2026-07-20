"""
业务服务层
负责处理跨模块的复杂业务计算逻辑，确保 UI 层仅负责数据展示与交互。
"""
from models import (
    get_session, VirtualContract, EquipmentInventory, MaterialInventory,
    SKU, Point, SupplyChain, Business, PartnerRelation, ExternalPartner
)
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from typing import List, Optional
from logic.constants import (
    VCType, VCStatus, SubjectStatus, ReturnDirection, OperationalStatus, SKUType,
    AccountOwnerType, SystemConstants, CashFlowType, CounterpartType, AccountLevel1,
    PartnerRelationType
)
import pandas as pd

def normalize_item_data(item: dict) -> dict:
    """将混乱的字典 Key 统一为系统标准格式（统一使用 snake_case 字段名）"""
    return {
        "sku_id": item.get("sku_id") or item.get("skuId") or item.get("id"),
        "sku_name": item.get("sku_name") or item.get("skuName") or item.get("name") or SystemConstants.UNKNOWN,
        "qty": float(item.get("qty") or item.get("quantity") or 0),
        "price": float(item.get("price") or item.get("unit_price") or item.get("unitPrice") or 0.0),
        # 收货点位（采购场景）
        "receiving_point_id": item.get("receiving_point_id") or item.get("point_id") or item.get("pointId"),
        "receiving_point_name": item.get("receiving_point_name") or item.get("point_name") or item.get("pointName") or item.get("warehouse") or SystemConstants.UNKNOWN,
        # 设备序列号
        "sn": item.get("sn") or "-",
        # 押金
        "deposit": float(item.get("deposit") or 0.0),
        # 发货点位（综合来源：source_warehouse/supplier仓库 或 shipping_point_name/退货原点位）
        "shipping_point_name": item.get("source_warehouse") or item.get("sourceWarehouse") or item.get("shipping_point_name") or item.get("shippingPointName") or SystemConstants.DEFAULT_POINT,
        # 目标仓库/退货目的地（用于退货/调拨场景）
        "target_warehouse": item.get("target_warehouse") or item.get("targetWarehouse") or item.get("receiving_warehouse") or item.get("receivingWarehouse") or item.get("退货目的地"),
        # 目标点位（调拨场景）
        "target_point_id": item.get("target_point_id") or item.get("targetPointId"),
        "target_point_name": item.get("target_point_name") or item.get("targetPointName"),
        # 发货点位ID（退货场景）
        "shipping_point_id": item.get("shipping_point_id") or item.get("shippingPointId"),
        # 批次号（物料供应）
        "batch_no": item.get("batch_no") or item.get("batchNo"),
    }

def format_item_list_preview(items: list) -> str:
    """将复杂的 Item 列表转换为用户易读的预览文本"""
    if not items:
        return "无货品明细"
    
    decoded = []
    for i in items:
        norm = normalize_item_data(i)
        desc = f"{norm['sku_name']} x{int(norm['qty']) if norm['qty'].is_integer() else norm['qty']}"
        if norm['sn'] != "-":
            desc += f" (SN:{norm['sn']})"
        decoded.append(desc)
    
    return " | ".join(decoded)

def _collect_returned_batch_nos(session, related_vc_ids: list[int]) -> set[str]:
    """
    查询所有退货VC涉及的批次号集合。
    从退货VC的elements中提取batch_no；如果elements中没有batch_no，
    则从原始VC的elements中回溯。
    """
    returned_batches = set()
    return_vcs = session.query(VirtualContract).filter(
        VirtualContract.related_vc_id.in_(related_vc_ids),
        VirtualContract.type == VCType.RETURN,
        VirtualContract.status != VCStatus.CANCELLED
    ).all()
    for r_vc in return_vcs:
        r_elems = (r_vc.elements or {}).get("items", [])
        for ri in r_elems:
            bn = ri.get("batch_no")
            if bn:
                returned_batches.add(bn)
    return returned_batches


def _build_source_vc_breakdown(session, related_vc_ids: list[int], sku_id: int, batch_no: str) -> list[dict]:
    """构造指定批次在各源VC中的供货明细，用于溯源。"""
    breakdown = []
    for vid in related_vc_ids:
        vc = session.query(VirtualContract).get(vid)
        if not vc:
            continue
        elems = (vc.elements or {}).get("items", [])
        for e in elems:
            if int(e.get("sku_id")) == int(sku_id) and e.get("batch_no") == batch_no:
                breakdown.append({
                    "vc_id": vid,
                    "qty": float(e.get("qty", 0)),
                    "price": float(e.get("price", 0)),
                })
    return breakdown


def get_returnable_items(session, target_vc_id, return_direction):
    """
    计算一个虚拟合同的可退货明细。
    物料退货按(sku_id, batch_no)聚合跨VC批次，已退批次标记为不可退。
    设备退货按SN校验，不变。
    """
    target_vc = session.query(VirtualContract).get(target_vc_id)
    if not target_vc:
        return []

    # ===================== 设备采购退货（不变） =====================
    if target_vc.type in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT]:
        locked_sns = set()
        existing_returns = session.query(VirtualContract).filter(
            VirtualContract.related_vc_id == target_vc.id,
            VirtualContract.type == VCType.RETURN,
            VirtualContract.status != VCStatus.CANCELLED
        ).all()
        for r_vc in existing_returns:
            r_elems = (r_vc.elements or {}).get("items", [])
            for ri in r_elems:
                rsn = ri.get("sn")
                if rsn and rsn != "-":
                    locked_sns.add(rsn)

        filter_status = OperationalStatus.OPERATING if ReturnDirection.CUSTOMER_TO_US in return_direction else OperationalStatus.STOCK
        equip_list = session.query(EquipmentInventory).options(
            joinedload(EquipmentInventory.sku),
            joinedload(EquipmentInventory.point)
        ).filter(
            EquipmentInventory.virtual_contract_id == target_vc.id,
            EquipmentInventory.operational_status == filter_status
        ).all()

        return_items = []
        for e in equip_list:
            if e.sn in locked_sns:
                continue
            return_items.append({
                "sku_id": e.sku_id,
                "sn": e.sn,
                "sku_name": e.sku.name if e.sku else "未知设备",
                "price": 0.0 if ReturnDirection.CUSTOMER_TO_US in return_direction else (e.sku.params.get("unit_price", 0) if e.sku and e.sku.params else 0),
                "qty": 1,
                "point_id": e.point_id,
                "point_name": e.point.name if e.point else "未定义",
                "shipping_point_name": e.point.name if e.point else None,
                "deposit": float(e.deposit_amount or 0.0),
            })
        return return_items

    # ===================== 物料退货（批次维度聚合） =====================
    if target_vc.type not in [VCType.MATERIAL_PROCUREMENT, VCType.MATERIAL_SUPPLY]:
        return []

    # Step 1: 确定同批次相关的VC列表
    related_vc_ids = []
    if target_vc.type == VCType.MATERIAL_PROCUREMENT:
        sc_id = target_vc.supply_chain_id
        if sc_id:
            related = session.query(VirtualContract).filter(
                VirtualContract.supply_chain_id == sc_id,
                VirtualContract.type == VCType.MATERIAL_PROCUREMENT
            ).all()
            related_vc_ids = [v.id for v in related]
    elif target_vc.type == VCType.MATERIAL_SUPPLY:
        biz_id = target_vc.business_id
        if biz_id:
            related = session.query(VirtualContract).filter(
                VirtualContract.business_id == biz_id,
                VirtualContract.type == VCType.MATERIAL_SUPPLY
            ).all()
            related_vc_ids = [v.id for v in related]

    if not related_vc_ids:
        return []

    # Step 2: 找出已退批次（跨VC检查同一批次是否已退货）
    returned_batch_nos = _collect_returned_batch_nos(session, related_vc_ids)

    # Step 3: 从相关VC的elements聚合批次数据
    # 对每个related VC，将其elements["items"]按(sku_id, batch_no)聚合
    batch_totals = {}  # (sku_id, batch_no) -> {qty, price_sum, price_count, source_vc_ids, point_id}
    for vid in related_vc_ids:
        vc = session.query(VirtualContract).get(vid)
        if not vc:
            continue
        elems = (vc.elements or {}).get("items", [])
        for e in elems:
            sku_id = e.get("sku_id")
            batch_no = e.get("batch_no") or "-"
            key = (sku_id, batch_no)
            if key not in batch_totals:
                batch_totals[key] = {
                    "qty": 0.0,
                    "price_sum": 0.0,
                    "price_count": 0,
                    "source_vc_ids": set(),
                    "point_id": e.get("receiving_point_id"),
                }
            qty = float(e.get("qty") or 0)
            price = float(e.get("price") or 0)
            batch_totals[key]["qty"] += qty
            if price > 0:
                batch_totals[key]["price_sum"] += price
                batch_totals[key]["price_count"] += 1
            batch_totals[key]["source_vc_ids"].add(vid)

    # Step 4: 查MaterialInventory获取实际库存量（用于MATERIAL_PROCUREMENT退货）
    if target_vc.type == VCType.MATERIAL_PROCUREMENT:
        # MaterialInventory 使用 latest_purchase_vc_id 而非 virtual_contract_id
        mi_rows = session.query(MaterialInventory).filter(
            MaterialInventory.latest_purchase_vc_id.in_(related_vc_ids)
        ).all()
        for row in mi_rows:
            key = (row.sku_id, row.batch_no)
            if key in batch_totals:
                # 用实际库存量更新
                batch_totals[key]["qty"] = row.qty
                if row.point_id:
                    batch_totals[key]["point_id"] = row.point_id

    # Step 5: 构造返回列表
    return_items = []
    sku_ids = list({k[0] for k in batch_totals})
    sku_name_map = {}
    if sku_ids:
        skus = session.query(SKU).filter(SKU.id.in_(sku_ids)).all()
        sku_name_map = {s.id: s.name for s in skus}

    for (sku_id, batch_no), info in batch_totals.items():
        is_returned = batch_no in returned_batch_nos
        source_vc_ids = list(info["source_vc_ids"])

        avg_price = 0.0
        if info["price_count"] > 0:
            avg_price = info["price_sum"] / info["price_count"]

        item = {
            "sku_id": sku_id,
            "sku_name": sku_name_map.get(sku_id, f"SKU{sku_id}"),
            "batch_no": batch_no,
            "original_qty": info['qty'],
            "price": avg_price,
            "qty": 0.0 if is_returned else info['qty'],
            "returnable": not is_returned,
            "returned_note": "已退货" if is_returned else None,
            "source_vc_ids": source_vc_ids,
            "point_id": info['point_id'],
        }
        return_items.append(item)

    return return_items




def get_sku_agreement_price(session, sc_id, business_id, sku_name):
    """
    获取 SKU 在特定业务 and 供应链环境下的协议单价与押金
    返回: (unit_price, deposit, sku_type)

    注意：pricing_config 和 details.pricing 的 key 已迁移为 sku_id (字符串)
    此函数通过 sku_name 查找对应的 sku_id 后再进行价格查找
    """
    # 先通过 sku_name 找到 sku_id（pricing key 已改为 sku_id）
    sku = session.query(SKU).filter(SKU.name == sku_name).first()
    sku_id = str(sku.id) if sku else None

    sc = session.query(SupplyChain).get(sc_id) if sc_id else None
    biz = session.query(Business).get(business_id) if isinstance(business_id, int) else business_id

    # 获取供应链提供的单价 (如果有)
    unit_price = 0.0
    if sc and sku_id:
        sc_pricing = sc.get_pricing_dict()
        raw_price = sc_pricing.get(sku_id, 0.0)
        if isinstance(raw_price, dict):
            unit_price = float(raw_price.get("price") or 0.0)
        elif isinstance(raw_price, (int, float)):
            unit_price = float(raw_price)

    # 获取客户业务约定的押金与单价 (优先级覆盖)
    if biz and isinstance(biz, dict):
        biz_agreement = biz.get("details", {}).get("pricing", {})
    else:
        biz_agreement = (biz.details or {}).get("pricing", {}) if biz else {}

    sku_config = {}
    if sku_id:
        sku_config = biz_agreement.get(sku_id, {})

    deposit = 0.0
    sku_type = SKUType.EQUIPMENT

    if isinstance(sku_config, dict):
        deposit = float(sku_config.get("deposit", 0.0))
        sku_type = sku_config.get("type", SKUType.EQUIPMENT)
        # 如果客户合同里也定了单价，通常以给客户的单价为准 (在供应场景下)
        if "price" in sku_config:
            unit_price = float(sku_config["price"])
    elif isinstance(sku_config, (int, float)):
        # 兼容旧版简单格式 {"SKU": 100.0}
        unit_price = float(sku_config)

    return float(unit_price), float(deposit), sku_type

def validate_inventory_availability(session, request_items):
    """
    统一校验库存充足性
    request_items: list of (sku_name, warehouse_name, requested_qty)
    返回: (is_valid, error_messages)
    """
    totals = {}
    for sku_n, wh_n, req_qty in request_items:
        if not sku_n or not wh_n or req_qty <= 0: continue
        key = (sku_n, wh_n)
        totals[key] = totals.get(key, 0) + req_qty

    over_stock = []
    for (sku_n, wh_n), total_req in totals.items():
        # 查询SKU
        sku = session.query(SKU).filter(SKU.name == sku_n).first()
        if not sku:
            over_stock.append(f"【{wh_n}】的 {sku_n}: SKU不存在")
            continue

        # warehouse name 格式为 "SKU - 仓库名 (类型) - 数量件"，提取中间段"仓库名"
        wh_n_clean = wh_n.split(' - ')[1].split(' (')[0] if ' - ' in wh_n else wh_n
        pt = session.query(Point).filter(Point.name == wh_n_clean).first()
        if not pt:
            over_stock.append(f"【{wh_n}】的 {sku_n}: 仓库不存在")
            continue

        # 查询该SKU在该仓库的批次库存总和
        available = session.query(func.sum(MaterialInventory.qty)).filter(
            MaterialInventory.sku_id == sku.id,
            MaterialInventory.point_id == pt.id
        ).scalar() or 0.0

        if total_req > available:
            over_stock.append(f"【{wh_n}】的 {sku_n}: 申请 {total_req}, 当前存量 {available}")

    return len(over_stock) == 0, over_stock


def validate_batch_inventory_availability(session, batch_check_items):
    """
    精确批次维度校验库存充足性。
    相同 (sku_id, batch_no, point_id) 的多个 element 合计不能超过该批次库存。

    batch_check_items: list of (sku_id, batch_no, point_id, requested_qty)
    返回: (is_valid, error_messages)
    """
    # 按 (sku_id, batch_no, point_id) 聚合
    from collections import defaultdict
    totals = defaultdict(float)
    item_keys = {}  # (sku_id, batch_no, point_id) -> (sku_name, batch_no, point_name)

    for sku_id, batch_no, point_id, req_qty in batch_check_items:
        if not sku_id or not point_id or req_qty <= 0:
            continue
        key = (sku_id, batch_no or '', point_id)
        totals[key] += req_qty
        if key not in item_keys:
            sku = session.query(SKU).get(sku_id)
            pt = session.query(Point).get(point_id)
            item_keys[key] = (
                sku.name if sku else f"SKU{sku_id}",
                batch_no or '(无批次)',
                pt.name if pt else f"点位{point_id}"
            )

    over_stock = []
    for (sku_id, batch_no, point_id), total_req in totals.items():
        sku_n, bn, pt_n = item_keys[(sku_id, batch_no, point_id)]

        # 查询该批次在该仓库的可用库存
        q = session.query(MaterialInventory).filter(
            MaterialInventory.sku_id == sku_id,
            MaterialInventory.point_id == point_id
        )
        if batch_no:
            q = q.filter(MaterialInventory.batch_no == batch_no)

        available = q.with_entities(func.sum(MaterialInventory.qty)).scalar() or 0.0

        if total_req > available + 0.001:  # epsilon=0.001 避免浮点误差
            over_stock.append(
                f"{sku_n}@{bn}@{pt_n}: 申请合计 {total_req}，该批次库存 {available}"
            )

    return len(over_stock) == 0, over_stock

def get_counterpart_info(session, vc):
    """
    公共方法：识别虚拟合同对应的交易对手类型与 ID
    """
    from models import Business, SupplyChain
    cp_type, cp_id = None, None
    
    # 获取关键属性 (适配 dict 或 SQLAlchemy 对象)
    vc_type = vc.get('type') if isinstance(vc, dict) else vc.type
    vc_related_id = vc.get('related_vc_id') if isinstance(vc, dict) else vc.related_vc_id

    # 穿透识别原始业务属性
    active_vc = vc
    if vc_type == VCType.RETURN and vc_related_id:
        active_vc = session.query(VirtualContract).get(vc_related_id) or vc

    # 获取 active_vc 的属性 (处理 active_vc 可能是 dict 的情况)
    active_vc_type = active_vc.get('type') if isinstance(active_vc, dict) else active_vc.type
    active_vc_sc_id = active_vc.get('supply_chain_id') if isinstance(active_vc, dict) else active_vc.supply_chain_id
    active_vc_biz_id = active_vc.get('business_id') if isinstance(active_vc, dict) else active_vc.business_id

    if active_vc_type in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT, VCType.MATERIAL_PROCUREMENT]:
        cp_type = CounterpartType.SUPPLIER
        if active_vc_sc_id:
            sc = session.query(SupplyChain).get(active_vc_sc_id)
            if sc: cp_id = sc.supplier_id
    elif active_vc_type == VCType.MATERIAL_SUPPLY:
        # 物料供应：判断 business 是否恰好有一个采购执行合作方
        cp_type = CounterpartType.CUSTOMER
        cp_id = None
        if active_vc_biz_id:
            from models import PartnerRelation
            rels = session.query(PartnerRelation).filter(
                PartnerRelation.owner_type == "business",
                PartnerRelation.owner_id == active_vc_biz_id,
                PartnerRelation.relation_type == PartnerRelationType.PROCUREMENT,
                PartnerRelation.ended_at == None
            ).all()
            if len(rels) == 1:
                cp_type = CounterpartType.PARTNER
                cp_id = rels[0].partner_id
            else:
                biz = session.query(Business).get(active_vc_biz_id)
                if biz: cp_id = biz.customer_id
    else:
        cp_type = CounterpartType.CUSTOMER
        if active_vc_biz_id:
            biz = session.query(Business).get(active_vc_biz_id)
            if biz: cp_id = biz.customer_id

    return cp_type, cp_id


def _get_biz_procurement_partner(session, biz_id):
    """
    查询 Business 是否关联了恰好一个"采购执行"类型的有效合作方。
    返回 (partner_id, partner_name) 或 (None, None)。
    """
    items = session.query(PartnerRelation).filter(
        PartnerRelation.owner_type == "business",
        PartnerRelation.owner_id == biz_id,
        PartnerRelation.relation_type == PartnerRelationType.PROCUREMENT,
        PartnerRelation.ended_at == None
    ).all()
    if len(items) == 1:
        partner = session.query(ExternalPartner).get(items[0].partner_id)
        return (items[0].partner_id, partner.name if partner else None)
    return None, None


def _get_biz_procurement_partner_name(session, biz_id):
    """查询 Business 关联的合作方名称，仅返回一个（多于一则返回 None）。"""
    items = session.query(PartnerRelation).filter(
        PartnerRelation.owner_type == "business",
        PartnerRelation.owner_id == biz_id,
        PartnerRelation.relation_type == PartnerRelationType.PROCUREMENT,
        PartnerRelation.ended_at == None
    ).all()
    if len(items) == 1:
        partner = session.query(ExternalPartner).get(items[0].partner_id)
        return partner.name if partner else None
    return None


def get_suggested_cashflow_parties(session, vc, cf_type: str = None) -> tuple:
    """
    根据合同类型、款项性质和流向建议付款方和收款方
    返回: (payer_type, payer_id, payee_type, payee_id)
    """
    from logic.constants import CashFlowType, AccountOwnerType
    # 获取关键属性 (适配 dict 或 SQLAlchemy 对象)
    elements = (vc.get('elements') or {}) if isinstance(vc, dict) else (vc.elements or {})
    vc_type = vc.get('type') if isinstance(vc, dict) else vc.type
    vc_bid = vc.get('business_id') if isinstance(vc, dict) else vc.business_id
    vc_scid = vc.get('supply_chain_id') if isinstance(vc, dict) else vc.supply_chain_id

    # 默认空值
    p_err, p_err_id = None, None
    p_ee, p_ee_id = None, None

    # 情况A：设备采购中的押金收入（客户 -> 我们）
    if vc_type == VCType.EQUIPMENT_PROCUREMENT and cf_type == CashFlowType.DEPOSIT:
        p_err = AccountOwnerType.CUSTOMER
        biz = session.query(Business).get(vc_bid) if vc_bid else None
        if biz: p_err_id = biz.customer_id
        p_ee, p_ee_id = AccountOwnerType.OURSELVES, 0
        return p_err, p_err_id, p_ee, p_ee_id

    # 情况B：设备采购中的押金退还（我们 -> 客户）
    if vc_type == VCType.EQUIPMENT_PROCUREMENT and cf_type == CashFlowType.RETURN_DEPOSIT:
        p_err, p_err_id = AccountOwnerType.OURSELVES, 0
        p_ee = AccountOwnerType.CUSTOMER
        biz = session.query(Business).get(vc_bid) if vc_bid else None
        if biz: p_ee_id = biz.customer_id
        return p_err, p_err_id, p_ee, p_ee_id

    if vc_type == VCType.MATERIAL_SUPPLY:
        # 物料供应：客户(Payer) -> 自己公司(Payee)
        p_ee, p_ee_id = AccountOwnerType.OURSELVES, 0
        biz = session.query(Business).get(vc_bid) if vc_bid else None
        if biz:
            partner_pid, _ = _get_biz_procurement_partner(session, biz.id)
            if partner_pid is not None:
                # 恰好有一个采购执行合作方 → 使用合作方账户
                p_err, p_err_id = AccountOwnerType.PARTNER, partner_pid
            else:
                # 没有或超过一个 → 退回到渠道客户
                p_err, p_err_id = AccountOwnerType.CUSTOMER, biz.customer_id
        else:
            p_err, p_err_id = AccountOwnerType.CUSTOMER, None
        
    elif vc_type in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT, VCType.MATERIAL_PROCUREMENT]:
        # 设备/物料采购（常规货款）：自己公司(Payer) -> 供应商(Payee)
        p_err, p_err_id = AccountOwnerType.OURSELVES, 0
        sc = session.query(SupplyChain).get(vc_scid) if vc_scid else None
        if sc: 
            p_ee, p_ee_id = AccountOwnerType.SUPPLIER, sc.supplier_id
            
    elif vc_type == VCType.RETURN:
        direction = (vc.get('return_direction') if isinstance(vc, dict) else vc.return_direction) or ''
        if ReturnDirection.US_TO_SUPPLIER in direction:
            # 向供应商退货：供应商(Payer) -> 自己公司(Payee) [退款流程]
            p_err, p_err_id = AccountOwnerType.SUPPLIER, None
            sc = session.query(SupplyChain).get(vc_scid) if vc_scid else None
            if sc: p_err_id = sc.supplier_id
            p_ee, p_ee_id = AccountOwnerType.OURSELVES, 0
        elif ReturnDirection.CUSTOMER_TO_US in direction:
            # 客户退回：自己公司(Payer) -> 客户(Payee) [退款流程]
            p_err, p_err_id = AccountOwnerType.OURSELVES, 0
            biz = session.query(Business).get(vc_bid) if vc_bid else None
            if biz:
                partner_pid, _ = _get_biz_procurement_partner(session, biz.id)
                if partner_pid is not None:
                    p_ee, p_ee_id = AccountOwnerType.PARTNER, partner_pid
                else:
                    p_ee, p_ee_id = AccountOwnerType.CUSTOMER, biz.customer_id
    
    return p_err, p_err_id, p_ee, p_ee_id

def format_vc_items_for_display(vc):
    """
    将虚拟合同的 elements 转换为 UI 友好的展示格式
    返回: (display_type, items_list)
    display_type: 'elements' | 'empty'
    """
    elements = (vc['elements'] if isinstance(vc, dict) else vc.elements) or {}

    # 统一结构：elements["items"]（新 VC）
    if "items" in elements and isinstance(elements["items"], list):
        elems = elements["items"]
        if elems:
            show_items = []
            for e in elems:
                row = {
                    "SKU_ID": e.get("sku_id"),
                    "数量": e.get("qty"),
                    "单价": e.get("price"),
                    "小计": e.get("subtotal"),
                    "发货点位ID": e.get("shipping_point_id"),
                    "收货点位ID": e.get("receiving_point_id"),
                }
                if e.get("deposit", 0) > 0:
                    row["单台押金"] = e.get("deposit")
                if e.get("sn_list"):
                    row["序列号列表"] = e.get("sn_list")
                show_items.append(row)
            return 'elements', show_items

    return 'empty', []

def calculate_cashflow_progress(session, vc, existing_cfs):
    """
    计算虚拟合同的资金流进度，并计算实时应付金额（扣除冲抵池余额）
    返回: {
        'is_return': bool,
        'goods': {'total': float, 'paid': float, 'balance': float, 'pool': float, 'due': float, 'label': str, 'paid_label': str, 'balance_label': str},
        'deposit': {'should': float, 'received': float, 'remaining': float},
        'payment_terms': dict
    }
    """
    from logic.constants import CashFlowType, AccountLevel1, CounterpartType
    from models import FinanceAccount, FinancialJournal
    from sqlalchemy import func
    
    # --- 计算冲抵池可用余额 ---
    pool_balance = 0.0
    party_type, party_id, account_level1 = None, None, None
    
    vc_type = vc.get('type') if isinstance(vc, dict) else vc.type
    vc_sc_id = vc.get('supply_chain_id') if isinstance(vc, dict) else vc.supply_chain_id
    vc_biz_id = vc.get('business_id') if isinstance(vc, dict) else vc.business_id
    vc_id = vc.get('id') if isinstance(vc, dict) else vc.id

    if vc_type in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT, VCType.MATERIAL_PROCUREMENT]:
        party_type, account_level1 = CounterpartType.SUPPLIER, AccountLevel1.PREPAYMENT
        if vc_sc_id:
            from models import SupplyChain
            sc = session.query(SupplyChain).get(vc_sc_id)
            if sc: party_id = sc.supplier_id
    elif vc_type == VCType.MATERIAL_SUPPLY:
        party_type, account_level1 = CounterpartType.CUSTOMER, AccountLevel1.PRE_COLLECTION
        if vc_biz_id:
            from models import Business
            biz = session.query(Business).get(vc_biz_id)
            if biz: party_id = biz.customer_id
            
    if party_id:
        account = session.query(FinanceAccount).filter(
            FinanceAccount.level1_name == account_level1,
            FinanceAccount.counterpart_type == party_type,
            FinanceAccount.counterpart_id == party_id
        ).first()
        if account:
            debit_sum = session.query(func.sum(FinancialJournal.debit)).filter(FinancialJournal.account_id == account.id).scalar() or 0.0
            credit_sum = session.query(func.sum(FinancialJournal.credit)).filter(FinancialJournal.account_id == account.id).scalar() or 0.0
            pool_balance = (credit_sum - debit_sum) if account_level1 == AccountLevel1.PRE_COLLECTION else (debit_sum - credit_sum)

    elements = (vc.get('elements') or {}) if isinstance(vc, dict) else (vc.elements or {})
    deposit_info = (vc.get('deposit_info') or {}) if isinstance(vc, dict) else (vc.deposit_info or {})
    is_return = (vc_type == VCType.RETURN)
    
    result = {
        'is_return': is_return,
        'goods': {},
        'deposit': {},
        'payment_terms': elements.get('payment_terms', {})
    }

    if is_return:
        # 退货合同：区分 货款退款 和 押金退还
        total_amt = elements.get('goods_amount', 0.0)
        paid_total = sum((c.get('amount', 0.0) if isinstance(c, dict) else c.amount) for c in existing_cfs if (c.get('type') if isinstance(c, dict) else c.type) == CashFlowType.REFUND)
        
        dep_should = elements.get('deposit_amount', 0.0)
        dep_received = sum((c.get('amount', 0.0) if isinstance(c, dict) else c.amount) for c in existing_cfs if (c.get('type') if isinstance(c, dict) else c.type) == CashFlowType.RETURN_DEPOSIT)
        
        result['goods'] = {
            'total': total_amt,
            'paid': paid_total,
            'balance': max(0, total_amt - paid_total),
            'pool': pool_balance,
            'due': max(0, total_amt - paid_total - pool_balance),
            'label': '应退货款总计',
            'paid_label': '已退货款',
            'balance_label': '待退货款余额'
        }
    else:
        # 常规合同：货款进度（预付、履约、退款、冲抵）
        total_amt = elements.get('total_amount', 0.0)
        # 将冲抵单独提出来的目的是为了在 UI 上展示“应付金额 = 总额 - 冲抵”
        applied_offsets = sum((c.get('amount', 0.0) if isinstance(c, dict) else c.amount) for c in existing_cfs if (c.get('type') if isinstance(c, dict) else c.type) == CashFlowType.OFFSET_PAY)
        cash_paid = sum((c.get('amount', 0.0) if isinstance(c, dict) else c.amount) for c in existing_cfs if (c.get('type') if isinstance(c, dict) else c.type) in [CashFlowType.PREPAYMENT, CashFlowType.FULFILLMENT, CashFlowType.REFUND])
        paid_total = applied_offsets + cash_paid
        
        dep_should = deposit_info.get('should_receive', 0.0)

        dep_received = deposit_info.get('total_deposit', 0.0)
        
        result['goods'] = {
            'total': total_amt,
            'applied_offsets': applied_offsets,
            'net_payable': total_amt - applied_offsets, # 扣除已确认冲抵后的“纯现金”应付
            'paid': paid_total,
            'balance': max(0, total_amt - paid_total),
            'pool': pool_balance,
            'due': max(0, total_amt - paid_total - pool_balance),
            'label': '合同总额',
            'paid_label': '累计已付/冲抵',
            'balance_label': '剩余待付'
        }

    
    result['deposit'] = {
        'should': dep_should,
        'received': dep_received,
        'remaining': max(0.0, dep_should - dep_received)
    }
    
    return result

def get_account_balance(session, level1_name, cp_type=None, cp_id=None):
    """
    获取特定会计科目的实时余额
    返回: Debit - Credit (正数代表借方余额，负数代表贷方余额)
    """
    from models import FinanceAccount, FinancialJournal
    from sqlalchemy import func
    
    # 1. 查找或创建科目
    from logic.finance import get_or_create_account
    acc = get_or_create_account(session, level1_name, cp_type, cp_id)
    
    # 2. 汇总借贷
    sums = session.query(
        func.sum(FinancialJournal.debit).label("debit_sum"),
        func.sum(FinancialJournal.credit).label("credit_sum")
    ).filter(FinancialJournal.account_id == acc.id).first()
    
    d_sum = float(sums.debit_sum or 0.0)
    c_sum = float(sums.credit_sum or 0.0)
    
    return d_sum - c_sum

# --- 财务上下文服务 ---

def get_logistics_finance_context(session, logistics_id):
    """
    构造物流记账所需的领域事实 Context
    """
    from models import Logistics, VirtualContract, MaterialInventory, SKU, FinancialJournal
    from sqlalchemy import func
    
    logistics = session.query(Logistics).get(logistics_id)
    if not logistics: return None
    
    vc = session.query(VirtualContract).get(logistics.virtual_contract_id)
    if not vc: return None
    
    cp_type, cp_id = get_counterpart_info(session, vc)
    
    ctx = {
        "logistics": logistics,
        "vc": vc,
        "cp_type": cp_type,
        "cp_id": cp_id,
        "total_amount": float((vc.elements or {}).get('total_amount', 0)),
        "is_return": (vc.type == VCType.RETURN),
        "items_cost": 0.0,
        "target_acc_l1": AccountLevel1.AR if cp_type == CounterpartType.CUSTOMER else AccountLevel1.AP,
        "deposit_acc_l1": AccountLevel1.DEPOSIT_PAYABLE if cp_type == CounterpartType.CUSTOMER else AccountLevel1.DEPOSIT_RECEIVABLE,
        "can_process": not logistics.finance_triggered and vc.subject_status == SubjectStatus.FINISH
    }
    
    if not ctx["can_process"]:
        return ctx

    # 1. 自动防重逻辑
    existing_entry = session.query(FinancialJournal).filter(
        FinancialJournal.ref_vc_id == vc.id,
        FinancialJournal.ref_type == "Logistics"
    ).first()
    ctx["is_duplicate"] = (existing_entry is not None and not ctx["is_return"])

    # 2. 成本核算逻辑
    if vc.type == VCType.MATERIAL_SUPPLY:
        total_cost = 0.0
        mat_elems = (vc.elements or {}).get("items", [])
        for item in mat_elems:
            sid = item.get("sku_id") or item.get("skuId")
            qty = float(item.get("qty") or 0)
            # 使用 sku.params.average_price
            sku_obj = session.query(SKU).get(sid)
            unit_cost = float(sku_obj.params.get("average_price", 0.0)) if (sku_obj and sku_obj.params) else 0.0
            if unit_cost == 0:
                unit_cost = float(sku_obj.params.get("unit_price", 0.0)) if (sku_obj and sku_obj.params) else 0.0
            total_cost += qty * unit_cost
        ctx["items_cost"] = total_cost

    elif vc.type == VCType.RETURN:
        total_asset_cost = 0.0
        ret_elems = (vc.elements or {}).get("items", [])
        for item in ret_elems:
            sid = item.get("sku_id")
            qty = float(item.get("qty") or 0)
            # 使用 sku.params.average_price
            sku_obj = session.query(SKU).get(sid)
            u_cost = float(sku_obj.params.get("average_price", 0.0)) if (sku_obj and sku_obj.params) else 0.0
            if u_cost == 0:
                u_cost = float(sku_obj.params.get("unit_price", 0.0)) if (sku_obj and sku_obj.params) else 0.0
            total_asset_cost += qty * u_cost
        ctx["items_cost"] = total_asset_cost
        
    return ctx

def get_cashflow_finance_context(session, cash_flow_id):
    """
    构造现金流记账所需的领域事实 Context
    """
    from models import CashFlow, VirtualContract, BankAccount
    from sqlalchemy import func
    
    cf = session.query(CashFlow).get(cash_flow_id)
    if not cf: return None
    
    vc = session.query(VirtualContract).get(cf.virtual_contract_id) if cf.virtual_contract_id else None
    cp_type, cp_id = None, None
    is_income = False
    
    # 逻辑穿透
    if vc:
        cp_type, cp_id = get_counterpart_info(session, vc)
        active_vc = vc
        if vc.type == VCType.RETURN and vc.related_vc_id:
            active_vc = session.query(VirtualContract).get(vc.related_vc_id) or vc
        
        if active_vc.type == VCType.MATERIAL_SUPPLY:
            is_income = True
        elif vc.type == VCType.RETURN:
            direction = vc.return_direction or (vc.elements.get("return_direction") if vc.elements else None)
            is_income = direction and ReturnDirection.US_TO_SUPPLIER in direction
            
    elif cf.type == CashFlowType.DEPOSIT_OFFSET_IN:
        payer_acc = session.query(BankAccount).get(cf.payer_account_id) if cf.payer_account_id else None
        payee_acc = session.query(BankAccount).get(cf.payee_account_id) if cf.payee_account_id else None
        target_acc = payer_acc if (payer_acc and payer_acc.owner_type != AccountOwnerType.OURSELVES) else payee_acc
        if target_acc:
            cp_type = target_acc.owner_type.capitalize()
            cp_id = target_acc.owner_id
            is_income = (cp_type == CounterpartType.CUSTOMER)

    # 计算核销进度
    ar_ap_amt, pre_amt = 0.0, 0.0
    if cf.type in [CashFlowType.PREPAYMENT, CashFlowType.FULFILLMENT] and vc:
        total_amt = float((vc.elements or {}).get('total_amount', 0))
        paid_before = session.query(func.sum(CashFlow.amount)).filter(
            CashFlow.virtual_contract_id == vc.id,
            CashFlow.type.in_([CashFlowType.PREPAYMENT, CashFlowType.FULFILLMENT, CashFlowType.OFFSET_PAY]),
            CashFlow.id != cf.id
        ).scalar() or 0.0
        remaining = max(0, total_amt - paid_before)
        ar_ap_amt = min(cf.amount, remaining)
        pre_amt = max(0, cf.amount - remaining)
        
    # 获取我方银行 ID
    our_bank_id = None
    payer_acc = session.query(BankAccount).get(cf.payer_account_id) if cf.payer_account_id else None
    payee_acc = session.query(BankAccount).get(cf.payee_account_id) if cf.payee_account_id else None
    if payee_acc and payee_acc.owner_type == AccountOwnerType.OURSELVES: our_bank_id = payee_acc.id
    elif payer_acc and payer_acc.owner_type == AccountOwnerType.OURSELVES: our_bank_id = payer_acc.id

    return {
        "cf": cf,
        "vc": vc,
        "cp_type": cp_type,
        "cp_id": cp_id,
        "is_income": is_income,
        "ar_ap_amt": ar_ap_amt,
        "pre_amt": pre_amt,
        "our_bank_id": our_bank_id,
        "can_process": not cf.finance_triggered
    }


# =============================================================================
# 物料供应提案生成
# =============================================================================

from logic.vc.queries import get_latest_supply_batches_by_sku, get_available_batches_by_sku


def _warehouse_priority(point_type: str) -> tuple:
    """仓库优先级：供应商仓 > 自有仓 > 客户仓"""
    if point_type == "供应商仓":
        return (1, 0)
    elif point_type == "自有仓":
        return (2, 0)
    else:
        return (3, 0)


def generate_material_supply_proposal(session, business_id: int, items: List[dict]) -> dict:
    """
    生成物料供应出货提案。

    逻辑：
    1. 对每个需求行，查历史批次新鲜度下限
    2. 过滤可用批次行（batch_no >= last_sent），按 FIFO + 仓库优先级分配
    3. 返回推荐方案 + 各 SKU 其他可选批次

    Args:
        business_id: 业务ID
        items: 客户需求列表 [{sku_id, qty, receiving_point_id}, ...]

    Returns:
        {
            valid: bool,
            proposed_plan: [...],
            alternatives: [...],
            total_amt: float,
            error: str | None
        }
    """
    from models import SKU, Point
    from logic.vc.queries import get_latest_supply_batches_by_sku, get_available_batches_by_sku

    # 批量查 SKU 信息
    sku_ids = list(set(i["sku_id"] for i in items))
    sku_map = {s.id: s for s in session.query(SKU).filter(SKU.id.in_(sku_ids)).all()}

    # 批量查点位信息
    pt_ids = list(set(i["receiving_point_id"] for i in items))
    pt_map = {p.id: p for p in session.query(Point).filter(Point.id.in_(pt_ids)).all()}

    # 查历史批次新鲜度
    last_batches = get_latest_supply_batches_by_sku(session, business_id)

    proposed_plan = []
    alternatives = []
    total_amt = 0.0
    errors = []

    for idx, item in enumerate(items):
        sku_id = item["sku_id"]
        qty_needed = float(item["qty"])
        rp_id = item["receiving_point_id"]

        sku_obj = sku_map.get(sku_id)
        rp_name = pt_map.get(rp_id).name if pt_map.get(rp_id) else f"点位{rp_id}"

        # 历史批次新鲜度下限
        last_bn = last_batches.get((sku_id, rp_id))
        all_batches = get_available_batches_by_sku(session, sku_id)
        if last_bn:
            all_batches = [b for b in all_batches if b["batch_no"] and b["batch_no"] >= last_bn]

        if not all_batches:
            errors.append(f"SKU {sku_obj.name if sku_obj else sku_id}（{rp_name}）：无可用批次" +
                          (f"，上次供货批次 {last_bn}" if last_bn else "，无历史供货记录"))
            continue

        # 收集所有可选方案（用于 alternatives）
        all_options = sorted(all_batches, key=lambda x: (x["batch_no"], _warehouse_priority(x["point_type"])))

        # FIFO 分配：先按 batch_no 排序，同批次按仓库优先级
        sorted_batches = sorted(all_batches, key=lambda x: (x["batch_no"], _warehouse_priority(x["point_type"])))

        # 按仓库合并同批次但不同仓库的行
        merged = {}
        for b in sorted_batches:
            key = (b["batch_no"], b["point_id"])
            if key not in merged:
                merged[key] = dict(b)
            else:
                merged[key]["qty"] += b["qty"]
        merged_batches = list(merged.values())

        # FIFO 凑够 qty_needed
        remaining = qty_needed
        sku_lines = []
        proposed_batch_nos = []
        for b in merged_batches:
            if remaining <= 0:
                break
            take = min(b["qty"], remaining)
            price = float(sku_obj.params.get("unit_price", 0)) if sku_obj and sku_obj.params else 0.0
            sku_lines.append({
                "idx": idx,
                "sku_id": sku_id,
                "sku_name": sku_obj.name if sku_obj else f"SKU{sku_id}",
                "qty": take,
                "receiving_point_id": rp_id,
                "receiving_point_name": rp_name,
                "batch_no": b["batch_no"],
                "shipping_point_id": b["point_id"],
                "shipping_point_name": b["point_name"],
                "unit_price": price,
                "subtotal": take * price,
            })
            proposed_batch_nos.append(f"{b['batch_no']}({b['point_name']}, {int(take)}件)")
            remaining -= take
            total_amt += take * price

        if remaining > 0:
            errors.append(f"SKU {sku_obj.name if sku_obj else sku_id}（{rp_name}）：库存不足，当前可发 {qty_needed - remaining}，需要 {qty_needed}")
            continue

        proposed_plan.extend(sku_lines)

        # alternatives：当前行所有可用选项
        options_for_sku = [
            {
                "batch_no": b["batch_no"],
                "shipping_point_id": b["point_id"],
                "shipping_point_name": b["point_name"],
                "available_qty": b["qty"],
                "warehouse_priority": _warehouse_priority(b["point_type"])[0],
            }
            for b in all_options
        ]
        alternatives.append({
            "idx": idx,
            "sku_id": sku_id,
            "sku_name": sku_obj.name if sku_obj else f"SKU{sku_id}",
            "receiving_point_id": rp_id,
            "receiving_point_name": rp_name,
            "options": options_for_sku,
            "current_proposed": " + ".join(proposed_batch_nos),
        })

    valid = len(errors) == 0 and len(proposed_plan) > 0

    # 生成摘要
    summary_parts = []
    by_sku_rp = {}
    for line in proposed_plan:
        key = (line["sku_name"], line["receiving_point_name"])
        if key not in by_sku_rp:
            by_sku_rp[key] = 0
        by_sku_rp[key] += line["qty"]
    for (sname, rpname), total_q in by_sku_rp.items():
        summary_parts.append(f"{sname}({rpname}): {total_q}件")

    summary = f"共需{len(set(l['shipping_point_name'] for l in proposed_plan))}个仓库发货，" + "，".join(summary_parts)

    return {
        "valid": valid,
        "proposed_plan": proposed_plan,
        "alternatives": alternatives,
        "total_amt": total_amt,
        "summary": summary,
        "errors": errors if errors else None,
    }
