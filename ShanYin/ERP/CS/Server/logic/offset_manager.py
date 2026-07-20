from models import CashFlow, VirtualContract, BankAccount, FinancialJournal, FinanceAccount
from logic.constants import CashFlowType, AccountOwnerType, VCType, AccountLevel1, CounterpartType, PartnerRelationType
from sqlalchemy import func
from datetime import datetime

# 最小冲抵金额阈值（单位：元），小于此值则忽略以避免浮点取整损失
# 注意：大量分笔交易此阈值以下的余额会累积成实际资金损失
MIN_OFFSET_THRESHOLD = 0.01

def check_and_split_excess(session, cf):
    """
    此方法在‘预收预付方案’下已被简化。
    现在不再拆分 CashFlow 流水，保持物理流水 1:1。
    具体的溢价剥离逻辑已移动到 finance.py 的会计分录生成阶段。
    这里仅作为一个钩子保留，或执行非破坏性的检查。
    """
    pass

def apply_offset_to_vc(session, vc):
    """
    为新创建的 VC 检查并应用存在的冲抵池余额 (基于会计科目余额)
    """
    # 退货 VC 不自动核销
    if vc.type == VCType.RETURN:
        return

    party_type = None
    party_id = None
    account_level1 = None
    
    if vc.type in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT, VCType.MATERIAL_PROCUREMENT]:
        # 采购：我们作为付款方，寻找我们‘预付’给供应商的余额 (资产类)
        party_type = CounterpartType.SUPPLIER
        account_level1 = AccountLevel1.PREPAYMENT
        if vc.supply_chain_id:
            from models import SupplyChain
            sc = session.query(SupplyChain).get(vc.supply_chain_id)
            if sc: party_id = sc.supplier_id
    else:
        # 供应：我们作为收款方，寻找客户或合作方’预存’在我们这里的余额 (负债类)
        account_level1 = AccountLevel1.PRE_COLLECTION
        party_id = None
        if vc.business_id:
            from models import Business, PartnerRelation
            rels = session.query(PartnerRelation).filter(
                PartnerRelation.owner_type == "business",
                PartnerRelation.owner_id == vc.business_id,
                PartnerRelation.relation_type == PartnerRelationType.PROCUREMENT,
                PartnerRelation.ended_at == None
            ).all()
            if len(rels) == 1:
                party_type = CounterpartType.PARTNER
                party_id = rels[0].partner_id
            else:
                party_type = CounterpartType.CUSTOMER
                biz = session.query(Business).get(vc.business_id)
                if biz: party_id = biz.customer_id

    if not party_id:
        return

    # --- 核心：通过会计分录查询科目余额 ---
    # 找到对应的二级科目
    account = session.query(FinanceAccount).filter(
        FinanceAccount.level1_name == account_level1,
        FinanceAccount.counterpart_type == party_type,
        FinanceAccount.counterpart_id == party_id
    ).first()
    
    if not account:
        return
        
    # 计算余额
    # 预收账款 (负债): 余额 = 贷 - 借
    # 预付账款 (资产): 余额 = 借 - 贷
    debit_sum = session.query(func.sum(FinancialJournal.debit)).filter(FinancialJournal.account_id == account.id).scalar() or 0.0
    credit_sum = session.query(func.sum(FinancialJournal.credit)).filter(FinancialJournal.account_id == account.id).scalar() or 0.0
    
    balance = (credit_sum - debit_sum) if account_level1 == AccountLevel1.PRE_COLLECTION else (debit_sum - credit_sum)
    
    if balance > MIN_OFFSET_THRESHOLD:
        # 尝试冲抵当前 VC
        target_amount = float((vc.elements or {}).get('total_amount', 0))
        if target_amount <= 0: return
        
        # 本合同已支付总额 (含历史冲抵)
        current_paid = session.query(func.sum(CashFlow.amount)).filter(
            CashFlow.virtual_contract_id == vc.id,
            CashFlow.type.in_([CashFlowType.PREPAYMENT, CashFlowType.FULFILLMENT, CashFlowType.OFFSET_PAY])
        ).scalar() or 0.0
        
        still_due = target_amount - current_paid
        if still_due <= 0: return
        
        use_amount = min(balance, still_due)
        
        # 创建一个‘逻辑流水’作为科目结转的载体
        # 冲抵支付不需要物理账号，但为了兼容性保留
        new_cf = CashFlow(
            virtual_contract_id=vc.id,
            type=CashFlowType.OFFSET_PAY,
            amount=use_amount,
            description=f"自动应用冲抵池余额: 结转 {account_level1} 至货款结算",
            transaction_date=datetime.now()
        )
        session.add(new_cf)
        session.flush()

        try:
            # 触发财务模组记录 (它会生成 预收/预付 -> 应收/应付 的对冲分录)
            from logic.finance import finance_module
            finance_module(cash_flow_id=new_cf.id, session=session)

            # 触发 VC 状态机更新
            from logic.state_machine import virtual_contract_state_machine
            virtual_contract_state_machine(vc.id, 'cash_flow', new_cf.id, session=session)
        except Exception:
            session.delete(new_cf)
            session.flush()
            raise
        
        print(f"DEBUG: Applied accounting offset {use_amount} for party {party_id} to VC {vc.id}")
