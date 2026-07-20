from fastapi import APIRouter, Depends
from typing import Optional
from sqlalchemy.orm import Session
from api.deps import get_db, verify_api_key, api_success, parse_ids
from logic.api_queries import list_equipment, list_material

router = APIRouter(prefix="/api/v1/inventory", tags=["库存"], dependencies=[Depends(verify_api_key)])


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
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    result = list_material(session, sku_id=sku_id, warehouse_point_id=warehouse_point_id,
                            page=page, size=size)
    return api_success(result)
