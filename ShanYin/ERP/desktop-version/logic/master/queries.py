"""
主数据领域 - UI专用查询层

本模块提供主数据相关的UI查询函数，返回格式化字典供UI层直接使用。
遵循CQRS模式，只处理读操作，不涉及写操作。
"""

from typing import List, Dict, Optional, Any
from sqlalchemy import func, String
from models import (
    get_session, ChannelCustomer, Supplier, Point, SKU, ExternalPartner, BankAccount,
    EquipmentInventory, MaterialInventory, SupplyChain, Contract, PartnerRelation
)
from logic.constants import (
    AccountOwnerType, SKUType, BankInfoKey, OperationalStatus
)


# ============================================================================
# 1. 客户相关查询
# ============================================================================

def get_customers_for_ui(
    status: Optional[str] = None,
    search_keyword: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    获取客户列表（专用于UI展示）
    """
    session = get_session()
    try:
        query = session.query(ChannelCustomer)

        if search_keyword:
            query = query.filter(
                ChannelCustomer.name.contains(search_keyword) |
                func.cast(ChannelCustomer.id, String).contains(search_keyword)
            )

        customers = query.order_by(ChannelCustomer.created_at.desc()).limit(limit).all()

        result = []
        for customer in customers:
            info = customer.info or {}
            if isinstance(info, str):
                import json
                try: info = json.loads(info)
                except: info = {}
            result.append({
                "id": customer.id,
                "name": customer.name,
                "contact": info.get("contact", ""),
                "phone": info.get("phone", ""),
                "email": info.get("email", ""),
                "address": info.get("address", ""),
                "status": info.get("status", "active"),
                "status_label": _get_status_label(info.get("status")),
                "info": info,
                "created_at": customer.created_at.strftime("%Y-%m-%d") if customer.created_at else ""
            })

        return result
    finally:
        session.close()


def get_customer_by_id(customer_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取客户详情
    """
    session = get_session()
    try:
        customer = session.query(ChannelCustomer).get(customer_id)
        if not customer:
            return None
        return {
            "id": customer.id,
            "name": customer.name,
            "status": customer.status,
            "info": customer.info or {}
        }
    finally:
        session.close()


# ============================================================================
# 2. 供应商相关查询
# ============================================================================

def get_suppliers_for_ui(
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """获取供应商列表（专用于UI展示）"""
    session = get_session()
    try:
        query = session.query(Supplier)

        if category:
            query = query.filter(Supplier.category == category)

        suppliers = query.order_by(Supplier.id.desc()).limit(limit).all()

        result = []
        for supplier in suppliers:
            info = supplier.info or {}
            contact_info = info.get("contact_info", {}) if isinstance(info, dict) else {}

            # 获取该供应商的SKU列表
            sku_list = session.query(SKU).filter(SKU.supplier_id == supplier.id).all()
            sku_names = [sku.name for sku in sku_list]

            supply_types = set()
            for sku in sku_list:
                if sku.type_level1 == SKUType.EQUIPMENT:
                    supply_types.add("equipment")
                elif sku.type_level1 == SKUType.MATERIAL:
                    supply_types.add("material")

            result.append({
                "id": supplier.id,
                "name": supplier.name,
                "contact_person": contact_info.get("contact_person", ""),
                "phone": contact_info.get("phone", ""),
                "email": contact_info.get("email", ""),
                "address": supplier.address or "",
                "status": info.get("status", "active") if isinstance(info, dict) else "active",
                "status_label": _get_status_label(info.get("status") if isinstance(info, dict) else None),
                "supply_types": list(supply_types),
                "sku_count": len(sku_list),
                "sku_list": sku_names[:10],
                "created_at": "",
                "category": supplier.category or ""
            })

        return result
    finally:
        session.close()


def get_supplier_by_id(supplier_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取供应商详情
    """
    session = get_session()
    try:
        supplier = session.query(Supplier).get(supplier_id)
        if not supplier:
            return None
        return {
            "id": supplier.id,
            "name": supplier.name,
            "status": supplier.status,
            "contact_info": supplier.contact_info or {}
        }
    finally:
        session.close()


def get_supplier_by_name(name: str, fuzzy: bool = False) -> Optional[Dict[str, Any]]:
    """
    根据名称获取供应商详情
    """
    session = get_session()
    try:
        query = session.query(Supplier)
        if fuzzy:
            supplier = query.filter(Supplier.name.like(f"%{name}%")).first()
        else:
            supplier = query.filter(Supplier.name == name).first()
        if not supplier: return None
        return {"id": supplier.id, "name": supplier.name, "contact_info": supplier.contact_info or {}}
    finally:
        session.close()


# ============================================================================
# 3. 点位相关查询
# ============================================================================

def get_points_for_ui(
    customer_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
    point_type: Optional[str] = None,
    search_keyword: Optional[str] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    """获取点位列表（专用于UI展示）"""
    session = get_session()
    try:
        query = session.query(Point)

        if customer_id is not None:
            query = query.filter(Point.customer_id == customer_id)
        if supplier_id is not None:
            query = query.filter(Point.supplier_id == supplier_id)
        if point_type:
            query = query.filter(Point.type == point_type)
        if search_keyword:
            query = query.filter(Point.name.like(f"%{search_keyword}%"))

        points = query.order_by(Point.name).limit(limit).all()

        # 批量预加载，消除 N+1
        customer_ids = list(set(p.customer_id for p in points if p.customer_id))
        supplier_ids = list(set(p.supplier_id for p in points if p.supplier_id))
        customer_map = {c.id: c.name for c in session.query(ChannelCustomer).filter(ChannelCustomer.id.in_(customer_ids)).all()} if customer_ids else {}
        supplier_map = {s.id: s.name for s in session.query(Supplier).filter(Supplier.id.in_(supplier_ids)).all()} if supplier_ids else {}

        result = []
        for point in points:
            result.append({
                "id": point.id,
                "name": point.name,
                "type": point.type or "",
                "address": point.address or "",
                "receiving_address": point.receiving_address or point.address or "",
                "customer_id": point.customer_id,
                "customer_name": customer_map.get(point.customer_id),
                "supplier_id": point.supplier_id,
                "supplier_name": supplier_map.get(point.supplier_id),
                "contact": "",
                "phone": "",
                "status": "active",
                "status_label": "正常",
                "created_at": "",
                "owner_label": (
                    f"[客户] {customer_map.get(point.customer_id)}"
                    if point.customer_id
                    else (
                        f"[供应商] {supplier_map.get(point.supplier_id)}"
                        if point.supplier_id
                        else "[公司] 闪饮自身"
                    )
                )
            })

        return result
    finally:
        session.close()


def get_point_by_name(name: str, fuzzy: bool = False) -> Optional[Dict[str, Any]]:
    """
    根据名称获取点位详情
    """
    session = get_session()
    try:
        query = session.query(Point)
        if fuzzy:
            point = query.filter(Point.name.like(f"%{name}%")).first()
        else:
            point = query.filter(Point.name == name).first()
        
        if not point: return None
        
        return {
            "id": point.id,
            "name": point.name,
            "type": point.type,
            "address": point.address,
            "customer_id": point.customer_id,
            "supplier_id": point.supplier_id
        }
    finally:
        session.close()


# ============================================================================
# 4. SKU相关查询
# ============================================================================

def get_skus_for_ui(
    supplier_id: Optional[int] = None,
    sku_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200
) -> List[Dict[str, Any]]:
    """获取SKU列表（专用于UI展示）"""
    session = get_session()
    try:
        query = session.query(SKU)

        if supplier_id:
            query = query.filter(SKU.supplier_id == supplier_id)
        if sku_type:
            query = query.filter(SKU.type_level1 == sku_type)

        skus = query.order_by(SKU.name).limit(limit).all()

        # 批量预加载供应商名称
        sup_ids = list(set(s.supplier_id for s in skus if s.supplier_id))
        supplier_map = {s.id: s.name for s in session.query(Supplier).filter(Supplier.id.in_(sup_ids)).all()} if sup_ids else {}

        result = []
        for sku in skus:
            params = sku.params or {}
            result.append({
                "id": sku.id,
                "name": sku.name,
                "model": sku.model or "",
                "spec": params.get("spec", ""),
                "type_level1": sku.type_level1 or "",
                "type_level2": sku.type_level2 or "",
                "category": sku.type_level2 or "",
                "unit": params.get("unit", "件"),
                "supplier_id": sku.supplier_id,
                "supplier_name": supplier_map.get(sku.supplier_id),
                "status": "active",
                "status_label": "正常",
                "price_info": params.get("price_info", {}),
                "created_at": ""
            })

        return result
    finally:
        session.close()

def get_equipment_inventory_summary() -> Dict[str, Any]:
    """获取设备库存汇总数据"""
    session = get_session()
    try:
        total_count = session.query(func.count(EquipmentInventory.id)).scalar() or 0
        stock_count = session.query(func.count(EquipmentInventory.id)).filter(EquipmentInventory.operational_status == OperationalStatus.STOCK).scalar() or 0
        operating_count = session.query(func.count(EquipmentInventory.id)).filter(EquipmentInventory.operational_status == OperationalStatus.OPERATING).scalar() or 0
        return {
            "total_count": total_count,
            "stock_count": stock_count,
            "operating_count": operating_count
        }
    finally:
        session.close()

def get_material_inventory_summary() -> Dict[str, Any]:
    """获取物料库存汇总数据"""
    session = get_session()
    try:
        # 新结构：按sku_id分组统计
        total_skus = session.query(func.count(func.distinct(MaterialInventory.sku_id))).filter(MaterialInventory.qty > 0).scalar() or 0
        total_quantity = session.query(func.sum(MaterialInventory.qty)).filter(MaterialInventory.qty > 0).scalar() or 0
        return {
            "total_skus": total_skus,
            "total_quantity": total_quantity or 0
        }
    finally:
        session.close()

def get_equipment_inventory_list(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取详情设备库存列表"""
    session = get_session()
    try:
        query = session.query(EquipmentInventory)
        if status:
            query = query.filter(EquipmentInventory.operational_status == status)
        
        equips = query.all()
        result = []
        for eq in equips:
            result.append({
                "设备ID": eq.id,
                "SN序列号": eq.sn,
                "品类ID": eq.sku_id,
                "品类名称": eq.sku.name if eq.sku else "未知",
                "运营状态": eq.operational_status,
                "所在点位": eq.point.name if eq.point else "自有仓"
            })
        return result
    finally:
        session.close()

def get_material_inventory_list() -> List[Dict[str, Any]]:
    """获取物料详情列表"""
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        # 按sku_id分组，汇总各SKU的批次库存
        invs = session.query(
            MaterialInventory.sku_id,
            func.sum(MaterialInventory.qty).label("total_qty")
        ).group_by(MaterialInventory.sku_id).having(func.sum(MaterialInventory.qty) > 0).all()

        # 收集所有sku_id并批量查询
        sku_ids = [inv.sku_id for inv in invs]
        skus_map = {}
        if sku_ids:
            skus = session.query(SKU).filter(SKU.id.in_(sku_ids)).all()
            skus_map = {s.id: s for s in skus}

        # 收集所有批次行用于分仓统计
        all_rows = session.query(MaterialInventory).filter(
            MaterialInventory.sku_id.in_(sku_ids),
            MaterialInventory.qty > 0
        ).all()

        # 收集所有需要的点位ID
        all_point_ids = set(br.point_id for br in all_rows if br.point_id)
        point_map = {}
        if all_point_ids:
            pts = session.query(Point).filter(Point.id.in_(all_point_ids)).all()
            point_map = {p.id: p.name for p in pts}

        # 按sku_id分组批次行
        batches_by_sku = {}
        for br in all_rows:
            if br.sku_id not in batches_by_sku:
                batches_by_sku[br.sku_id] = []
            batches_by_sku[br.sku_id].append(br)

        result = []
        for inv in invs:
            sku = skus_map.get(inv.sku_id)
            batches = batches_by_sku.get(inv.sku_id, [])

            # 转换库存分布：point_id -> "点位名称: 数量"
            dist = {}
            for br in batches:
                pt_name = point_map.get(br.point_id, f"点位{br.point_id}")
                dist[pt_name] = dist.get(pt_name, 0) + br.qty

            # 从sku.params获取average_price
            avg_price = 0.0
            if sku and sku.params:
                avg_price = float(sku.params.get("average_price", 0.0) or 0)

            result.append({
                "物料ID": inv.sku_id,
                "物料名称": sku.name if sku else "未知",
                "总余额": inv.total_qty,
                "平均单价": avg_price,
                "库存分布": dist
            })

        return result
    finally:
        session.close()

def get_warehouse_points() -> List[Dict[str, Any]]:
    """获取所有仓库类型的点位"""
    session = get_session()
    try:
        points = session.query(Point).filter(Point.customer_id == None, Point.supplier_id == None).all()
        return [{"id": p.id, "name": p.name, "type": p.type, "address": p.address} for p in points]
    finally:
        session.close()


def get_material_movement_timeline(sku_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    重建物料出入库流水记录。
    基于 VC 类型 + subject_status 完成时间 + 仓库点位信息，重建每笔出入库明细。

    返回: [{
        "sku_id": int,
        "sku_name": str,
        "vc_id": int,
        "vc_type": str,
        "direction": str,       # 入库 / 出库
        "warehouse": str,       # 仓库名称
        "qty": float,
        "timestamp": datetime,
        "biz_id": int or None,
        "description": str,
    }]
    """
    session = get_session()
    try:
        from models import VirtualContract, VirtualContractStatusLog, SKU, Point, Business, ChannelCustomer
        from logic.constants import VCType, SubjectStatus, SystemConstants

        # 1. 查 subject=FINISH 的时间戳
        status_logs = session.query(VirtualContractStatusLog).filter(
            VirtualContractStatusLog.category == 'subject',
            VirtualContractStatusLog.status_name == SubjectStatus.FINISH
        ).all()
        vc_finish_time = {}
        for log in status_logs:
            if log.vc_id not in vc_finish_time:
                vc_finish_time[log.vc_id] = log.timestamp

        # 2. 查物料采购/物料供应 VC（subject_status = FINISH）
        vc_query = session.query(VirtualContract).filter(
            VirtualContract.type.in_([VCType.MATERIAL_PROCUREMENT, VCType.MATERIAL_SUPPLY]),
            VirtualContract.subject_status == SubjectStatus.FINISH
        )
        if sku_id:
            # 需要通过 elements 过滤，这个在 Python 层处理
            pass

        all_movements = []
        point_map = {}
        sku_map = {}

        for vc in vc_query.all():
            elements = vc.elements or {}
            items = elements.get('elements') or []

            # 过滤指定 sku_id
            if sku_id:
                items = [it for it in items if int(it.get('sku_id') or 0) == sku_id]
                if not items:
                    continue

            ts = vc_finish_time.get(vc.id, vc.status_timestamp)

            # 预加载 SKU 和 Point（批量）
            for item in items:
                sid = int(item.get('sku_id') or 0)
                if sid not in sku_map:
                    sku = session.query(SKU).get(sid)
                    sku_map[sid] = sku.name if sku else f"SKU-{sid}"

                if vc.type == VCType.MATERIAL_PROCUREMENT:
                    direction = "入库"
                    point_id = item.get('receiving_point_id')
                    warehouse = None
                    if point_id:
                        if point_id not in point_map:
                            pt = session.query(Point).get(int(point_id))
                            point_map[point_id] = pt.name if pt else None
                        warehouse = point_map[point_id]
                    qty = float(item.get('qty') or 0)
                    desc = f"物料采购入库"
                else:
                    direction = "出库"
                    point_id = item.get('shipping_point_id')
                    warehouse = None
                    if point_id:
                        if point_id not in point_map:
                            pt = session.query(Point).get(int(point_id))
                            point_map[point_id] = pt.name if pt else None
                        warehouse = point_map[point_id]
                    qty = -float(item.get('qty') or 0)
                    desc = f"物料供应出库"

                if not warehouse:
                    warehouse = SystemConstants.DEFAULT_POINT

                all_movements.append({
                    "sku_id": sid,
                    "sku_name": sku_map[sid],
                    "vc_id": vc.id,
                    "vc_type": vc.type,
                    "direction": direction,
                    "warehouse": warehouse,
                    "qty": qty,
                    "timestamp": ts,
                    "biz_id": vc.business_id,
                    "description": desc,
                })

        # 按时间倒序
        all_movements.sort(key=lambda x: x["timestamp"] or "", reverse=True)
        return all_movements
    finally:
        session.close()


def get_sku_map_by_names(names: List[str]) -> Dict[str, Any]:
    """获取 SKU 名称到详情的映射"""
    session = get_session()
    try:
        skus = session.query(SKU).filter(SKU.name.in_(names)).all()
        return {s.name: {"id": s.id, "type": s.type_level1} for s in skus}
    finally:
        session.close()


# ============================================================================
# 5. 合作伙伴相关查询
# ============================================================================

def get_external_partner_by_id(partner_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取外部合作伙伴详情
    
    Args:
        partner_id: 合作伙伴ID
    
    Returns:
        合作伙伴详情字典，如果不存在则返回None
    """
    session = get_session()
    try:
        partner = session.query(ExternalPartner).get(partner_id)
        if not partner:
            return None
        
        return {
            "id": partner.id,
            "name": partner.name or "",
            "type": partner.type or "",
            "address": partner.address or "",
            "contact_info": partner.contact_info or {},
            "content": partner.content or "",
            "status": "active",
            "created_at": partner.created_at.strftime("%Y-%m-%d") if partner.created_at else ""
        }
    finally:
        session.close()


def get_partners_for_ui(
    status: Optional[str] = None,
    partner_type: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """获取外部合作伙伴列表（专用于UI展示）"""
    session = get_session()
    try:
        query = session.query(ExternalPartner)

        if partner_type:
            query = query.filter(ExternalPartner.type == partner_type)

        partners = query.order_by(ExternalPartner.id.desc()).limit(limit).all()

        result = []
        for partner in partners:
            result.append({
                "id": partner.id,
                "name": partner.name or "",
                "partner_type": partner.type or "",
                "contact_person": "",
                "phone": "",
                "email": "",
                "address": partner.address or "",
                "status": "active",
                "status_label": "正常",
                "notes": partner.content or "",
                "created_at": ""
            })

        return result
    finally:
        session.close()


def get_partner_detail_for_ui(partner_id: int) -> Optional[Dict[str, Any]]:
    """
    获取外部合作方详情（专用于UI展示，含银行账户和合作关系）

    Args:
        partner_id: 合作方ID

    Returns:
        合作方详情字典，如果不存在则返回None
    """
    session = get_session()
    try:
        partner = session.query(ExternalPartner).get(partner_id)
        if not partner:
            return None

        # 获取银行账户
        bank_accounts = get_bank_accounts_for_ui(
            owner_type=AccountOwnerType.PARTNER,
            owner_id=partner_id
        )

        # 获取合作关系
        relations = get_partner_relations(partner_id=partner_id, active_only=False)

        # 获取归属主体名称
        for rel in relations:
            rel["owner_name"] = _get_owner_name(session, rel["owner_type"], rel["owner_id"])

        return {
            "id": partner.id,
            "name": partner.name or "",
            "type": partner.type or "",
            "address": partner.address or "",
            "content": partner.content or "",
            "status": "active",
            "bank_accounts": bank_accounts,
            "relations": relations,
            "created_at": ""
        }
    finally:
        session.close()


def _get_owner_name(session, owner_type: str, owner_id: Optional[int]) -> str:
    """获取归属主体名称"""
    if owner_type == AccountOwnerType.OURSELVES:
        return "[我方] 闪饮业务中心"
    elif owner_type == "business":
        return f"[业务] ID:{owner_id}"
    elif owner_type == "supply_chain":
        return f"[供应链] ID:{owner_id}"
    else:
        return f"[{owner_type}] ID:{owner_id}"


# ============================================================================
# 6. 银行账户相关查询（master领域）
# ============================================================================

def get_bank_accounts_for_ui(
    owner_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    获取银行账户列表（专用于UI展示）
    
    Args:
        owner_type: 所有者类型过滤
        owner_id: 所有者ID过滤
        status: 状态过滤
        limit: 返回数量限制
    
    Returns:
        格式化后的银行账户列表
    """
    session = get_session()
    try:
        query = session.query(BankAccount)
        
        if owner_type:
            query = query.filter(BankAccount.owner_type == owner_type)
        
        if owner_id:
            query = query.filter(BankAccount.owner_id == owner_id)
        
        # models.py 中 BankAccount 没有 created_at 和 status 字段，使用 id 排序并移除 status
        accounts = query.order_by(BankAccount.id.desc()).limit(limit).all()
        
        # 批量获取所有者名称，消除 N+1
        customer_ids = list(set(a.owner_id for a in accounts if a.owner_type == AccountOwnerType.CUSTOMER))
        supplier_ids = list(set(a.owner_id for a in accounts if a.owner_type == AccountOwnerType.SUPPLIER))
        partner_ids = list(set(a.owner_id for a in accounts if a.owner_type == AccountOwnerType.PARTNER))
        
        customer_names = {c.id: c.name for c in session.query(ChannelCustomer).filter(ChannelCustomer.id.in_(customer_ids)).all()} if customer_ids else {}
        supplier_names = {s.id: s.name for s in session.query(Supplier).filter(Supplier.id.in_(supplier_ids)).all()} if supplier_ids else {}
        partner_names = {p.id: p.name for p in session.query(ExternalPartner).filter(ExternalPartner.id.in_(partner_ids)).all()} if partner_ids else {}
        
        result = []
        for acc in accounts:
            info = acc.account_info or {}
            
            # 确定所有者名称
            if acc.owner_type == AccountOwnerType.CUSTOMER:
                owner_name = f"[客户] {customer_names.get(acc.owner_id, '未知')}"
            elif acc.owner_type == AccountOwnerType.SUPPLIER:
                owner_name = f"[供应商] {supplier_names.get(acc.owner_id, '未知')}"
            elif acc.owner_type == AccountOwnerType.PARTNER:
                owner_name = f"[合作方] {partner_names.get(acc.owner_id, '未知')}"
            elif acc.owner_type == AccountOwnerType.OURSELVES:
                owner_name = f"[我方] {info.get(BankInfoKey.BANK_NAME, '未知账户')}"
            else:
                owner_name = "未知所有者"
            
            result.append({
                "id": acc.id,
                "bank_name": info.get(BankInfoKey.BANK_NAME, '未知银行'),
                "account_no": info.get(BankInfoKey.ACCOUNT_NO, ''),
                "account_type": info.get(BankInfoKey.ACCOUNT_TYPE, '对公账户'),
                "holder_name": info.get(BankInfoKey.HOLDER_NAME, ''),
                "owner_type": acc.owner_type,
                "owner_id": acc.owner_id,
                "owner_name": owner_name,
                "owner_label": owner_name,
                "balance": info.get('balance', 0),
                "balance_formatted": f"¥{info.get('balance', 0):,.2f}",
                "is_default": acc.is_default,
                "created_at": ""
            })
        
        return result
    finally:
        session.close()


# ============================================================================
# 7. 库存相关查询 (用于库存拨付等场景)
# ============================================================================

def get_stock_equipment_for_allocation(
    operational_status: Optional[str] = None,
    limit: int = 500
) -> List[Dict[str, Any]]:
    """
    获取可用于库存拨付的设备列表
    
    Args:
        operational_status: 运营状态过滤，默认为 STOCK（库存中）
        limit: 返回数量限制
    
    Returns:
        格式化的设备列表，包含SKU信息、点位信息
    """
    session = get_session()
    try:
        status_filter = operational_status or OperationalStatus.STOCK
        
        equipments = session.query(EquipmentInventory).filter(
            EquipmentInventory.operational_status == status_filter
        ).limit(limit).all()
        
        result = []
        for eq in equipments:
            sku = session.query(SKU).get(eq.sku_id) if eq.sku_id else None
            point = session.query(Point).get(eq.point_id) if eq.point_id else None
            
            result.append({
                "id": eq.id,
                "sn": eq.sn or "",
                "sku_id": eq.sku_id,
                "sku_name": sku.name if sku else "未知品类",
                "sku_model": sku.model if sku else "",
                "operational_status": eq.operational_status,
                "device_status": eq.device_status,
                "point_id": eq.point_id,
                "point_name": point.name if point else "库存中",
                "warehouse_name": point.name if point else "自有仓",
                "deposit_amount": eq.deposit_amount or 0.0,
            })
        
        return result
    finally:
        session.close()


def get_material_stock_for_supply(
    min_balance: float = 0.01,
    limit: int = 500
) -> List[Dict[str, Any]]:
    """
    获取可用于物料供应的库存物料列表

    Args:
        min_balance: 最小库存余额过滤（已废弃，保留参数兼容）
        limit: 返回数量限制

    Returns:
        格式化的物料库存列表，包含可供应数量、仓库分布
    """
    session = get_session()
    try:
        # 新结构：按sku_id分组统计
        materials = session.query(
            MaterialInventory.sku_id,
            func.sum(MaterialInventory.qty).label("total_qty")
        ).group_by(MaterialInventory.sku_id).having(func.sum(MaterialInventory.qty) >= min_balance).limit(limit).all()

        if not materials:
            return []

        sku_ids = [m.sku_id for m in materials]
        skus_map = {}
        if sku_ids:
            skus = session.query(SKU).filter(SKU.id.in_(sku_ids)).all()
            skus_map = {s.id: s for s in skus}

        # 查询所有相关批次行用于分仓
        all_rows = session.query(MaterialInventory).filter(
            MaterialInventory.sku_id.in_(sku_ids),
            MaterialInventory.qty > 0
        ).all()

        # 收集点位
        all_point_ids = set(br.point_id for br in all_rows if br.point_id)
        point_map = {}
        if all_point_ids:
            pts = session.query(Point).filter(Point.id.in_(all_point_ids)).all()
            point_map = {p.id: p.name for p in pts}

        # 按sku_id分组批次行
        batches_by_sku = {}
        for br in all_rows:
            if br.sku_id not in batches_by_sku:
                batches_by_sku[br.sku_id] = []
            batches_by_sku[br.sku_id].append(br)

        result = []
        for mat in materials:
            sku = skus_map.get(mat.sku_id)
            batches = batches_by_sku.get(mat.sku_id, [])

            # 从sku.params获取average_price
            avg_price = 0.0
            if sku and sku.params:
                avg_price = float(sku.params.get("average_price", 0.0) or 0)

            # 分仓统计
            stock_dist = {}
            available_warehouses = []
            for br in batches:
                pt_name = point_map.get(br.point_id, f"点位{br.point_id}")
                stock_dist[pt_name] = stock_dist.get(pt_name, 0) + br.qty
                available_warehouses.append({"warehouse": pt_name, "qty": br.qty, "point_id": br.point_id})

            result.append({
                "id": sku.id if sku else mat.sku_id,
                "sku_id": mat.sku_id,
                "sku_name": sku.name if sku else "未知物料",
                "sku_model": sku.model if sku else "",
                "total_balance": mat.total_qty,
                "average_price": avg_price,
                "stock_distribution": stock_dist,
                "available_warehouses": available_warehouses,
            })

        return result
    finally:
        session.close()




# ============================================================================
# 8. 私有辅助函数
# ============================================================================

def _get_status_label(status: Optional[str]) -> str:
    """获取状态中文标签"""
    status_map = {
        "active": "正常",
        "inactive": "停用",
        "frozen": "冻结",
        "pending": "待审核",
        "verified": "已认证",
    }
    return status_map.get(status, status or "未知")


def _get_bank_account_owner_name(session, account) -> str:
    """获取银行账户所有者名称"""
    owner_type = account.owner_type
    owner_id = account.owner_id
    
    if owner_type == AccountOwnerType.CUSTOMER:
        obj = session.query(ChannelCustomer).get(owner_id)
        return f"[客户] {obj.name}" if obj else "[客户] 未知"
    elif owner_type == AccountOwnerType.SUPPLIER:
        obj = session.query(Supplier).get(owner_id)
        return f"[供应商] {obj.name}" if obj else "[供应商] 未知"
    elif owner_type == AccountOwnerType.OURSELVES:
        return "[我方] 闪饮业务中心"
    else:
        return "[未知]"


def get_points_by_customer(customer_id: int) -> List[Dict[str, Any]]:
    """获取指定客户的所有点位"""
    session = get_session()
    try:
        points = session.query(Point).filter(Point.customer_id == customer_id).all()
        return [{"id": p.id, "name": p.name, "address": p.address} for p in points]
    finally:
        session.close()

def get_skus_by_names(sku_names: List[str], supplier_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """获取指定名称列表的 SKU"""
    session = get_session()
    try:
        query = session.query(SKU).filter(SKU.name.in_(sku_names))
        if supplier_id:
            query = query.filter(SKU.supplier_id == supplier_id)
        skus = query.all()
        return [{"id": s.id, "name": s.name, "supplier_id": s.supplier_id} for s in skus]
    finally:
        session.close()

def get_material_inventory_all() -> List[Dict[str, Any]]:
    """获取所有物料库存信息（新批次结构）"""
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        # 新结构：查询所有批次行
        invs = session.query(MaterialInventory).options(
            joinedload(MaterialInventory.sku),
            joinedload(MaterialInventory.point)
        ).filter(MaterialInventory.qty > 0).all()

        return [
            {
                "sku_id": i.sku_id,
                "sku_name": i.sku.name if i.sku else "未知",
                "batch_no": i.batch_no,
                "point_id": i.point_id,
                "point_name": i.point.name if i.point else f"点位{i.point_id}",
                "qty": i.qty,
                "latest_purchase_vc_id": i.latest_purchase_vc_id
            }
            for i in invs
        ]
    finally:
        session.close()

def get_supply_chains_by_type(sku_type: str) -> List[Dict[str, Any]]:
    """获取指定类型的供应链协议"""
    session = get_session()
    try:
        chains = session.query(SupplyChain).filter(SupplyChain.type == sku_type).all()
        return [
            {
                "id": c.id,
                "supplier_id": c.supplier_id,
                "supplier_name": c.supplier.name if c.supplier else "未知",
                "type": c.type,
                "payment_terms": c.payment_terms
            }
            for c in chains
        ]
    finally:
        session.close()

def get_supply_chain_by_id(sc_id: int) -> Optional[Dict[str, Any]]:
    """获取供应链详情"""
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        c = session.query(SupplyChain).options(joinedload(SupplyChain.supplier)).get(sc_id)
        if not c: return None

        pricing_dict = c.get_pricing_dict()
        # 构建 sku_id -> sku_name 映射
        sku_name_map = {}
        for sku_id_key in pricing_dict.keys():
            sku_id_int = int(sku_id_key) if str(sku_id_key).isdigit() else None
            if sku_id_int:
                sku_obj = session.query(SKU).get(sku_id_int)
                sku_name_map[sku_id_key] = sku_obj.name if sku_obj else sku_id_key
            else:
                sku_name_map[sku_id_key] = sku_id_key

        return {
            "id": c.id,
            "supplier_id": c.supplier_id,
            "supplier_name": c.supplier.name if c.supplier else "未知供应商",
            "type": c.type,
            "payment_terms": c.payment_terms,
            "pricing_dict": pricing_dict,
            "sku_name_map": sku_name_map,
            "supplier": {"name": c.supplier.name} if c.supplier else None
        }
    finally:
        session.close()


def get_point_by_id(point_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取点位详情
    """
    session = get_session()
    try:
        point = session.query(Point).get(point_id)
        if not point:
            return None
        
        return {
            "id": point.id,
            "name": point.name or "",
            "type": point.type or "",
            "address": point.address or "",
            "receiving_address": point.receiving_address or point.address or "",
            "customer_id": point.customer_id,
            "supplier_id": point.supplier_id
        }
    finally:
        session.close()

def get_partner_by_id(partner_id: int) -> Optional[Dict[str, Any]]:
    """获取合作方详情"""
    session = get_session()
    try:
        p = session.query(ExternalPartner).get(partner_id)
        if not p: return None
        return {"id": p.id, "name": p.name, "type": p.type}
    finally:
        session.close()


def get_partner_relations(
    partner_id: Optional[int] = None,
    owner_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    relation_type: Optional[str] = None,
    active_only: bool = True
) -> List[Dict[str, Any]]:
    """
    查询合作方关系列表，支持多维过滤。

    Args:
        partner_id: 合作方ID
        owner_type: 归属主体类型 (customer/supplier/ourselves)
        owner_id: 归属主体ID
        relation_type: 合作模式
        active_only: 是否仅查询有效关系（ended_at IS NULL）
    """
    session = get_session()
    try:
        query = session.query(PartnerRelation)

        if partner_id is not None:
            query = query.filter(PartnerRelation.partner_id == partner_id)
        if owner_type is not None:
            query = query.filter(PartnerRelation.owner_type == owner_type)
        if owner_id is not None:
            query = query.filter(PartnerRelation.owner_id == owner_id)
        if relation_type is not None:
            query = query.filter(PartnerRelation.relation_type == relation_type)
        if active_only:
            query = query.filter(PartnerRelation.ended_at.is_(None))

        relations = query.order_by(PartnerRelation.id.desc()).all()

        # 批量获取合作方名称
        partner_ids = list(set(r.partner_id for r in relations))
        partner_names = {
            p.id: p.name for p in
            session.query(ExternalPartner).filter(ExternalPartner.id.in_(partner_ids)).all()
        } if partner_ids else {}

        result = []
        for r in relations:
            result.append({
                "id": r.id,
                "partner_id": r.partner_id,
                "partner_name": partner_names.get(r.partner_id, ""),
                "owner_type": r.owner_type,
                "owner_id": r.owner_id,
                "relation_type": r.relation_type,
                "remark": r.remark or "",
                "established_at": r.established_at.strftime("%Y-%m-%d") if r.established_at else "",
                "ended_at": r.ended_at.strftime("%Y-%m-%d") if r.ended_at else None,
                "is_active": r.ended_at is None
            })
        return result
    finally:
        session.close()


def get_bank_account_by_id(account_id: int) -> Optional[Dict[str, Any]]:
    """获取银行账户详情"""
    session = get_session()
    try:
        acc = session.query(BankAccount).get(account_id)
        if not acc: return None
        info = acc.account_info or {}
        return {
            "id": acc.id,
            "owner_type": acc.owner_type,
            "owner_id": acc.owner_id,
            "bank_name": info.get(BankInfoKey.BANK_NAME, ""),
            "account_no": info.get(BankInfoKey.ACCOUNT_NO, ""),
            "is_default": acc.is_default
        }
    finally:
        session.close()

def get_contract_detail(contract_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取合同详情
    
    Args:
        contract_id: 合同ID
    
    Returns:
        合同详情字典，如果不存在则返回None
    """
    session = get_session()
    try:
        contract = session.query(Contract).get(contract_id)
        if not contract:
            return None
        
        return {
            "id": contract.id,
            "contract_number": contract.contract_number or "",
            "type": contract.type or "",
            "status": contract.status or "",
            "parties": contract.parties or {},
            "content": contract.content or {},
            "signed_date": contract.signed_date.strftime("%Y-%m-%d") if contract.signed_date else None,
            "effective_date": contract.effective_date.strftime("%Y-%m-%d") if contract.effective_date else None,
            "expiry_date": contract.expiry_date.strftime("%Y-%m-%d") if contract.expiry_date else None,
            "timestamp": contract.timestamp.strftime("%Y-%m-%d") if contract.timestamp else None
        }
    finally:
        session.close()


def get_system_constants() -> Dict[str, Any]:
    """
    获取全局系统常量速查表
    包含所有业务状态、类型定义及枚举地图
    """
    from logic.constants import VCType, VCStatus, SubjectStatus, CashStatus, BusinessStatus, SKUType, CounterpartType
    return {
        "虚拟合同类型 (VCType)": {k: v for k, v in VCType.__dict__.items() if not k.startswith("__")},
        "虚拟合同状态 (VCStatus)": {k: v for k, v in VCStatus.__dict__.items() if not k.startswith("__")},
        "执行阶段状态 (SubjectStatus)": {k: v for k, v in SubjectStatus.__dict__.items() if not k.startswith("__")},
        "资金流阶段状态 (CashStatus)": {k: v for k, v in CashStatus.__dict__.items() if not k.startswith("__")},
        "业务项目状态 (BusinessStatus)": {k: v for k, v in BusinessStatus.__dict__.items() if not k.startswith("__")},
        "货品/一级分类 (SKUType)": {k: v for k, v in SKUType.__dict__.items() if not k.startswith("__")},
        "交易对手类型 (CounterpartType)": {k: v for k, v in CounterpartType.__dict__.items() if not k.startswith("__")}
    }




