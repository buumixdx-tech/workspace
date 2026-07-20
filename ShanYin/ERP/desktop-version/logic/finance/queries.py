"""
财务领域 - UI专用查询层

本模块提供财务相关的UI查询函数，返回格式化字典供UI层直接使用。
遵循CQRS模式，只处理读操作，不涉及写操作。
"""

from typing import List, Dict, Optional, Any
from sqlalchemy import func, cast, String
from models import (
    get_session, FinanceAccount, FinancialJournal, BankAccount,
    CashFlow, VirtualContract, ChannelCustomer, Supplier,
    Point, EquipmentInventory, MaterialInventory, SKU, ExternalPartner
)
from logic.constants import (
    CashFlowType, AccountOwnerType, BankInfoKey, FinanceConstants,
    AccountLevel1, OperationalStatus
)


# ============================================================================
# 1. 会计科目相关查询
# ============================================================================

def get_account_list_for_ui(
    status: Optional[str] = None,
    has_balance_only: bool = True,
    limit: int = 200
) -> List[Dict[str, Any]]:
    """
    获取会计科目列表（专用于UI展示）
    
    Args:
        status: 状态过滤（如 active, inactive）
        has_balance_only: 是否只返回有余额的科目
        limit: 返回数量限制
    
    Returns:
        包含格式化信息的科目列表
    """
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        query = session.query(FinanceAccount)
        
        # models.py 中 FinanceAccount 没有 status 字段，移除过滤
        accounts = query.order_by(FinanceAccount.level1_name, FinanceAccount.level2_name).limit(limit).all()
        
        result = []
        for acc in accounts:
            # 计算科目余额 (这里保持 N+1 因为是标量聚合，通常比加载所有分录快且 models 没关系)
            # 但我们可以优化：如果只需要有发生额的科目
            # 先简单实现
            balance = _calculate_account_balance(session, acc.id)
            
            # 如果要求只显示有余额的科目，且余额为0，则跳过
            if has_balance_only and balance == 0:
                continue
            
            # 获取对手方信息
            counterparty = _get_account_counterparty_info(session, acc)
            
            # UI 展示用的计算余额 (根据方向)
            display_bal = balance
            if acc.direction == "Credit":
                display_bal = -balance

            result.append({
                "id": acc.id,
                "level1": acc.level1_name,
                "level2": acc.level2_name,
                "category": acc.category,
                "direction": acc.direction,
                "direction_label": "借" if acc.direction == "Debit" else "贷",
                "balance": balance,
                "display_balance": display_bal,
                "balance_formatted": f"¥{abs(display_bal):,.2f}",
                "counterparty": counterparty,
                "full_name": f"{acc.level1_name} - {acc.level2_name}" if acc.level2_name else acc.level1_name
            })
        
        return result
    finally:
        session.close()


