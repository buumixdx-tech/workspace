from fastapi import APIRouter, Depends
from typing import Optional
from sqlalchemy.orm import Session
from api.deps import get_db, verify_api_key, api_success, parse_ids
from api.middleware.error_handler import raise_not_found_error
from logic.api_queries import list_cashflows, get_cashflow
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

router = APIRouter(prefix="/api/v1/finance", tags=["财务"], dependencies=[Depends(verify_api_key)])


@router.post("/create-cashflow", summary="录入资金流水")
def create_cashflow(payload: CreateCashFlowSchema, session: Session = Depends(get_db)):
    return create_cash_flow_action(session, payload).model_dump()


@router.post("/internal-transfer", summary="内部转账")
def internal_transfer(payload: InternalTransferSchema, session: Session = Depends(get_db)):
    return internal_transfer_action(session, payload).model_dump()


@router.post("/external-fund", summary="外部资金出入")
def external_fund(payload: ExternalFundSchema, session: Session = Depends(get_db)):
    return external_fund_action(session, payload).model_dump()


# ==================== Query Endpoints ====================

@router.get("/cashflows", summary="资金流列表")
def get_cashflows(
    ids: Optional[str] = None,
    vc_id: Optional[int] = None,
    vc_ids: Optional[str] = None,
    type: Optional[str] = None,
    payer_id: Optional[int] = None,
    payee_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    page: int = 1,
    size: int = 50,
    session: Session = Depends(get_db)
):
    id_list = parse_ids(ids)
    vc_id_list = parse_ids(vc_ids) if vc_ids else None
    result = list_cashflows(session, ids=id_list, vc_id=vc_id, vc_ids=vc_id_list,
                            type=type, payer_id=payer_id, payee_id=payee_id,
                            date_from=date_from, date_to=date_to,
                            amount_min=amount_min, amount_max=amount_max, page=page, size=size)
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


@router.get("/bank-accounts", summary="我方银行账户列表")
def get_our_bank_accounts(session: Session = Depends(get_db)):
    """获取所有我方银行账户及其余额。"""
    return api_success(get_bank_account_list_for_ui(owner_type="ourselves"))


@router.get("/bank-accounts/{account_id}", summary="银行账户详情")
def get_bank_account_detail(account_id: int, session: Session = Depends(get_db)):
    data = _fin_bank_by_id(account_id)
    if data is None:
        raise_not_found_error("银行账户", str(account_id))
    return api_success(data)
