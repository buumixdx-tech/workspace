from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
import json
import os
from api.deps import get_db, verify_token, api_success, parse_ids
from api.middleware.error_handler import raise_not_found_error
from logic.api_queries import list_logistics, get_logistics, list_express_orders_global, list_logistics_global
from logic.logistics import (
    create_logistics_plan_action, confirm_inbound_action,
    update_express_order_action, update_express_order_status_action,
    bulk_progress_express_orders_action,
    CreateLogisticsPlanSchema, ConfirmInboundSchema,
    UpdateExpressOrderSchema, ExpressOrderStatusSchema,
    BatchItemSchema,
)
from logic.file_mgmt import save_batch_certificate
from logic.logistics.queries import get_logistics_dashboard_summary

router = APIRouter(prefix="/api/v1/logistics", tags=["物流"], dependencies=[Depends(verify_token)])


@router.post("/create-plan", summary="创建物流发货计划")
def create_logistics_plan(payload: CreateLogisticsPlanSchema, session: Session = Depends(get_db)):
    return create_logistics_plan_action(session, payload).model_dump()


@router.post("/confirm-inbound", summary="确认入库")
def confirm_inbound(payload: ConfirmInboundSchema, session: Session = Depends(get_db)):
    return confirm_inbound_action(session, payload).model_dump()


@router.post("/confirm-inbound-material", summary="物料采购确认入库（含质检报告）")
async def confirm_inbound_material(
    log_id: int = Form(...),
    sn_list: str = Form("[]"),
    batch_items_json: str = Form(..., description="批次明细 JSON 字符串"),
    certificates: List[UploadFile] = File(default=[]),
    created_date: Optional[str] = Form(None, description="业务发生日期 YYYY-MM-DD"),
    session: Session = Depends(get_db)
):
    sn_parsed = json.loads(sn_list)
    batch_items_raw = json.loads(batch_items_json)
    batch_items = [BatchItemSchema(**bi) for bi in batch_items_raw]

    # 构建 certificate_filename → batch_item 索引 的映射（client 传 batch_no 作为 certificate_filename）
    cert_key_to_idx: dict[str, int] = {}
    for idx, bi in enumerate(batch_items):
        if bi.certificate_filename:
            cert_key_to_idx[bi.certificate_filename] = idx

    # 按 certificate_filename 分组保存证书文件
    # cert_paths: batch_item_idx → [saved_path, ...]
    cert_paths: dict[int, list[str]] = {i: [] for i in range(len(batch_items))}
    for cert_file in certificates:
        if not cert_file.filename:
            continue
        fname = os.path.splitext(cert_file.filename)[0]  # client 传的 batch_no
        ext = os.path.splitext(cert_file.filename)[1]
        idx = cert_key_to_idx.get(fname)
        if idx is None:
            continue
        batch_no = fname  # batch_no 就是 certificate_filename
        existing_count = len(cert_paths[idx])
        # 命名：单文件={batch_no}{ext}，多文件={batch_no}_1.ext, {batch_no}_2.ext, ...
        cert_filename = f"{batch_no}_{existing_count + 1}{ext}" if existing_count > 0 else f"{batch_no}{ext}"
        saved_path = save_batch_certificate(cert_filename, cert_file)
        cert_paths[idx].append(saved_path)

    # 将证书路径写回 batch_items
    for idx, bi in enumerate(batch_items):
        paths = cert_paths[idx]
        if paths:
            bi.certificate_filename = json.dumps(paths) if len(paths) > 1 else paths[0]

    from datetime import datetime as dt
    created_date_parsed = dt.strptime(created_date, "%Y-%m-%d").date() if created_date else None
    payload = ConfirmInboundSchema(log_id=log_id, sn_list=sn_parsed, batch_items=batch_items, created_date=created_date_parsed)
    return confirm_inbound_action(session, payload).model_dump()


@router.put("/update-express", summary="更新快递单信息")
def update_express_order(payload: UpdateExpressOrderSchema, session: Session = Depends(get_db)):
    return update_express_order_action(session, payload).model_dump()


@router.post("/update-express-status", summary="更新快递状态")
def update_express_order_status(payload: ExpressOrderStatusSchema, session: Session = Depends(get_db)):
    return update_express_order_status_action(session, payload).model_dump()


class BulkProgressRequest(BaseModel):
    order_ids: List[int]
    target_status: str
    logistics_id: int
    created_date: Optional[date] = None

