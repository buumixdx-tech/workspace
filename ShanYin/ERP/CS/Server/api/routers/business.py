from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from api.deps import get_db, verify_token, api_success, parse_ids, row_to_dict
from api.middleware.error_handler import raise_not_found_error
from logic.api_queries import list_businesses, get_business, list_addons_global
from models import Business
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

router = APIRouter(prefix="/api/v1/business", tags=["业务"], dependencies=[Depends(verify_token)])


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


@router.get("/addons/global", summary="附加业务全局列表（跨业务）")
def list_addons_global_endpoint(
    business_id: Optional[int] = None,
    customer_name_kw: Optional[str] = None,
    sku_name_kw: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_db)
):
    result = list_addons_global(
        session,
        business_id=business_id,
        customer_name_kw=customer_name_kw,
        sku_name_kw=sku_name_kw,
        status=status,
        page=page,
        size=size,
    )
    return api_success(result)


# ==================== Query Endpoints ====================

@router.get("/list", summary="业务列表")
def get_businesses(
    ids: Optional[str] = None,
    customer_id: Optional[int] = None,
    customer_ids: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    customer_name_kw: Optional[str] = None,
    sku_name_kw: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    cust_ids = parse_ids(customer_ids) if customer_ids else None
    result = list_businesses(session, ids=id_list, customer_id=customer_id,
                              customer_ids=cust_ids, status=status, date_from=date_from,
                              date_to=date_to, customer_name_kw=customer_name_kw,
                              sku_name_kw=sku_name_kw, page=page, size=size)
    return api_success(result)


@router.get("/{bid}", summary="业务详情")
def get_business_detail(bid: int, session: Session = Depends(get_db)):
    data = get_business(session, bid)
    if data is None:
        raise_not_found_error("业务", str(bid))
    return api_success(data)


@router.get("/{bid}/sku-price-table", summary="业务SKU协议价格表（定价+NEW_SKU addon，addon价格优先）")
def get_business_sku_price_table(bid: int, include_equipment: bool = False, session: Session = Depends(get_db)):
    """
    返回该业务可供应的SKU列表及其协议供货价。
    合并 business.details.pricing 和生效 NEW_SKU addon 的价格，addon 优先。
    默认只返回 type_level1='物料' 的SKU；include_equipment=True 时返回所有类型。
    """
    biz = session.query(Business).get(bid)
    if not biz:
        raise_not_found_error("业务", str(bid))

    # 1. 从 business pricing 获取 SKU 价格
    details = biz.details or {}
    biz_pricing: dict = details.get("pricing", {})

    # 2. 从生效 NEW_SKU addon 获取扩展 SKU 价格（addon 优先）
    from logic.addon_business.queries import get_active_addons
    addons = get_active_addons(session, bid)
    addon_new_skus = {
        a.sku_id: {
            "override_price": a.override_price,
            "override_deposit": a.override_deposit,
        }
        for a in addons
        if a.addon_type == "NEW_SKU" and a.sku_id
    }

    # 3. 合并：addon 覆盖 business pricing
    all_sku_ids = set(biz_pricing.keys()) | set(addon_new_skus.keys())
    if not all_sku_ids:
        return api_success([])

    # 4. 查询 SKU 名称和类型
    from models import SKU
    sku_rows = session.query(SKU).filter(SKU.id.in_(all_sku_ids)).all()
    sku_map = {str(s.id): s for s in sku_rows}

    items = []
    for sku_id in sorted(all_sku_ids, key=lambda x: int(x)):
        sku = sku_map.get(sku_id)
        if not sku:
            continue
        # 只返回物料类型，除非 include_equipment=True
        if not include_equipment and getattr(sku, 'type_level1', None) != '物料':
            continue

        addon_info = addon_new_skus.get(sku_id, {})
        biz_info = biz_pricing.get(sku_id, {})

        items.append({
            "sku_id": int(sku_id),
            "sku_name": sku.name,
            "price": addon_info.get("override_price") if addon_info.get("override_price") is not None else biz_info.get("price", 0),
            "deposit": addon_info.get("override_deposit") if addon_info.get("override_deposit") is not None else biz_info.get("deposit", 0),
            "source": "addon" if addon_info else "business_pricing",
        })

    return api_success(items)
