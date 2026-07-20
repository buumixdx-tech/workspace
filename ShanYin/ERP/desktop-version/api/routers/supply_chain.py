from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from api.deps import get_db, verify_api_key, api_success, parse_ids
from api.middleware.error_handler import raise_not_found_error
from logic.api_queries import list_supply_chains, get_supply_chain
from logic.supply_chain import (
    create_supply_chain_action, update_supply_chain_action, delete_supply_chain_action,
    CreateSupplyChainSchema, UpdateSupplyChainSchema, DeleteSupplyChainSchema,
)

router = APIRouter(prefix="/api/v1/supply-chain", tags=["供应链"], dependencies=[Depends(verify_api_key)])


class CreateSupplyChainRequest(BaseModel):
    sc: CreateSupplyChainSchema
    template_rules: Optional[list] = None


@router.post("/create", summary="创建供应链协议")
def create_supply_chain(req: CreateSupplyChainRequest, session: Session = Depends(get_db)):
    return create_supply_chain_action(session, req.sc, template_rules=req.template_rules).model_dump()


@router.put("/{sc_id}", summary="更新供应链协议")
def update_supply_chain(sc_id: int, payload: UpdateSupplyChainSchema, session: Session = Depends(get_db)):
    if payload.id != sc_id:
        payload.id = sc_id
    return update_supply_chain_action(session, payload).model_dump()


@router.delete("/{sc_id}", summary="删除供应链协议")
def delete_supply_chain(sc_id: int, session: Session = Depends(get_db)):
    return delete_supply_chain_action(session, DeleteSupplyChainSchema(id=sc_id)).model_dump()


# ==================== Query Endpoints ====================

@router.get("/list", summary="供应链列表")
def get_supply_chains(
    ids: Optional[str] = None,
    supplier_id: Optional[int] = None,
    supplier_ids: Optional[str] = None,
    status: Optional[str] = None,
    type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    sup_ids = parse_ids(supplier_ids) if supplier_ids else None
    result = list_supply_chains(session, ids=id_list, supplier_id=supplier_id,
                                 supplier_ids=sup_ids, status=status, type=type,
                                 date_from=date_from, date_to=date_to,
                                 search=search, page=page, size=size)
    return api_success(result)


@router.get("/{sc_id}", summary="供应链详情")
def get_supply_chain_detail(sc_id: int, session: Session = Depends(get_db)):
    data = get_supply_chain(session, sc_id)
    if data is None:
        raise_not_found_error("供应链", str(sc_id))
    return api_success(data)
