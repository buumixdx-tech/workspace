from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from api.deps import get_db, verify_api_key, api_success, parse_ids, row_to_dict
from api.middleware.error_handler import raise_not_found_error
from logic.api_queries import list_businesses, get_business
from logic.business import (
    create_business_action, update_business_status_action,
    delete_business_action, advance_business_stage_action,
    CreateBusinessSchema, UpdateBusinessStatusSchema, AdvanceBusinessStageSchema,
)
from logic.addon_business import (
    create_addon_business_action,
    update_addon_business_action,
    deactivate_addon_business_action,
)
from logic.addon_business.queries import (
    get_addon_detail,
    get_business_addons,
    get_active_addons,
)
from logic.addon_business.schemas import CreateAddonSchema, UpdateAddonSchema

router = APIRouter(prefix="/api/v1/business", tags=["业务"], dependencies=[Depends(verify_api_key)])


# ==================== Business CRUD ====================

@router.post("/create", summary="创建业务")
def create_business(payload: CreateBusinessSchema, session: Session = Depends(get_db)):
    return create_business_action(session, payload).model_dump()


@router.post("/update-status", summary="更新业务状态")
def update_business_status(payload: UpdateBusinessStatusSchema, session: Session = Depends(get_db)):
    return update_business_status_action(session, payload).model_dump()


@router.delete("/delete", summary="删除业务")
def delete_business(business_id: int, session: Session = Depends(get_db)):
    return delete_business_action(session, business_id).model_dump()


@router.post("/advance-stage", summary="推进业务阶段")
def advance_business_stage(payload: AdvanceBusinessStageSchema, session: Session = Depends(get_db)):
    return advance_business_stage_action(session, payload).model_dump()


# ==================== Addon Business ====================

@router.post("/addons/create", summary="创建附加业务政策")
def create_addon(payload: CreateAddonSchema, session: Session = Depends(get_db)):
    return create_addon_business_action(session, payload).model_dump()


@router.put("/addons/update", summary="更新附加业务政策")
def update_addon(payload: UpdateAddonSchema, session: Session = Depends(get_db)):
    return update_addon_business_action(session, payload).model_dump()


@router.post("/addons/deactivate", summary="失效附加业务")
def deactivate_addon(addon_id: int, session: Session = Depends(get_db)):
    return deactivate_addon_business_action(session, addon_id).model_dump()


@router.get("/addons/list/{business_id}", summary="查询业务的附加政策列表")
def list_addons(business_id: int, include_expired: bool = False, session: Session = Depends(get_db)):
    addons = get_business_addons(session, business_id, include_expired=include_expired)
    return api_success([row_to_dict(a) for a in addons])


@router.get("/addons/active/{business_id}", summary="查询业务当前生效的附加政策")
def list_active_addons(business_id: int, session: Session = Depends(get_db)):
    addons = get_active_addons(session, business_id)
    return api_success([row_to_dict(a) for a in addons])


@router.get("/addons/detail/{addon_id}", summary="附加政策详情")
def get_addon(addon_id: int, session: Session = Depends(get_db)):
    addon = get_addon_detail(session, addon_id)
    if not addon:
        raise_not_found_error("附加政策", str(addon_id))
    return api_success(row_to_dict(addon))


# ==================== Query Endpoints ====================

@router.get("/list", summary="业务列表")
def get_businesses(
    ids: Optional[str] = None,
    customer_id: Optional[int] = None,
    customer_ids: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    cust_ids = parse_ids(customer_ids) if customer_ids else None
    result = list_businesses(session, ids=id_list, customer_id=customer_id,
                              customer_ids=cust_ids, status=status, date_from=date_from,
                              date_to=date_to, search=search, page=page, size=size)
    return api_success(result)


@router.get("/{bid}", summary="业务详情")
def get_business_detail(bid: int, session: Session = Depends(get_db)):
    data = get_business(session, bid)
    if data is None:
        raise_not_found_error("业务", str(bid))
    return api_success(data)
