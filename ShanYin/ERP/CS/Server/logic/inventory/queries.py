from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import EquipmentInventory, MaterialInventory, SKU, Point

def get_equipment_inventory(session: Session) -> List[Dict[str, Any]]:
    items = session.query(EquipmentInventory).all()
    result = []
    for e in items:
        sku = session.query(SKU).get(e.sku_id)
        point = session.query(Point).get(e.point_id) if e.point_id else None
        result.append({
            "id": e.id,
            "sn": e.sn,
            "sku_name": sku.name if sku else "未知",
            "model": sku.model if sku else "",
            "operational_status": e.operational_status,
            "device_status": e.device_status,
            "point_name": point.name if point else "库存中",
            "deposit_amount": e.deposit_amount,
            "deposit_timestamp": e.deposit_timestamp.strftime("%Y-%m-%d") if e.deposit_timestamp else ""
        })
    return result

def get_material_inventory(session: Session) -> List[Dict[str, Any]]:
    # 新结构：按sku_id分组返回批次列表
    items = session.query(
        MaterialInventory.sku_id,
        func.sum(MaterialInventory.qty).label("total_qty")
    ).group_by(MaterialInventory.sku_id).having(func.sum(MaterialInventory.qty) > 0).all()

    result = []
    for m in items:
        sku = session.query(SKU).get(m.sku_id)
        # 获取该SKU所有批次行
        batches = session.query(MaterialInventory).filter(
            MaterialInventory.sku_id == m.sku_id,
            MaterialInventory.qty > 0
        ).all()

        # 收集点位并查询
        point_ids = set(b.point_id for b in batches if b.point_id)
        point_map = {}
        if point_ids:
            pts = session.query(Point).filter(Point.id.in_(point_ids)).all()
            point_map = {p.id: p.name for p in pts}

        batch_list = []
        for b in batches:
            batch_list.append({
                "batch_no": b.batch_no,
                "point_id": b.point_id,
                "point_name": point_map.get(b.point_id, f"点位{b.point_id}"),
                "qty": b.qty,
                "vc_id": b.latest_purchase_vc_id
            })

        # 从sku.params获取average_price
        avg_price = 0.0
        if sku and sku.params:
            avg_price = float(sku.params.get("average_price", 0.0) or 0)

        result.append({
            "id": m.sku_id,
            "sku_name": sku.name if sku else "未知",
            "total_qty": m.total_qty,
            "average_price": avg_price,
            "batches": batch_list
        })
    return result

def get_inventory_stats(session: Session) -> Dict[str, Any]:
    total_eq = session.query(EquipmentInventory).count()
    # 新结构：统计有库存的SKU数和总数量
    mat_skus = session.query(func.count(func.distinct(MaterialInventory.sku_id))).filter(MaterialInventory.qty > 0).scalar() or 0
    total_mat_qty = session.query(func.sum(MaterialInventory.qty)).filter(MaterialInventory.qty > 0).scalar() or 0
    return {
        "total_equipment": total_eq,
        "material_sku_count": mat_skus,
        "total_material_quantity": total_mat_qty
    }
