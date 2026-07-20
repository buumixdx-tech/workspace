from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from api.deps import get_db, verify_token, api_success, parse_ids
from api.middleware.error_handler import raise_not_found_error
from logic.api_queries import list_vcs, get_vc, list_vcs_for_overview
from logic.services import calculate_cashflow_progress
from logic.vc import (
    create_procurement_vc_action, create_material_supply_vc_action,
    create_return_vc_action, create_mat_procurement_vc_action,
    create_stock_procurement_vc_action, create_inventory_allocation_action,
    update_vc_action, delete_vc_action,
    CreateProcurementVCSchema, CreateMaterialSupplyVCSchema, CreateReturnVCSchema,
    CreateMatProcurementVCSchema, CreateStockProcurementVCSchema, AllocateInventorySchema,
    TimeRuleSchema,
)
from logic.vc.schemas import UpdateVCSchema, DeleteVCSchema

router = APIRouter(prefix="/api/v1/vc", tags=["虚拟合同"], dependencies=[Depends(verify_token)])


class CreateProcurementVCRequest(BaseModel):
    vc: CreateProcurementVCSchema
    draft_rules: Optional[List[TimeRuleSchema]] = None

class CreateMaterialSupplyVCRequest(BaseModel):
    vc: CreateMaterialSupplyVCSchema
    draft_rules: Optional[List[TimeRuleSchema]] = None

class CreateReturnVCRequest(BaseModel):
    vc: CreateReturnVCSchema
    draft_rules: Optional[List[TimeRuleSchema]] = None

class CreateMatProcurementVCRequest(BaseModel):
    vc: CreateMatProcurementVCSchema
    draft_rules: Optional[List[TimeRuleSchema]] = None

class CreateStockProcurementVCRequest(BaseModel):
    vc: CreateStockProcurementVCSchema
    draft_rules: Optional[List[TimeRuleSchema]] = None

class UpdateVCRequest(BaseModel):
    vc_id: int
    description: Optional[str] = None
    elements: Optional[dict] = None
    deposit_info: Optional[dict] = None


@router.post("/create-procurement", summary="创建设备采购执行单")
def create_procurement_vc(req: CreateProcurementVCRequest, session: Session = Depends(get_db)):
    return create_procurement_vc_action(session, req.vc, draft_rules=req.draft_rules).model_dump()


@router.post("/create-material-supply", summary="创建物料供应执行单")
def create_material_supply_vc(req: CreateMaterialSupplyVCRequest, session: Session = Depends(get_db)):
    return create_material_supply_vc_action(session, req.vc, draft_rules=req.draft_rules).model_dump()


class MaterialSupplyProposalRequest(BaseModel):
    business_id: int
    items: List[dict]

@router.post("/material-supply-proposal", summary="物料供应出货提案")
def material_supply_proposal(req: MaterialSupplyProposalRequest, session: Session = Depends(get_db)):
    from logic.services import generate_material_supply_proposal
    return api_success(generate_material_supply_proposal(session, req.business_id, req.items))


@router.post("/create-return", summary="创建退货执行单")
def create_return_vc(req: CreateReturnVCRequest, session: Session = Depends(get_db)):
    return create_return_vc_action(session, req.vc, draft_rules=req.draft_rules).model_dump()


@router.post("/create-mat-procurement", summary="创建物料采购执行单")
def create_mat_procurement_vc(req: CreateMatProcurementVCRequest, session: Session = Depends(get_db)):
    return create_mat_procurement_vc_action(session, req.vc, draft_rules=req.draft_rules).model_dump()


@router.post("/create-stock-procurement", summary="创建库存采购执行单")
def create_stock_procurement_vc(req: CreateStockProcurementVCRequest, session: Session = Depends(get_db)):
    return create_stock_procurement_vc_action(session, req.vc, draft_rules=req.draft_rules).model_dump()


@router.post("/create-allocate-inventory", summary="库存拨付")
def allocate_inventory(payload: AllocateInventorySchema, session: Session = Depends(get_db)):
    return create_inventory_allocation_action(session, payload).model_dump()


@router.put("/update", summary="更新虚拟合同")
def update_vc(req: UpdateVCRequest, session: Session = Depends(get_db)):
    payload = UpdateVCSchema(id=req.vc_id, description=req.description,
                              elements=req.elements, deposit_info=req.deposit_info)
    return update_vc_action(session, payload).model_dump()


