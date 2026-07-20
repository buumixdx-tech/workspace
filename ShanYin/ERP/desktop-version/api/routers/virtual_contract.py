from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from api.deps import get_db, verify_api_key, api_success, parse_ids
from api.middleware.error_handler import raise_not_found_error
from logic.api_queries import list_vcs, get_vc
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

router = APIRouter(prefix="/api/v1/vc", tags=["虚拟合同"], dependencies=[Depends(verify_api_key)])


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


@router.post("/allocate-inventory", summary="库存拨付")
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
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    result = list_vcs(session, ids=id_list, business_id=business_id, type=type,
                      status=status, cash_status=cash_status, subject_status=subject_status,
                      date_from=date_from, date_to=date_to, search=search, page=page, size=size)
    return api_success(result)


@router.get("/{vc_id}", summary="虚拟合同详情")
def get_vc_detail(vc_id: int, session: Session = Depends(get_db)):
    data = get_vc(session, vc_id)
    if data is None:
        raise_not_found_error("虚拟合同", str(vc_id))
    return api_success(data)
