from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from api.deps import get_db, verify_token, api_success, parse_ids
from api.middleware.error_handler import raise_not_found_error
from logic.api_queries import (
    list_customers, get_customer, suggest_customers,
    list_points, get_point, suggest_points,
    list_suppliers, get_supplier, suggest_suppliers,
    list_skus, get_sku, suggest_skus,
    list_partners, get_partner, suggest_partners,
    list_bank_accounts, get_bank_account, suggest_bank_accounts,
)
from logic.master import (
    create_customer_action, update_customers_action, delete_customers_action,
    create_point_action, update_points_action, delete_points_action,
    create_supplier_action, update_suppliers_action, delete_suppliers_action,
    create_sku_action, update_skus_action, delete_skus_action,
    create_partner_action, update_partners_action, delete_partners_action,
    CustomerSchema, PointSchema, SupplierSchema, SKUSchema, PartnerSchema,
    DeleteMasterDataSchema,
)
from logic.finance import (
    create_bank_account_action, update_bank_accounts_action, delete_bank_accounts_action,
    CreateBankAccountSchema, UpdateBankAccountSchema,
)

router = APIRouter(prefix="/api/v1/master", tags=["主数据"], dependencies=[Depends(verify_token)])


# ==================== Customer ====================

@router.post("/create-customer", summary="创建渠道客户")
def create_customer(payload: CustomerSchema, session: Session = Depends(get_db)):
    return create_customer_action(session, payload).model_dump()


@router.put("/update-customers", summary="批量更新客户")
def update_customers(payloads: List[CustomerSchema], session: Session = Depends(get_db)):
    return update_customers_action(session, payloads).model_dump()


@router.delete("/delete-customers", summary="批量删除客户")
def delete_customers(payloads: List[DeleteMasterDataSchema], session: Session = Depends(get_db)):
    return delete_customers_action(session, payloads).model_dump()


