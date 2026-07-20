from fastapi import APIRouter, Depends, UploadFile, File
from typing import Optional
from sqlalchemy.orm import Session
import os
import shutil
from logic.api_queries import list_cashflows, get_cashflow
from api.deps import get_db, verify_token, api_success, parse_ids
from api.middleware.error_handler import raise_not_found_error
from logic.finance import (
    create_cash_flow_action, internal_transfer_action, external_fund_action,
    CreateCashFlowSchema, InternalTransferSchema, ExternalFundSchema
)
from logic.finance.queries import (
    get_account_list_for_ui, get_journal_entries_for_ui,
    get_fund_operation_history_for_ui, get_bank_account_list_for_ui,
    get_bank_account_by_id as _fin_bank_by_id, get_dashboard_stats,
    get_cash_flow_list_for_ui,
)

router = APIRouter(prefix="/api/v1/finance", tags=["财务"], dependencies=[Depends(verify_token)])


@router.post("/create-cashflow", summary="录入资金流水")
def create_cashflow(payload: CreateCashFlowSchema, session: Session = Depends(get_db)):
    return create_cash_flow_action(session, payload).model_dump()


@router.post("/cashflows/{cf_id}/attachment", summary="上传资金流附件")
async def upload_cashflow_attachment(
    cf_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_db)
):
    """上传银行转账单据附件（图片或PDF），保存到 data/BankTransferForm/CF-{cf_id}.{ext}"""
    # Verify cashflow exists
    cf = get_cashflow(session, cf_id)
    if cf is None:
        raise_not_found_error("资金流", str(cf_id))

    # Validate file type
    content_type = file.content_type or ''
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf']
    if content_type not in allowed_types:
        return {"success": False, "error": {"message": "仅支持 JPG、PNG、GIF、WebP、PDF 格式"}}

    # Determine extension
    ext = content_type.split('/')[-1]
    if ext == 'jpeg':
        ext = 'jpg'

    # Save file
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'BankTransferForm')
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f'CF-{cf_id}.{ext}')

    with open(file_path, 'wb') as f:
        shutil.copyfileobj(file.file, f)

    return {"success": True, "data": {"path": file_path}}


@router.post("/internal-transfer", summary="内部转账")
def internal_transfer(payload: InternalTransferSchema, session: Session = Depends(get_db)):
    return internal_transfer_action(session, payload).model_dump()


@router.post("/external-fund", summary="外部资金出入")
def external_fund(payload: ExternalFundSchema, session: Session = Depends(get_db)):
    return external_fund_action(session, payload).model_dump()


# ==================== Query Endpoints ====================

@router.get("/cashflows/list", summary="资金流列表")
def get_cashflows_list(
    ids: Optional[str] = None,
    vc_id: Optional[int] = None,
    type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    result = list_cashflows(session, ids=id_list, vc_id=vc_id,
                            type=type, date_from=date_from, date_to=date_to,
                            page=page, size=size)
    return api_success(result)


@router.get("/cashflows/global", summary="资金流全局搜索")
def get_cashflows_global(
    ids: Optional[str] = None,
    cf_id: Optional[int] = None,
    vc_id: Optional[int] = None,
    vc_ids: Optional[str] = None,
    type: Optional[str] = None,
    payer_id: Optional[int] = None,
    payee_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    business_ids: Optional[str] = None,
    sc_ids: Optional[str] = None,
    customer_kw: Optional[str] = None,
    supplier_kw: Optional[str] = None,
    payer_name_kw: Optional[str] = None,
    payee_name_kw: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    if cf_id is not None:
        id_list = [cf_id]
    vc_id_list = parse_ids(vc_ids) if vc_ids else None
    business_id_list = parse_ids(business_ids) if business_ids else None
    sc_id_list = parse_ids(sc_ids) if sc_ids else None
    result = list_cashflows(session, ids=id_list, vc_id=vc_id, vc_ids=vc_id_list,
                            type=type, payer_id=payer_id, payee_id=payee_id,
                            date_from=date_from, date_to=date_to,
                            amount_min=amount_min, amount_max=amount_max,
                            business_ids=business_id_list, sc_ids=sc_id_list,
                            customer_kw=customer_kw, supplier_kw=supplier_kw,
                            payer_name_kw=payer_name_kw, payee_name_kw=payee_name_kw,
                            page=page, size=size)
    return api_success(result)


@router.get("/cashflows/{cf_id}", summary="资金流详情")
def get_cashflow_detail(cf_id: int, session: Session = Depends(get_db)):
    data = get_cashflow(session, cf_id)
    if data is None:
        raise_not_found_error("资金流", str(cf_id))
    return api_success(data)


@router.get("/accounts", summary="会计科目列表")
def get_accounts(has_balance_only: bool = True, session: Session = Depends(get_db)):
    """科目余额查询。has_balance_only: 是否只显示有余额的科目。"""
    return api_success(get_account_list_for_ui(has_balance_only=has_balance_only))


@router.get("/journals", summary="日记账分录")
def get_journals(account_id: Optional[int] = None, start_date: Optional[str] = None,
                end_date: Optional[str] = None, voucher_type: Optional[str] = None,
                limit: int = 50, session: Session = Depends(get_db)):
    """凭证分录查询。"""
    return api_success(get_journal_entries_for_ui(
        account_id=account_id, start_date=start_date, end_date=end_date,
        voucher_type=voucher_type, limit=limit))


@router.get("/fund-history", summary="资金划拨历史")
def get_fund_history(limit: int = 50, session: Session = Depends(get_db)):
    """资金划拨/入金/出金历史。"""
    return api_success(get_fund_operation_history_for_ui(limit=limit))


@router.get("/dashboard", summary="财务看板统计")
def get_finance_dashboard(session: Session = Depends(get_db)):
    """财务看板：库存估值、现金、营收、应收应付。"""
    return api_success(get_dashboard_stats())


@router.get("/bank-accounts", summary="银行账户列表")
def get_bank_accounts(session: Session = Depends(get_db)):
    """获取所有银行账户（我方/客户/供应商/合作伙伴）。"""
    return api_success(get_bank_account_list_for_ui())


@router.get("/bank-accounts/{account_id}", summary="银行账户详情")
def get_bank_account_detail(account_id: int, session: Session = Depends(get_db)):
    data = _fin_bank_by_id(account_id)
    if data is None:
        raise_not_found_error("银行账户", str(account_id))
    return api_success(data)