@router.post("/bulk-progress", summary="批量推进快递状态")
def bulk_progress_express_orders(req: BulkProgressRequest, session: Session = Depends(get_db)):
    return bulk_progress_express_orders_action(
        session, req.order_ids, req.target_status, req.logistics_id, created_date=req.created_date).model_dump()


# ==================== Query Endpoints ====================

@router.get("/list", summary="物流列表")
def get_logistics_list(
    ids: Optional[str] = None,
    vc_id: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tracking_number: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    result = list_logistics(session, ids=id_list, vc_id=vc_id, status=status,
                             date_from=date_from, date_to=date_to,
                             tracking_number=tracking_number, page=page, size=size)
    return api_success(result)


@router.get("/express-orders/global", summary="快递单全局概览")
def get_express_orders_global(
    ids: Optional[int] = None,
    tracking_number: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sku_id: Optional[int] = None,
    sku_name_kw: Optional[str] = None,
    shipping_point_id: Optional[int] = None,
    shipping_point_name_kw: Optional[str] = None,
    receiving_point_id: Optional[int] = None,
    receiving_point_name_kw: Optional[str] = None,
    vc_id: Optional[int] = None,
    vc_type: Optional[str] = None,
    vc_status_type: Optional[str] = None,
    vc_status_value: Optional[str] = None,
    subject_status: Optional[str] = None,
    business_id: Optional[int] = None,
    business_customer_name_kw: Optional[str] = None,
    supply_chain_id: Optional[int] = None,
    supply_chain_supplier_name_kw: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_db)
):
    id_list = [ids] if ids else None
    result = list_express_orders_global(
        session, ids=id_list, tracking_number=tracking_number, status=status,
        date_from=date_from, date_to=date_to,
        sku_id=sku_id, sku_name_kw=sku_name_kw,
        shipping_point_id=shipping_point_id, shipping_point_name_kw=shipping_point_name_kw,
        receiving_point_id=receiving_point_id, receiving_point_name_kw=receiving_point_name_kw,
        vc_id=vc_id, vc_type=vc_type, vc_status_type=vc_status_type, vc_status_value=vc_status_value,
        subject_status=subject_status,
        business_id=business_id, business_customer_name_kw=business_customer_name_kw,
        supply_chain_id=supply_chain_id, supply_chain_supplier_name_kw=supply_chain_supplier_name_kw,
        page=page, size=size
    )
    return api_success(result)


@router.get("/global", summary="物流全局概览")
def get_logistics_global(
    ids: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tracking_number: Optional[str] = None,
    express_order_id: Optional[int] = None,
    sku_id: Optional[int] = None,
    sku_name_kw: Optional[str] = None,
    shipping_point_id: Optional[int] = None,
    shipping_point_name_kw: Optional[str] = None,
    receiving_point_id: Optional[int] = None,
    receiving_point_name_kw: Optional[str] = None,
    vc_id: Optional[int] = None,
    vc_type: Optional[str] = None,
    vc_status_type: Optional[str] = None,
    vc_status_value: Optional[str] = None,
    subject_status: Optional[str] = None,
    business_id: Optional[int] = None,
    business_customer_name_kw: Optional[str] = None,
    supply_chain_id: Optional[int] = None,
    supply_chain_supplier_name_kw: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_db)
):
    id_list = [ids] if ids else None
    result = list_logistics_global(
        session, ids=id_list, status=status,
        date_from=date_from, date_to=date_to,
        tracking_number=tracking_number, express_order_id=express_order_id,
        sku_id=sku_id, sku_name_kw=sku_name_kw,
        shipping_point_id=shipping_point_id, shipping_point_name_kw=shipping_point_name_kw,
        receiving_point_id=receiving_point_id, receiving_point_name_kw=receiving_point_name_kw,
        vc_id=vc_id, vc_type=vc_type, vc_status_type=vc_status_type, vc_status_value=vc_status_value,
        subject_status=subject_status,
        business_id=business_id, business_customer_name_kw=business_customer_name_kw,
        supply_chain_id=supply_chain_id, supply_chain_supplier_name_kw=supply_chain_supplier_name_kw,
        page=page, size=size
    )
    return api_success(result)


@router.get("/dashboard/summary", summary="物流看板统计")
def get_logistics_dash(session: Session = Depends(get_db)):
    """物流看板：各状态数量统计、今日新增。"""
    return api_success(get_logistics_dashboard_summary())


@router.get("/{log_id}", summary="物流详情")
def get_logistics_detail(log_id: int, session: Session = Depends(get_db)):
    data = get_logistics(session, log_id)
    if data is None:
        raise_not_found_error("物流", str(log_id))
    return api_success(data)