@router.get("/customers", summary="客户列表")
def get_customers(
    ids: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    result = list_customers(session, ids=id_list, search=search, page=page, size=size)
    return api_success(result)


@router.get("/customers/suggest", summary="客户名称自动补全")
def get_customer_suggest(q: str, limit: int = 10, session: Session = Depends(get_db)):
    if not q or len(q) < 1:
        return api_success({"suggestions": []})
    suggestions = suggest_customers(session, q, limit)
    return api_success({"suggestions": suggestions})


@router.get("/customers/{cid}", summary="客户详情")
def get_customer_detail(cid: int, session: Session = Depends(get_db)):
    data = get_customer(session, cid)
    if data is None:
        raise_not_found_error("客户", str(cid))
    return api_success(data)


# ==================== Point ====================

@router.post("/create-point", summary="创建点位/仓库")
def create_point(payload: PointSchema, session: Session = Depends(get_db)):
    return create_point_action(session, payload).model_dump()


@router.put("/update-points", summary="批量更新点位")
def update_points(payloads: List[PointSchema], session: Session = Depends(get_db)):
    return update_points_action(session, payloads).model_dump()


@router.delete("/delete-points", summary="批量删除点位")
def delete_points(payloads: List[DeleteMasterDataSchema], session: Session = Depends(get_db)):
    return delete_points_action(session, payloads).model_dump()


@router.get("/points", summary="点位列表")
def get_points(
    ids: Optional[str] = None,
    customer_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
    type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    result = list_points(session, ids=id_list, customer_id=customer_id,
                         supplier_id=supplier_id, type=type, search=search, page=page, size=size)
    return api_success(result)


@router.get("/points/suggest", summary="点位名称自动补全")
def get_point_suggest(q: str, limit: int = 10, session: Session = Depends(get_db)):
    if not q or len(q) < 1:
        return api_success({"suggestions": []})
    suggestions = suggest_points(session, q, limit)
    return api_success({"suggestions": suggestions})


@router.get("/points/{pid}", summary="点位详情")
def get_point_detail(pid: int, session: Session = Depends(get_db)):
    data = get_point(session, pid)
    if data is None:
        raise_not_found_error("点位", str(pid))
    return api_success(data)


# ==================== Supplier ====================

@router.post("/create-supplier", summary="创建供应商")
def create_supplier(payload: SupplierSchema, session: Session = Depends(get_db)):
    return create_supplier_action(session, payload).model_dump()


@router.put("/update-suppliers", summary="批量更新供应商")
def update_suppliers(payloads: List[SupplierSchema], session: Session = Depends(get_db)):
    return update_suppliers_action(session, payloads).model_dump()


@router.delete("/delete-suppliers", summary="批量删除供应商")
def delete_suppliers(payloads: List[DeleteMasterDataSchema], session: Session = Depends(get_db)):
    return delete_suppliers_action(session, payloads).model_dump()


@router.get("/suppliers", summary="供应商列表")
def get_suppliers(
    ids: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    result = list_suppliers(session, ids=id_list, category=category, search=search, page=page, size=size)
    return api_success(result)


@router.get("/suppliers/suggest", summary="供应商名称自动补全")
def get_supplier_suggest(q: str, category: Optional[str] = None, limit: int = 10, session: Session = Depends(get_db)):
    if not q or len(q) < 1:
        return api_success({"suggestions": []})
    suggestions = suggest_suppliers(session, q, category=category, limit=limit)
    return api_success({"suggestions": suggestions})


@router.get("/suppliers/{sid}", summary="供应商详情")
def get_supplier_detail(sid: int, session: Session = Depends(get_db)):
    data = get_supplier(session, sid)
    if data is None:
        raise_not_found_error("供应商", str(sid))
    return api_success(data)


# ==================== SKU ====================

@router.post("/create-sku", summary="创建SKU")
def create_sku(payload: SKUSchema, session: Session = Depends(get_db)):
    return create_sku_action(session, payload).model_dump()


@router.put("/update-skus", summary="批量更新SKU")
def update_skus(payloads: List[SKUSchema], session: Session = Depends(get_db)):
    return update_skus_action(session, payloads).model_dump()


@router.delete("/delete-skus", summary="批量删除SKU")
def delete_skus(payloads: List[DeleteMasterDataSchema], session: Session = Depends(get_db)):
    return delete_skus_action(session, payloads).model_dump()


@router.get("/skus", summary="SKU列表")
def get_skus(
    ids: Optional[str] = None,
    supplier_id: Optional[int] = None,
    type_level1: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    result = list_skus(session, ids=id_list, supplier_id=supplier_id,
                       type_level1=type_level1, search=search, page=page, size=size)
    return api_success(result)


@router.get("/skus/suggest", summary="SKU名称自动补全")
def get_sku_suggest(q: str, type_level1: Optional[str] = None, limit: int = 10, session: Session = Depends(get_db)):
    if not q or len(q) < 1:
        return api_success({"suggestions": []})
    suggestions = suggest_skus(session, q, type_level1=type_level1, limit=limit)
    return api_success({"suggestions": suggestions})


@router.get("/skus/{sku_id}", summary="SKU详情")
def get_sku_detail(sku_id: int, session: Session = Depends(get_db)):
    data = get_sku(session, sku_id)
    if data is None:
        raise_not_found_error("SKU", str(sku_id))
    return api_success(data)


# ==================== Partner ====================

@router.post("/create-partner", summary="创建外部合作方")
def create_partner(payload: PartnerSchema, session: Session = Depends(get_db)):
    return create_partner_action(session, payload).model_dump()


@router.put("/update-partners", summary="批量更新合作方")
def update_partners(payloads: List[PartnerSchema], session: Session = Depends(get_db)):
    return update_partners_action(session, payloads).model_dump()


@router.delete("/delete-partners", summary="批量删除合作方")
def delete_partners(payloads: List[DeleteMasterDataSchema], session: Session = Depends(get_db)):
    return delete_partners_action(session, payloads).model_dump()


@router.get("/partners", summary="合作方列表")
def get_partners(
    ids: Optional[str] = None,
    type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    result = list_partners(session, ids=id_list, type=type, search=search, page=page, size=size)
    return api_success(result)


@router.get("/partners/suggest", summary="合作方名称自动补全")
def get_partner_suggest(q: str, type: Optional[str] = None, limit: int = 10, session: Session = Depends(get_db)):
    if not q or len(q) < 1:
        return api_success({"suggestions": []})
    suggestions = suggest_partners(session, q, type=type, limit=limit)
    return api_success({"suggestions": suggestions})


@router.get("/partners/{pid}", summary="合作方详情")
def get_partner_detail(pid: int, session: Session = Depends(get_db)):
    data = get_partner(session, pid)
    if data is None:
        raise_not_found_error("合作方", str(pid))
    return api_success(data)


# ==================== Bank Account ====================

@router.post("/create-bank-account", summary="创建银行账户")
def create_bank_account(payload: CreateBankAccountSchema, session: Session = Depends(get_db)):
    return create_bank_account_action(session, payload).model_dump()


@router.put("/update-bank-accounts", summary="批量更新银行账户")
def update_bank_accounts(payloads: List[UpdateBankAccountSchema], session: Session = Depends(get_db)):
    return update_bank_accounts_action(session, payloads).model_dump()


@router.delete("/delete-bank-accounts", summary="批量删除银行账户")
def delete_bank_accounts(payloads: List[DeleteMasterDataSchema], session: Session = Depends(get_db)):
    return delete_bank_accounts_action(session, payloads).model_dump()


@router.get("/bank-accounts", summary="银行账户列表")
def get_bank_accounts(
    ids: Optional[str] = None,
    owner_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    result = list_bank_accounts(session, ids=id_list, owner_type=owner_type,
                                owner_id=owner_id, search=search, page=page, size=size)
    return api_success(result)


@router.get("/bank-accounts/suggest", summary="银行账户自动补全")
def get_bank_account_suggest(q: str, owner_type: Optional[str] = None,
                              owner_id: Optional[int] = None, limit: int = 10,
                              session: Session = Depends(get_db)):
    if not q or len(q) < 1:
        return api_success({"suggestions": []})
    suggestions = suggest_bank_accounts(session, q, owner_type=owner_type,
                                         owner_id=owner_id, limit=limit)
    return api_success({"suggestions": suggestions})


@router.get("/bank-accounts/{account_id}", summary="银行账户详情")
def get_bank_account_detail(account_id: int, session: Session = Depends(get_db)):
    data = get_bank_account(session, account_id)
    if data is None:
        raise_not_found_error("银行账户", str(account_id))
    return api_success(data)
