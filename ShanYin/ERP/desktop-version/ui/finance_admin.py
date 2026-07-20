from models import get_session
import streamlit as st
import pandas as pd
from logic.constants import AccountOwnerType, FinancialOpMode, FundNature, FinanceConstants, AccountLevel1, CounterpartType, BankInfoKey
from datetime import datetime
import streamlit_antd_components as sac
from logic.finance import (
    internal_transfer_action, external_fund_action,
    InternalTransferSchema, ExternalFundSchema
)
from logic.finance.queries import (
    get_account_list_for_ui, get_journal_entries_for_ui, get_fund_operation_history_for_ui
)
from logic.master.queries import get_bank_accounts_for_ui

def show_finance_management_page():
    st.markdown("<h1 style='font-size: 24px;'><i class='bi bi-cash-coin'></i> 财务管理</h1>", unsafe_allow_html=True)
    sel_tab = sac.tabs([
        sac.TabsItem('资金往来明细', icon='bank'),
        sac.TabsItem('资金调拨与往来', icon='arrow-left-right'),
        sac.TabsItem('财务凭证', icon='journal-text'),
        sac.TabsItem('会计科目', icon='list-columns'),
    ], align='center', variant='outline', key='finance_admin_tabs')
    
    if sel_tab == '资金往来明细':
        st.markdown("### <i class='bi bi-bank'></i> 银行/往来账户核算表", unsafe_allow_html=True)
        # 使用查询层获取账户余额数据
        accounts_data = get_account_list_for_ui(has_balance_only=True)
        
        if accounts_data:
            bal_data = []
            for a in accounts_data:
                bal_data.append({
                    "科目": a["level1"],
                    "二级核算项目": a["level2"] or "未分类明细",
                    "详细名称": a["full_name"],
                    "余额方向": a["direction_label"],
                    "计算余额": a["display_balance"]
                })
            
            df_bal = pd.DataFrame(bal_data)
            df_bal["当前余额"] = df_bal["计算余额"].apply(lambda x: f"¥{x:,.2f}")
            st.dataframe(df_bal[["科目", "详细名称", "余额方向", "当前余额"]], use_container_width=True)
        else:
            st.info("当前无活动余额数据")

    elif sel_tab == '资金调拨与往来':
        st.markdown("### <i class='bi bi-arrow-left-right'></i> 资金流入流出管理", unsafe_allow_html=True)
        st.markdown("<div style='color: #666; font-size: 14px; margin-bottom: 20px;'>本操作用于记录账户对调、外部增资注入、借款往来或日常行政开支。</div>", unsafe_allow_html=True)
        
        op_mode = st.radio("选择操作模式", FinancialOpMode.ALL_MODES, horizontal=True)
        
        # 使用 master 查询层获取我方账户
        our_accounts = get_bank_accounts_for_ui(owner_type=AccountOwnerType.OURSELVES)
        acc_options = {a["owner_name"]: a["id"] for a in our_accounts}

        if op_mode == FinancialOpMode.INTERNAL_TRANSFER:
            if len(our_accounts) < 2:
                st.warning("执行账户划拨至少需要两个经营账户。")
            else:
                with st.form("internal_transfer_form"):
                    col1, col2 = st.columns(2)
                    from_acc = col1.selectbox("转出账户 (付款方)", list(acc_options.keys()))
                    to_acc = col2.selectbox("转入账户 (收款方)", list(acc_options.keys()), index=1 if len(acc_options)>1 else 0)
                    
                    col3, col4 = st.columns(2)
                    t_amount = col3.number_input("划拨金额", min_value=0.01, step=1000.0)
                    t_date = col4.date_input("操作日期", value=datetime.now())
                    t_desc = st.text_input("备注", placeholder="例如：日常经营资金调拔")
                    
                    if st.form_submit_button("执行划拨", type="primary"):
                        if from_acc == to_acc:
                            st.error("转出与转入账户不能相同")
                        else:
                            session = get_session()
                            try:
                                payload = InternalTransferSchema(
                                    from_acc_id=acc_options[from_acc],
                                    to_acc_id=acc_options[to_acc],
                                    amount=t_amount,
                                    transaction_date=datetime.combine(t_date, datetime.now().time()),
                                    description=t_desc
                                )
                                result = internal_transfer_action(session, payload)
                                if result.success:
                                    st.success(result.message)
                                    st.rerun()
                                else:
                                    st.error(result.error)
                            finally:
                                session.close()

        elif op_mode == FinancialOpMode.EXTERNAL_IN:
            with st.form("ext_in_form"):
                col1, col2 = st.columns(2)
                target_acc = col1.selectbox("公司收款账户", list(acc_options.keys()))
                fund_type = col2.selectbox("资金性质", FundNature.IN_TYPES)
                
                col3, col4 = st.columns(2)
                t_amount = col3.number_input("入金金额", min_value=0.01, step=1000.0)
                t_date = col4.date_input("操作日期", value=datetime.now())
                
                ext_source = st.text_input("外部来源名称", placeholder="例如：股东张三、XX信贷机构")
                t_desc = st.text_input("详细说明")
                
                if st.form_submit_button("确认外部入金", type="primary"):
                    if not ext_source.strip():
                        st.error("请填写“外部来源名称”")
                    else:
                        session = get_session()
                        try:
                            payload = ExternalFundSchema(
                                account_id=acc_options[target_acc],
                                fund_type=fund_type,
                                amount=t_amount,
                                transaction_date=datetime.combine(t_date, datetime.now().time()),
                                external_entity=ext_source.strip(),
                                description=t_desc,
                                is_inbound=True
                            )
                            result = external_fund_action(session, payload)
                            if result.success:
                                st.success(result.message)
                                st.rerun()
                            else:
                                st.error(result.error)
                        finally:
                            session.close()

        elif op_mode == FinancialOpMode.EXTERNAL_OUT:
            with st.form("ext_out_form"):
                col1, col2 = st.columns(2)
                source_acc = col1.selectbox("公司付款账户", list(acc_options.keys()))
                fund_type = col2.selectbox("款项用途", FundNature.OUT_TYPES)
                
                col3, col4 = st.columns(2)
                t_amount = col3.number_input("出金金额", min_value=0.01, step=100.0)
                t_date = col4.date_input("操作日期", value=datetime.now())
                
                ext_dest = st.text_input("外部去向名称", placeholder="例如：XX物业公司、员工王五、银行还款")
                t_desc = st.text_input("详细说明")
                
                if st.form_submit_button("确认外部出金", type="primary"):
                    if not ext_dest.strip():
                        st.error("请填写“外部去向名称”")
                    else:
                        session = get_session()
                        try:
                            payload = ExternalFundSchema(
                                account_id=acc_options[source_acc],
                                fund_type=fund_type,
                                amount=t_amount,
                                transaction_date=datetime.combine(t_date, datetime.now().time()),
                                external_entity=ext_dest.strip(),
                                description=t_desc,
                                is_inbound=False
                            )
                            result = external_fund_action(session, payload)
                            if result.success:
                                st.success(result.message)
                                st.rerun()
                            else:
                                st.error(result.error)
                        finally:
                            session.close()

        st.divider()
        st.markdown("#### <i class='bi bi-clock-history'></i> 资金账户历史流水", unsafe_allow_html=True)
        # 使用查询层获取历史流水
        history = get_fund_operation_history_for_ui()
        if history:
            df_history = pd.DataFrame(history)
            df_history.columns = ["日期", "流水号", "摘要", "金额数值", "总额"]
            st.dataframe(df_history[["日期", "流水号", "摘要", "总额"]], use_container_width=True)
        else:
            st.info("暂无历史流水")

    elif sel_tab == '财务凭证':
        st.markdown("### <i class='bi bi-journal-text'></i> 财务凭证明细 (复式分录)", unsafe_allow_html=True)
        # 使用查询层获取日记账分录
        journals = get_journal_entries_for_ui(limit=200)
        if journals:
            j_data = []
            for j in journals:
                j_data.append({
                    "时间": j["transaction_date"],
                    "凭证号": j["voucher_no"],
                    "会计科目": j["account_name"],
                    "借 (Debit)": j["debit"],
                    "贷 (Credit)": j["credit"],
                    "摘要": j["summary"]
                })
            st.dataframe(pd.DataFrame(j_data), use_container_width=True)
        else:
            st.info("尚无分录记录")

    elif sel_tab == '会计科目':
        st.markdown("### <i class='bi bi-list-columns'></i> 会计科目表", unsafe_allow_html=True)
        # 使用查询层获取科目列表
        accounts = get_account_list_for_ui(has_balance_only=False)
        if accounts:
            acc_data = []
            for a in accounts:
                acc_data.append({
                    "分类": a["category"],
                    "一级科目": a["level1"],
                    "二级科目": a["level2"] or "-",
                    "方向": a["direction"]
                })
            st.dataframe(pd.DataFrame(acc_data), use_container_width=True)
