from fastapi import APIRouter, Depends
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from api.deps import get_db, verify_token, api_success, parse_ids
from logic.api_queries import list_equipment, list_material
from models import MaterialInventory, SKU as SKUModel, Point as PointModel

router = APIRouter(prefix="/api/v1/inventory", tags=["库存"], dependencies=[Depends(verify_token)])


@router.get("/equipment", summary="设备库存列表")
def get_equipment(
    vc_id: Optional[int] = None,
    point_id: Optional[int] = None,
    sku_id: Optional[int] = None,
    operational_status: Optional[str] = None,
    device_status: Optional[str] = None,
    sn: Optional[str] = None,
    deposit_amount_min: Optional[float] = None,
    deposit_amount_max: Optional[float] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    result = list_equipment(session, vc_id=vc_id, point_id=point_id, sku_id=sku_id,
                             operational_status=operational_status, device_status=device_status,
                             sn=sn, deposit_amount_min=deposit_amount_min,
                             deposit_amount_max=deposit_amount_max, page=page, size=size)
    return api_success(result)


@router.get("/material", summary="物料库存列表")
def get_material(
    sku_id: Optional[int] = None,
    warehouse_point_id: Optional[int] = None,
    batch_no: Optional[str] = None,
    production_date_from: Optional[str] = None,
    production_date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    result = list_material(session, sku_id=sku_id, warehouse_point_id=warehouse_point_id,
                            batch_no=batch_no, production_date_from=production_date_from,
                            production_date_to=production_date_to, status=status,
                            page=page, size=size)
    return api_success(result)


@router.get("/material-skus-with-stock", summary="查询有库存的物料SKU")
def get_material_skus_with_stock(session: Session = Depends(get_db)):
    """返回所有有可用库存（qty > 0）的物料 SKU 列表。"""
    items = session.query(
        func.count(MaterialInventory.id).label('batch_count'),
        func.sum(MaterialInventory.qty).label('total_qty'),
        MaterialInventory.sku_id,
        SKUModel.name.label('sku_name')
    ).join(SKUModel, MaterialInventory.sku_id == SKUModel.id
    ).filter(
        MaterialInventory.qty > 0
    ).group_by(MaterialInventory.sku_id, SKUModel.name).all()
    return api_success([{
        "sku_id": i.sku_id,
        "sku_name": i.sku_name,
        "batch_count": i.batch_count,
        "total_qty": float(i.total_qty or 0)
    } for i in items])


@router.get("/material-batches", summary="查询 SKU 可用批次（按仓库+批次）")
def get_material_batches(sku_id: int, session: Session = Depends(get_db)):
    """返回指定 SKU 下所有有库存的批次（warehouse_point + batch_no）。"""
    items = session.query(MaterialInventory).filter(
        MaterialInventory.sku_id == sku_id,
        MaterialInventory.qty > 0
    ).all()
    # 关联 SKU 和 Point
    s_ids = list(set(i.sku_id for i in items if i.sku_id))
    p_ids = list(set(i.point_id for i in items if i.point_id))
    sku_map = {s.id: s for s in session.query(SKUModel).filter(SKUModel.id.in_(s_ids)).all()} if s_ids else {}
    pt_map = {p.id: p for p in session.query(PointModel).filter(PointModel.id.in_(p_ids)).all()} if p_ids else {}
    result = []
    for b in items:
        sku = sku_map.get(b.sku_id)
        pt = pt_map.get(b.point_id)
        avg_price = float(sku.params.get("average_price", 0.0)) if sku and sku.params else 0.0
        result.append({
            "inventory_id": b.id,
            "batch_no": b.batch_no,
            "warehouse_point_id": b.point_id,
            "warehouse_point_name": pt.name if pt else f"点位{b.point_id}",
            "quantity": b.qty,
            "average_price": avg_price,
            "production_date": b.production_date,
            "display": f"{pt.name if pt else '点位'} - {b.batch_no} ({b.qty}件)"
        })
    return api_success(result)
