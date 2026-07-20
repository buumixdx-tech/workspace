from models import get_session
from sqlalchemy import func, and_
import streamlit as st
import os
import json
import pandas as pd
from datetime import datetime
from logic.constants import AccountOwnerType, AccountLevel1, BankInfoKey
import streamlit_antd_components as sac
from logic.finance import get_dashboard_stats
import streamlit_antd_components as sac

REPORT_PATH = 'data/finance/finance-report/report.json'

def draw_stat_card(icon_class, value, label, color="#2ECC71"):
    st.markdown(f"""
    <div class="stat-card">
        <div style="display: flex; align-items: center; gap: 20px;">
            <div style="background-color: {color}15; color: {color}; width: 56px; height: 56px; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 26px;">
                <i class="bi {icon_class}"></i>
            </div>
            <div>
                <div class="stat-label">{label}</div>
                <div class="stat-value">{value}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def show_dashboard_page():
    session = get_session()
    
    # 顶部标题栏 + 模式切换 + 刷新按钮
    col_t1, col_t2 = st.columns([7, 3])
    
    try:
        # 强制过期所有对象，确保从数据库读最新数据
        session.expire_all()
        
        # 调用逻辑层获取统计数据
        stats = get_dashboard_stats()
        db_name = stats["db_mode"]

        with col_t1:
            st.markdown(f"""
                <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 20px;'>
                    <i class="bi bi-speedometer2" style="font-size: 24px; color: #2D3436;"></i>
                    <h2 style='margin:0; font-size: 24px;'>运行看板 <span style='font-size:14px; font-weight:normal; color:#636E72; margin-left:10px;'>{db_name} 实时监控中</span></h2>
                </div>
            """, unsafe_allow_html=True)
        
        with col_t2:
            c_mode, c_refresh = st.columns([2, 1])
            with c_mode:
                is_prod = st.toggle(
                    "生产环境数据", 
                    value=(st.session_state.db_mode == "生产环境"),
                    key="dash_env_toggle"
                )
                new_mode = "生产环境" if is_prod else "测试/演示环境"
                if new_mode != st.session_state.db_mode:
                    st.session_state.db_mode = new_mode
                    st.rerun()
            with c_refresh:
                if st.button("🔄 刷新", key="dash_refresh", use_container_width=True):
                    session.expire_all()
                    st.rerun()
        
        # 3. 页面展示渲染
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: draw_stat_card("bi-people", f"{stats['total_customers']}", "服务客户", "#3498DB")
        with c2: draw_stat_card("bi-geo-alt", f"{stats['total_points']}", "点位数量", "#9B59B6")
        with c3: draw_stat_card("bi-box-seam", f"¥{stats['total_inventory_val']:,.2f}", "固定资产及库存", "#E67E22")
        with c4: draw_stat_card("bi-cash-stack", f"¥{stats['total_cash']:,.2f}", "货币资金", "#2ECC71")
        with c5: draw_stat_card("bi-graph-up-arrow", f"¥{stats['monthly_revenue']:,.2f}", "本月营收预估", "#E74C3C")

        # 4. 详细财务分解面板
        st.write("")
        st.markdown("""<div style='margin-bottom: 15px;'>
            <span style='font-weight: 700; font-size: 16px; color: #2D3436;'>
                <i class="bi bi-file-earmark-break" style="margin-right: 8px;"></i>资产负债与流水拆解
            </span>
        </div>""", unsafe_allow_html=True)
        
        detail_tab = sac.tabs([
            sac.TabsItem('银行账户余额', icon='bank'),
            sac.TabsItem('应收应付账款', icon='arrow-left-right'),
        ], variant='light', size='sm', align='start')

        if detail_tab == '银行账户余额':
            if stats['bank_balances']:
                # 将元数据转换为 DataFrame 展示，并格式化金额
                df_bank = pd.DataFrame(stats['bank_balances'])
                df_bank["当前余额"] = df_bank["当前余额"].map(lambda x: f"¥{x:,.2f}")
                st.dataframe(df_bank, use_container_width=True, hide_index=True)
            else:
                st.info("尚未录入银行账户信息")

        else:
            summary_data = {
                "项目类别": ["应收账款 (AR)", "应付账款 (AP)", "存货资产 (INV)"],
                "金额": [f"¥{stats['total_ar']:,.2f}", f"¥{stats['total_ap']:,.2f}", f"¥{stats['total_inventory_val']:,.2f}"],
                "业务说明": ["客户待结清余额", "供应商/三方待付余额", "在途/在库物品价值"]
            }
            st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

    finally:
        session.close()

    st.write("---")
    
    if os.path.exists(REPORT_PATH):
        with open(REPORT_PATH, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        # 显示月度汇总
        st.markdown("""<div style='margin: 20px 0 15px 0;'>
            <span style='font-weight: 700; font-size: 16px; color: #2D3436;'>
                <i class="bi bi-calendar3" style="margin-right: 8px;"></i>经营月度财务概览
            </span>
        </div>""", unsafe_allow_html=True)
        
        col_r1, col_r2 = st.columns([5, 1])
        with col_r2:
            from logic.finance import rebuild_report
            if st.button("🏗️ 重建月报", key="rebuild_dash_report", use_container_width=True):
                rebuild_report()
                st.rerun()

        for month, data in report_data.items():
            with st.expander(f"📊 {month} 月度经营简报"):
                s = data.get("summary", {})
                
                # A. 损益概览
                st.markdown("##### 收益与利润 (损益表)")
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("主营营收", f"¥{s.get(AccountLevel1.REVENUE, 0):,.2f}")
                p2.metric("主营成本", f"¥{s.get(AccountLevel1.COST, 0):,.2f}", delta=f"-{s.get(AccountLevel1.COST, 0):,.2f}", delta_color="inverse")
                p3.metric("管理费用", f"¥{s.get(AccountLevel1.EXPENSE, 0):,.2f}", delta=f"-{s.get(AccountLevel1.EXPENSE, 0):,.2f}", delta_color="inverse")
                p4.metric("月度净利润", f"¥{s.get('月度净利润', 0):,.2f}", delta=f"{s.get('月度净利润', 0):,.2f}")
                
                # B. 现金流概览
                st.markdown("##### 现金流向 (现金流量表)")
                cf1, cf2, cf3, cf4 = st.columns(4)
                cf1.metric("经营性流入", f"¥{s.get('经营性流入', 0):,.2f}")
                cf2.metric("筹资性流入", f"¥{s.get('借贷/注资流入', 0):,.2f}")
                cf3.metric("月度总支出", f"¥{s.get('所有支出', 0):,.2f}", delta_color="normal")
                cf4.metric("期末现金头寸", f"¥{s.get('现金净流量', 0):,.2f}")
                
                # C. 详细凭证追溯
                st.markdown("---")
                if st.checkbox("查看当月记账凭证明细", key=f"v_show_{month}"):
                    vouchers = data.get("vouchers", [])
                    if vouchers:
                        v_data = []
                        for v in vouchers:
                            v_data.append({
                                "凭证号": v["voucher_no"],
                                "业务类型": v["ref_type"],
                                "摘要": v["entries"][0]["summary"] if v["entries"] else "-"
                            })
                        st.table(pd.DataFrame(v_data))
    else:
        st.info("尚无自动生成的财务月报，请通过业务操作产生流水。")
        from logic.finance import rebuild_report
        if st.button("🏗️ 尝试从现有凭证重建报表"):
            rebuild_report()
            st.rerun()

    st.divider()
    st.markdown("""<div style='display: flex; align-items: center; gap: 8px; color: #2ECC71;'>
        <i class="bi bi-check-circle-fill"></i>
        <span style='font-size: 14px; font-weight: 600;'>系统运行状态：数据链路已接通，系统实时监控中。</span>
    </div>""", unsafe_allow_html=True)
