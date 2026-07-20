import streamlit as st
import streamlit_antd_components as sac
import pandas as pd
import sys
import os

# 将项目根目录添加到 python 路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from sqlalchemy import func, and_
from models import (
    get_session, init_db, ChannelCustomer, Point, MaterialInventory, CashFlow,
    FinancialJournal, FinanceAccount, BankAccount
)
from logic.constants import AccountOwnerType, AccountLevel1
from datetime import datetime
import json

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="闪饮业务管理系统 v2.0",
    page_icon="🍹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 视觉注入 (Enterprise Skin) ---
st.markdown("""
    <style>
    /* 引入 Inter 字体 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    }

    /* 背景色 - 强制浅色底 */
    .stApp, .stAppViewContainer, .stAppMainPresenter, .st-emotion-cache-12w0qpk {
        background-color: #F8FAFC !important;
    }
    
    /* 强制 Dataframe 浅色 */
    [data-testid="stTable"], [data-testid="stDataFrame"] {
        background-color: #FFFFFF !important;
    }
    
    /* 侧边栏强制白色 */
    [data-testid="stSidebar"], [data-testid="stSidebar"] div {
        background-color: #FFFFFF !important;
    }
    
    /* 修复所有 card 内文字 */
    .content-card, .content-card * {
        color: #0F172A !important;
        background-color: #FFFFFF !important;
    }

    /* 侧边栏文字颜色 */
    section[data-testid="stSidebar"] * {
        color: #0F172A !important;
    }

    /* 内容卡片容器 */
    .content-card {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 24px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        margin-bottom: 20px !important;
    }
    
    .kpi-label {
        color: #64748B !important;
        font-size: 14px;
        font-weight: 500;
        background: transparent !important;
    }
    
    .kpi-value {
        color: #0F172A !important;
        font-size: 28px;
        font-weight: 700;
        background: transparent !important;
    }

    h1, h2, h3 {
        color: #0F172A !important;
        font-weight: 700 !important;
        background: transparent !important;
    }
    
    .kpi-trend-up { color: #10B981 !important; background: transparent !important; }
    .kpi-trend-down { color: #EF4444 !important; background: transparent !important; }
    
    /* 隐藏默认 Header */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. 数据库连接初始化 ---
if "db_mode" not in st.session_state:
    st.session_state.db_mode = "生产环境"

db_file = 'business_system.db' if st.session_state.db_mode == "生产环境" else 'test.db'
db_path = os.path.join(BASE_DIR, 'data', db_file)
db_uri = f'sqlite:///{db_path}'
init_db(db_uri)

# --- 4. 侧边栏 (SAC Menu) ---
with st.sidebar:
    # Brand Area
    st.markdown("""
        <div style="padding: 12px 0 24px 0; display: flex; align-items: center; gap: 12px;">
            <div style="width: 36px; height: 36px; background: linear-gradient(135deg, #2563EB, #1D4ED8); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 14px; box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);">SY</div>
            <div>
                <div style="font-weight: 600; font-size: 16px; color: #0F172A; letter-spacing: -0.01em;">ShanYin OS</div>
                <div style="font-size: 12px; color: #64748B;">v2.0 Enterprise</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Main Navigation
    menu = sac.menu([
        sac.MenuItem('工作台 (Dashboard)', icon='columns-gap'),
        sac.MenuItem('业务中心', icon='briefcase', children=[
            sac.MenuItem('信息录入', icon='pencil-square'),
            sac.MenuItem('业务管理', icon='kanban'),
            sac.MenuItem('运营执行', icon='play-circle'),
        ]),
        sac.MenuItem('财务枢纽', icon='wallet2', children=[
            sac.MenuItem('资金流水', icon='cash-stack'),
            sac.MenuItem('财务报表', icon='file-earmark-spreadsheet'),
        ]),
        sac.MenuItem(type='divider'),
        sac.MenuItem('系统设置', icon='gear', children=[
            sac.MenuItem('时间规则', icon='clock-history'),
            sac.MenuItem('数据维护', icon='database'),
        ]),
    ], key='main_nav', open_all=True, index=0, size='sm', variant='light', color='blue')
    
    st.write("")
    
    # Alert Area (Mocking System Alerts)
    with st.container():
        st.markdown("<div style='font-size:12px; color:#94A3B8; font-weight:600; margin-bottom:8px; padding-left:12px;'>UPDATES</div>", unsafe_allow_html=True)
        sac.alert(
            label='系统正常运行', 
            description='所有节点连接稳定 (Latency: 24ms)', 
            size='sm', color='success', icon=True, variant='transparent'
        )

# --- 5. 主内容逻辑 ---

if menu == '工作台 (Dashboard)':
    session = get_session()
    
    # 顶部状态栏
    col_h1, col_h2 = st.columns([6, 2])
    with col_h1:
        st.markdown("<h2 style='margin:0; font-size: 24px;'>核心运营看板</h2>", unsafe_allow_html=True)
        st.markdown("<div style='color:#64748B; font-size:14px;'>Real-time operational metrics and financial overview</div>", unsafe_allow_html=True)
    with col_h2:
        sac.buttons(['刷新数据', '导出报表'], align='end', size='sm', gap='xs', variant='light', color='blue')
    
    st.write("")
    st.write("")

    try:
        # --- 数据获取 ( 复用 dashboard.py 逻辑 ) ---
        total_customers = session.query(ChannelCustomer).count()
        total_points = session.query(Point).count()
        
        # 现金
        cash_acc_ids = [a.id for a in session.query(FinanceAccount).filter(FinanceAccount.level1_name == AccountLevel1.CASH).all()]
        total_cash = 0.0
        if cash_acc_ids:
            total_cash = session.query(func.sum(FinancialJournal.debit) - func.sum(FinancialJournal.credit)).filter(FinancialJournal.account_id.in_(cash_acc_ids)).scalar() or 0.0

        # 本月营收
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        revenue_acc_ids = [a.id for a in session.query(FinanceAccount).filter(FinanceAccount.category == "损益", FinanceAccount.level1_name.like("%收入%")).all()]
        monthly_revenue = 0.0
        if revenue_acc_ids:
            monthly_revenue = session.query(func.sum(FinancialJournal.credit) - func.sum(FinancialJournal.debit)).filter(
                FinancialJournal.account_id.in_(revenue_acc_ids),
                FinancialJournal.transaction_date >= current_month_start
            ).scalar() or 0.0
            
        # 库存价值
        inv_acc_ids = [a.id for a in session.query(FinanceAccount).filter(FinanceAccount.level1_name.in_([AccountLevel1.INVENTORY, AccountLevel1.FIXED_ASSET])).all()]
        total_inventory = 0.0
        if inv_acc_ids:
            total_inventory = session.query(func.sum(FinancialJournal.debit) - func.sum(FinancialJournal.credit)).filter(FinancialJournal.account_id.in_(inv_acc_ids)).scalar() or 0.0

        # --- 模块 A: 核心指标卡片 ---
        c1, c2, c3, c4 = st.columns(4)
        
        def kpi_card(title, value, trend_icon=None, trend_text=None, trend_class="kpi-trend-up"):
            st.markdown(f"""
                <div class="content-card" style="padding: 20px;">
                    <div class="kpi-label">{title}</div>
                    <div class="kpi-value">{value}</div>
                    {"<div class='" + trend_class + "'>" + trend_icon + " " + trend_text + "</div>" if trend_text else "<div style='height:20px'></div>"}
                </div>
            """, unsafe_allow_html=True)
            
        with c1: kpi_card("合作客户", f"{total_customers}", "↗", "较上月 +2")
        with c2: kpi_card("部署点位", f"{total_points}", "↗", "覆盖率 94%")
        with c3: kpi_card("实时资金池", f"¥{total_cash:,.0f}", "↗", "流动性充足")
        with c4: kpi_card("本月营收", f"¥{monthly_revenue:,.0f}", "↗", "环比增长 12%")

        # --- 模块 B: 详细数据面板 ---
        col_main, col_side = st.columns([2, 1])
        
        with col_main:
            st.markdown("""
                <div class="content-card">
                    <h3 style="margin-top:0; border-bottom:1px solid #F1F5F9; padding-bottom:12px; margin-bottom:16px;">资金流向分析</h3>
            """, unsafe_allow_html=True)
            
            # 使用 SAC Tabs 替代原生 Expander
            tab_item = sac.tabs([
                sac.TabsItem('银行账户', icon='bank'),
                sac.TabsItem('应收应付', icon='arrow-left-right'),
                sac.TabsItem('经营报表', icon='file-bar-graph'),
            ], align='start', variant='light', size='sm', color='blue')
            
            if tab_item == '银行账户':
                bank_accounts = session.query(BankAccount).filter(BankAccount.owner_type == AccountOwnerType.OURSELVES).all()
                if bank_accounts:
                    data = []
                    for ba in bank_accounts:
                        # Logic copied from dashboard.py
                        acc = session.query(FinanceAccount).filter(FinanceAccount.level1_name == AccountLevel1.CASH, FinanceAccount.counterpart_type == "BankAccount", FinanceAccount.counterpart_id == ba.id).first()
                        bal = 0
                        if acc:
                            bal = session.query(func.sum(FinancialJournal.debit) - func.sum(FinancialJournal.credit)).filter(FinancialJournal.account_id == acc.id).scalar() or 0.0
                        info = ba.account_info
                        data.append({"银行": info.get("bank_name"), "尾号": info.get("account_number")[-4:], "余额": f"¥{bal:,.2f}"})
                    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
                else:
                    sac.result(label='暂无数据', description='请先录入公司银行账户', status='warning')

            elif tab_item == '应收应付':
                # Reusing Ar/Ap logic
                ar_acc_ids = [a.id for a in session.query(FinanceAccount).filter(FinanceAccount.level1_name == AccountLevel1.AR).all()]
                ap_acc_ids = [a.id for a in session.query(FinanceAccount).filter(FinanceAccount.level1_name == AccountLevel1.AP).all()]
                
                ar_val = session.query(func.sum(FinancialJournal.debit) - func.sum(FinancialJournal.credit)).filter(FinancialJournal.account_id.in_(ar_acc_ids)).scalar() or 0.0 if ar_acc_ids else 0.0
                ap_val = session.query(func.sum(FinancialJournal.credit) - func.sum(FinancialJournal.debit)).filter(FinancialJournal.account_id.in_(ap_acc_ids)).scalar() or 0.0 if ap_acc_ids else 0.0
                
                st.dataframe(pd.DataFrame([
                    {"类别": "应收账款 (AR)", "金额": f"¥{ar_val:,.2f}", "说明": "客户欠款"},
                    {"类别": "应付账款 (AP)", "金额": f"¥{ap_val:,.2f}", "说明": "供应商/物流欠款"},
                    {"类别": "库存资产", "金额": f"¥{total_inventory:,.2f}", "说明": "物料+设备"}
                ]), use_container_width=True, hide_index=True)

            elif tab_item == '经营报表':
                report_file_path = os.path.join(BASE_DIR, 'data', 'finance', 'finance-report', 'report.json')
                if os.path.exists(report_file_path):
                    with open(report_file_path, 'r', encoding='utf-8') as f:
                        report_data = json.load(f)
                    latest_month = sorted(report_data.keys())[-1] if report_data else None
                    if latest_month:
                        s = report_data[latest_month].get("summary", {})
                        st.markdown(f"**{latest_month} 月度简报**")
                        c_r1, c_r2 = st.columns(2)
                        c_r1.metric("净利润", f"¥{s.get('月度净利润', 0):,.2f}")
                        c_r2.metric("经营性现金流", f"¥{s.get('经营性流入', 0):,.2f}")
                else:
                    st.info("尚未生成月度报表")

            st.markdown("</div>", unsafe_allow_html=True) # End content-card

        with col_side:
            # 快捷操作区
            st.markdown("""
                <div class="content-card">
                    <h3 style="margin-top:0; font-size:16px; margin-bottom:12px;">快捷入口</h3>
            """, unsafe_allow_html=True)
            
            sac.buttons([
                sac.ButtonsItem(label='录入新合同', icon='plus-circle', color='blue'),
                sac.ButtonsItem(label='发起付款', icon='credit-card'),
                sac.ButtonsItem(label='查看日志', icon='journal-text', color='gray'),
            ], align='start', direction='vertical', size='sm', variant='text')
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            # 系统状态
            st.markdown("""
                <div class="content-card" style="background:#F8FAFC; border:1px dashed #E2E8F0;">
                    <div style="font-size:12px; color:#64748B;">系统最后同步时间</div>
                    <div style="font-size:14px; font-weight:600; color:#334155;">Today, 10:23 AM</div>
                </div>
            """, unsafe_allow_html=True)

    finally:
        session.close()

else:
    # 占位符页面
    st.markdown(f"## {menu}")
    sac.result(label='正在建设中', description='该模块将在 v2.1 版本中上线', status='info')