def get_journal_entries_for_ui(
    account_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    voucher_type: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    获取日记账分录（专用于UI展示）
    
    Args:
        account_id: 科目ID过滤
        start_date: 开始日期（格式：YYYY-MM-DD）
        end_date: 结束日期（格式：YYYY-MM-DD）
        voucher_type: 凭证类型过滤
        limit: 返回数量限制
    
    Returns:
        格式化后的分录列表
    """
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        query = session.query(FinancialJournal).options(joinedload(FinancialJournal.account))
        
        if account_id:
            query = query.filter(FinancialJournal.account_id == account_id)
        
        if start_date:
            query = query.filter(FinancialJournal.transaction_date >= start_date)
        
        if end_date:
            query = query.filter(FinancialJournal.transaction_date <= end_date)
        
        if voucher_type:
            query = query.filter(FinancialJournal.voucher_no.like(f"%{voucher_type}%"))
        
        entries = query.order_by(FinancialJournal.transaction_date.desc(), FinancialJournal.id.desc()).limit(limit).all()
        
        result = []
        for entry in entries:
            acc = entry.account
            acc_name = f"{acc.level1_name}"
            if acc and acc.level2_name:
                acc_name += f" - {acc.level2_name}"
            
            result.append({
                "id": entry.id,
                "voucher_no": entry.voucher_no,
                "transaction_date": entry.transaction_date.strftime("%Y-%m-%d %H:%M"),
                "account_id": entry.account_id,
                "account_name": acc_name,
                "debit": entry.debit,
                "credit": entry.credit,
                "summary": entry.summary,
                "ref_type": entry.ref_type,
                "ref_id": entry.ref_id,
                "formatted_amount": f"¥{max(entry.debit, entry.credit):,.2f}",
                "direction": "借" if entry.debit > 0 else "贷"
            })
        
        return result
    finally:
        session.close()


def get_fund_operation_history_for_ui(limit: int = 50) -> List[Dict[str, Any]]:
    """
    获取资金划拨/入金/出金的历史流水（专用于UI展示）
    """
    session = get_session()
    try:
        # 查找特定前缀的凭证
        query = session.query(FinancialJournal).filter(
            FinancialJournal.voucher_no.like(f"{FinanceConstants.VOUCHER_PREFIX_TRANSFER}%") | 
            FinancialJournal.voucher_no.like(f"{FinanceConstants.VOUCHER_PREFIX_EXT_IN}%") |
            FinancialJournal.voucher_no.like(f"{FinanceConstants.VOUCHER_PREFIX_EXT_OUT}%")
        ).order_by(FinancialJournal.transaction_date.desc(), FinancialJournal.id.desc())
        
        logs = query.all() # 通常这类操作不多，可以全取后在内存中按 voucher_no 去重，或者使用 distinct (sqlite 不支持对特定列 distinct)
        
        result = []
        seen_vouchers = set()
        for l in logs:
            if l.voucher_no not in seen_vouchers:
                result.append({
                    "date": l.transaction_date.strftime("%Y-%m-%d"),
                    "voucher_no": l.voucher_no,
                    "summary": l.summary,
                    "amount": max(l.debit, l.credit),
                    "amount_formatted": f"¥{max(l.debit, l.credit):,.2f}"
                })
                seen_vouchers.add(l.voucher_no)
                if len(result) >= limit:
                    break
        
        return result
    finally:
        session.close()


# ============================================================================
# 2. 银行账户相关查询
# ============================================================================

def get_bank_account_list_for_ui(
    owner_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    is_default: Optional[bool] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    获取银行账户列表（专用于UI选择）
    """
    session = get_session()
    try:
        query = session.query(BankAccount)
        
        if owner_type:
            query = query.filter(BankAccount.owner_type == owner_type)
        if owner_id is not None:
            query = query.filter(BankAccount.owner_id == owner_id)
        if is_default is not None:
            query = query.filter(BankAccount.is_default == is_default)
            
        accounts = query.limit(limit).all()
        
        result = []
        for acc in accounts:
            info = acc.account_info or {}
            result.append({
                "id": acc.id,
                "owner_type": acc.owner_type,
                "owner_id": acc.owner_id,
                "owner_name": _get_account_owner_name(session, acc),
                "bank_name": info.get(BankInfoKey.BANK_NAME, '未知银行'),
                "account_no": info.get(BankInfoKey.ACCOUNT_NO, '****'),
                "is_default": acc.is_default,
                "status": "active",
                "account_info": info
            })
        return result
    finally:
        session.close()


def get_bank_account_by_id(account_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取银行账户详情
    """
    session = get_session()
    try:
        acc = session.query(BankAccount).get(account_id)
        if not acc:
            return None
        info = acc.account_info or {}
        return {
            "id": acc.id,
            "owner_type": acc.owner_type,
            "owner_id": acc.owner_id,
            "owner_name": _get_account_owner_name(session, acc),
            "bank_name": info.get(BankInfoKey.BANK_NAME, '未知银行'),
            "account_no": info.get(BankInfoKey.ACCOUNT_NO, '****'),
            "is_default": acc.is_default,
            "status": acc.status,
            "account_info": info
        }
    finally:
        session.close()


# ============================================================================
# 3. 资金流相关查询
# ============================================================================

def get_cash_flow_list_for_ui(
    vc_id: Optional[int] = None,
    cf_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    获取资金流列表（专用于UI展示）
    
    Args:
        vc_id: 虚拟合同ID过滤
        cf_type: 资金类型过滤
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回数量限制
    
    Returns:
        格式化后的资金流列表
    """
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        query = session.query(CashFlow).options(
            joinedload(CashFlow.virtual_contract),
            joinedload(CashFlow.payer_account),
            joinedload(CashFlow.payee_account)
        )
        
        if vc_id:
            query = query.filter(CashFlow.virtual_contract_id == vc_id)
        
        if cf_type:
            query = query.filter(CashFlow.type == cf_type)
        
        if start_date:
            query = query.filter(CashFlow.transaction_date >= start_date)
        
        if end_date:
            query = query.filter(CashFlow.transaction_date <= end_date)
        
        flows = query.order_by(CashFlow.transaction_date.desc()).limit(limit).all()
        
        # 批量获取所有者名称，消除 N+1
        # 1. 收集所有相关的账户和所有者 ID
        accounts = []
        for cf in flows:
            if cf.payer_account: accounts.append(cf.payer_account)
            if cf.payee_account: accounts.append(cf.payee_account)
        
        customer_ids = list(set(a.owner_id for a in accounts if a.owner_type == AccountOwnerType.CUSTOMER))
        supplier_ids = list(set(a.owner_id for a in accounts if a.owner_type == AccountOwnerType.SUPPLIER))
        
        customer_names = {c.id: c.name for c in session.query(ChannelCustomer).filter(ChannelCustomer.id.in_(customer_ids)).all()} if customer_ids else {}
        supplier_names = {s.id: s.name for s in session.query(Supplier).filter(Supplier.id.in_(supplier_ids)).all()} if supplier_ids else {}
        
        def _get_owner_name_local(acc):
            if not acc: return "[未知]"
            if acc.owner_type == AccountOwnerType.CUSTOMER:
                return f"[客户] {customer_names.get(acc.owner_id, '未知')}"
            if acc.owner_type == AccountOwnerType.SUPPLIER:
                return f"[供应商] {supplier_names.get(acc.owner_id, '未知')}"
            if acc.owner_type == AccountOwnerType.OURSELVES:
                return "[我方] 闪饮业务中心"
            return "[未知]"

        def _get_acc_info_local(acc):
            if not acc:
                return {"label": "未指定/现金", "type": "未知", "bank": "-", "account": "-"}
            info = acc.account_info or {}
            bank_name = info.get(BankInfoKey.BANK_NAME, '未知银行')
            acc_no = str(info.get(BankInfoKey.ACCOUNT_NO) or '****')
            short_no = f"*{acc_no[-4:]}" if len(acc_no) >= 4 else acc_no
            owner_name = _get_owner_name_local(acc)
            return {
                "label": f"{owner_name} - {bank_name} ({short_no})",
                "type": acc.owner_type,
                "bank": bank_name,
                "account": acc_no,
                "owner": owner_name
            }

        result = []
        for cf in flows:
            # 获取虚拟合同信息
            vc = cf.virtual_contract
            
            # 获取收付款账户信息
            payer_info = _get_acc_info_local(cf.payer_account)
            payee_info = _get_acc_info_local(cf.payee_account)
            
            result.append({
                "id": cf.id,
                "vc_id": cf.virtual_contract_id,
                "vc_description": vc.description if vc else "N/A",
                "type": cf.type,
                "type_label": _get_cash_flow_type_label(cf.type),
                "amount": cf.amount,
                "amount_formatted": f"¥{cf.amount:,.2f}",
                "payer_info": payer_info,
                "payee_info": payee_info,
                "transaction_date": cf.transaction_date.strftime("%Y-%m-%d") if cf.transaction_date else "",
                "description": cf.description or "",
                "created_at": cf.timestamp.strftime("%Y-%m-%d %H:%M") if cf.timestamp else ""
            })
        
        return result
    finally:
        session.close()


# ============================================================================
# 4. 私有辅助函数
# ============================================================================

def _calculate_account_balance(session, account_id: int) -> float:
    """计算科目余额"""
    result = session.query(
        func.sum(FinancialJournal.debit) - func.sum(FinancialJournal.credit)
    ).filter(FinancialJournal.account_id == account_id).scalar()
    return result or 0.0


def _get_account_counterparty_info(session, account) -> Optional[Dict[str, Any]]:
    """获取科目对手方信息"""
    if not account.counterpart_type or not account.counterpart_id:
        return None
    
    if account.counterpart_type == 'customer':
        obj = session.query(ChannelCustomer).get(account.counterpart_id)
        if obj:
            return {"type": "客户", "name": obj.name}
    elif account.counterpart_type == 'supplier':
        obj = session.query(Supplier).get(account.counterpart_id)
        if obj:
            return {"type": "供应商", "name": obj.name}
    elif account.counterpart_type == 'partner':
        obj = session.query(ExternalPartner).get(account.counterpart_id)
        if obj:
            return {"type": "合作伙伴", "name": obj.name}

    return None


def _get_account_owner_name(session, account) -> str:
    """获取账户所有者名称"""
    owner_type = account.owner_type
    owner_id = account.owner_id
    
    if owner_type == AccountOwnerType.CUSTOMER:
        obj = session.query(ChannelCustomer).get(owner_id)
        return f"[客户] {obj.name}" if obj else "[客户] 未知"
    elif owner_type == AccountOwnerType.SUPPLIER:
        obj = session.query(Supplier).get(owner_id)
        return f"[供应商] {obj.name}" if obj else "[供应商] 未知"
    elif owner_type == AccountOwnerType.OURSELVES:
        return "[我方] 闪饮业务中心"
    else:
        return "[未知]"


def _get_cash_flow_account_info(session, account) -> Dict[str, Any]:
    """获取资金流账户信息"""
    if not account:
        return {"label": "未指定/现金", "type": "未知", "bank": "-", "account": "-"}
    
    info = account.account_info or {}
    bank_name = info.get(BankInfoKey.BANK_NAME, '未知银行')
    acc_no = str(info.get(BankInfoKey.ACCOUNT_NO) or '****')
    short_no = f"*{acc_no[-4:]}" if len(acc_no) >= 4 else acc_no
    
    owner_name = _get_account_owner_name(session, account)
    
    return {
        "label": f"{bank_name} ({short_no}) - {owner_name}",
        "type": owner_name.split(']')[0] + "]",
        "bank": bank_name,
        "account": short_no
    }


def _get_status_label(status: Optional[str]) -> str:
    """获取状态中文标签"""
    from logic.constants import FinanceAccountStatus
    status_map = {
        FinanceAccountStatus.ACTIVE: "正常",
        FinanceAccountStatus.INACTIVE: "停用",
        FinanceAccountStatus.FROZEN: "冻结",
        "active": "正常",
        "inactive": "停用",
        "frozen": "冻结",
    }
    return status_map.get(status, status or "未知")


def _get_cash_flow_type_label(cf_type: str) -> str:
    """获取资金流类型中文标签"""
    type_map = {
        CashFlowType.PREPAYMENT: "预付款",
        CashFlowType.FULFILLMENT: "履约款",
        CashFlowType.DEPOSIT: "押金",
        CashFlowType.RETURN_DEPOSIT: "退押金",
        CashFlowType.REFUND: "退款",
        CashFlowType.PENALTY: "违约金",
        CashFlowType.OFFSET_IN: "冲抵入账",
        CashFlowType.OFFSET_PAY: "冲抵支付",
    }
    return type_map.get(cf_type, cf_type)


def get_dashboard_stats() -> Dict[str, Any]:
    """
    获取运行看板统计数据 (核心逻辑)
    """
    from datetime import datetime
    
    session = get_session()
    # 1. 基础维度统计
    total_customers = session.query(ChannelCustomer).count()
    total_points = session.query(Point).count()
    
    # 2. 库存资产估算
    # 设备资产 (按押金估算，若无则为0)
    total_equip_val = session.query(func.sum(EquipmentInventory.deposit_amount)).scalar() or 0.0
    # 物料资产 (余额 * 均价)：新结构按批次统计
    total_mat_val = 0.0
    batches = session.query(MaterialInventory).filter(MaterialInventory.qty > 0).all()
    sku_ids = set(b.sku_id for b in batches if b.sku_id)
    sku_avg_prices = {}
    if sku_ids:
        skus = session.query(SKU).filter(SKU.id.in_(sku_ids)).all()
        for s in skus:
            sku_avg_prices[s.id] = float(s.params.get("average_price", 0.0) or 0) if s.params else 0
    for b in batches:
        avg_price = sku_avg_prices.get(b.sku_id, 0)
        total_mat_val += (b.qty or 0) * avg_price
    
    total_inventory_val = total_equip_val + total_mat_val
    
    # 3. 货币资金统计
    bank_balances = []
    total_cash = 0.0
    accounts = session.query(BankAccount).filter(BankAccount.owner_type == AccountOwnerType.OURSELVES).all()
    for acc in accounts:
        info = acc.account_info or {}
        bal = info.get("balance", 0.0)
        total_cash += bal
        bank_name = info.get(BankInfoKey.BANK_NAME, "未知银行")
        acc_no = str(info.get(BankInfoKey.ACCOUNT_NO, ""))[-4:]
        bank_balances.append({
            "账户": f"{bank_name} (*{acc_no})",
            "当前余额": bal
        })
        
    # 4. 营收预估 (本月)
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # 查找主营业务收入科目
    revenue_acc_ids = session.query(FinanceAccount.id).filter(FinanceAccount.level1_name == AccountLevel1.REVENUE).all()
    rev_ids = [r[0] for r in revenue_acc_ids]
    
    monthly_revenue = 0.0
    if rev_ids:
        # 贷方发生额表示收入增加
        monthly_revenue = session.query(func.sum(FinancialJournal.credit - FinancialJournal.debit)).filter(
            FinancialJournal.account_id.in_(rev_ids),
            FinancialJournal.transaction_date >= month_start
        ).scalar() or 0.0
        
    # 5. 应收应付统计
    def _compute_level1_balance(l1_name):
        acc_ids = session.query(FinanceAccount.id).filter(FinanceAccount.level1_name == l1_name).all()
        ids = [r[0] for r in acc_ids]
        if not ids: return 0.0
        # 借方 - 贷方 (资产类)
        return session.query(func.sum(FinancialJournal.debit - FinancialJournal.credit)).filter(
            FinancialJournal.account_id.in_(ids)
        ).scalar() or 0.0

    total_ar = _compute_level1_balance(AccountLevel1.AR)
    # 应付是负债，贷方 - 借方
    total_ap = -_compute_level1_balance(AccountLevel1.AP)
    
    # 6. 确定数据库模式
    db_url = str(session.bind.url)
    db_mode = "生产环境" if "production" in db_url.lower() or "prod" in db_url.lower() else "测试/演示环境"
    
    res = {
        "db_mode": db_mode,
        "total_customers": total_customers,
        "total_points": total_points,
        "total_inventory_val": total_inventory_val,
        "total_cash": total_cash,
        "monthly_revenue": monthly_revenue,
        "bank_balances": bank_balances,
        "total_ar": total_ar,
        "total_ap": total_ap
    }
    session.close()
    return res