@router.delete("/delete", summary="删除虚拟合同")
def delete_vc(vc_id: int, session: Session = Depends(get_db)):
    return delete_vc_action(session, DeleteVCSchema(id=vc_id)).model_dump()


# ==================== Query Endpoints ====================

@router.get("/list", summary="虚拟合同列表")
def get_vcs(
    ids: Optional[str] = None,
    business_id: Optional[int] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    cash_status: Optional[str] = None,
    subject_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    has_logistics: Optional[bool] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    result = list_vcs(session, ids=id_list, business_id=business_id, type=type,
                      status=status, cash_status=cash_status, subject_status=subject_status,
                      date_from=date_from, date_to=date_to, search=search,
                      has_logistics=has_logistics, page=page, size=size)
    return api_success(result)


@router.get("/returnable", summary="可退货的虚拟合同列表")
def get_returnable_vcs_endpoint(
    subject_status: str = "完成,签收",
    session: Session = Depends(get_db)
):
    """获取可退货的虚拟合同（标的已完成或已签收）"""
    from logic.vc.queries import get_returnable_vcs
    subject_statuses = [s.strip() for s in subject_status.split(",")]
    result = get_returnable_vcs(
        vc_types=["设备采购", "库存采购", "物料采购", "物料供应", "库存拨付"],
        statuses=["执行", "完成"],  # 状态为执行或完成都可以退货
        subject_statuses=subject_statuses
    )
    return api_success({"items": result, "total": len(result)})


@router.get("/global", summary="虚拟合同全局概览")
def get_vcs_overview(
    vc_id: Optional[int] = None,
    vc_type: Optional[str] = None,
    vc_status: Optional[str] = None,
    vc_subject_status: Optional[str] = None,
    vc_cash_status: Optional[str] = None,
    business_id: Optional[int] = None,
    business_customer_name_kw: Optional[str] = None,
    supply_chain_id: Optional[int] = None,
    supply_chain_supplier_name_kw: Optional[str] = None,
    sku_id: Optional[int] = None,
    sku_name_kw: Optional[str] = None,
    shipping_point_id: Optional[int] = None,
    shipping_point_name_kw: Optional[str] = None,
    receiving_point_id: Optional[int] = None,
    receiving_point_name_kw: Optional[str] = None,
    tracking_number: Optional[str] = None,
    batch_no: Optional[str] = None,
    vc_date_from: Optional[str] = None,
    vc_date_to: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    result = list_vcs_for_overview(
        session, vc_id=vc_id, vc_type=vc_type, vc_status=vc_status,
        vc_subject_status=vc_subject_status, vc_cash_status=vc_cash_status,
        business_id=business_id, business_customer_name_kw=business_customer_name_kw,
        supply_chain_id=supply_chain_id, supply_chain_supplier_name_kw=supply_chain_supplier_name_kw,
        sku_id=sku_id, sku_name_kw=sku_name_kw,
        shipping_point_id=shipping_point_id, shipping_point_name_kw=shipping_point_name_kw,
        receiving_point_id=receiving_point_id, receiving_point_name_kw=receiving_point_name_kw,
        tracking_number=tracking_number,
        batch_no=batch_no,
        vc_date_from=vc_date_from, vc_date_to=vc_date_to,
        page=page, size=size
    )
    return api_success(result)


@router.get("/{vc_id}", summary="虚拟合同详情")
def get_vc_detail(vc_id: int, session: Session = Depends(get_db)):
    data = get_vc(session, vc_id)
    if data is None:
        raise_not_found_error("虚拟合同", str(vc_id))

    # Enrich deposit_info with computed financial fields
    existing_cfs = data.get("cash_flows") or []
    fin = calculate_cashflow_progress(session, data, existing_cfs)
    existing_di = data.get("deposit_info") or {}
    data["deposit_info"] = {
        **existing_di,
        "total_amount": fin["goods"].get("total") or 0,
        "prepayment_ratio": fin["payment_terms"].get("prepayment_ratio") or 0,
        "expected_deposit": fin["deposit"].get("should") or 0,
        "actual_deposit": fin["deposit"].get("received") or 0,
        "should_receive": fin["deposit"].get("should") or 0,
        "offset_pool": fin["goods"].get("pool") or 0,
        "paid_amount": fin["goods"].get("paid") or 0,
        "balance": fin["goods"].get("balance") or 0,
    }
    return api_success(data)
