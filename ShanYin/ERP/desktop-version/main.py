import streamlit as st
st.set_page_config(page_title="闪饮业务管理系统", layout="wide", page_icon="🍹")

import pandas as pd
from models import init_db, get_session
from sqlalchemy import text

# 1. 顶部状态与环境持久化逻辑
if "db_mode" not in st.session_state:
    st.session_state.db_mode = "生产环境"

# 2. 数据库初始化 (先于 UI 渲染，确保 check_db 能拿到正确 engine)
db_uri = 'sqlite:///data/business_system.db' if st.session_state.db_mode == "生产环境" else 'sqlite:///data/test.db'
init_db(db_uri)

# 3. 辅助函数：真实检查数据库连接状态
def check_db_connection():
    try:
        session = get_session()
        # 执行真实查询验证连接并非僵死状态
        session.execute(text("SELECT 1"))
        session.close()
        return True
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return False

# 4. 导入业务页面与逻辑
import streamlit_antd_components as sac
from ui.entry import show_entry_page
from ui.operations import (
    show_business_management_page, 
    show_supply_chain_management_page, 
    show_virtual_contract_page, 
    show_inventory_dashboard_page
)
from ui.finance_logistics import show_logistics_page, show_cash_flow_page
from ui.finance_admin import show_finance_management_page
from ui.dashboard import show_dashboard_page
from logic.time_rules import TimeRuleEngine

# 5. 加载 CSS 样式
with open("style.css", encoding='utf-8') as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 6. 顶部应用页眉 (Header)
header_container = st.container()
with header_container:
    # 布局: [品牌, 留白, 状态与用户]
    c1, c2, c3 = st.columns([4, 5, 3])
    
    with c1:
        st.markdown("""
            <div style='display: flex; align-items: center; gap: 12px; margin-top: 5px;'>
                <div style='background-color: #2ECC71; width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;'>SY</div>
                <div style='font-size: 18px; font-weight: 700; color: #2D3436;'>闪饮管理系统 <span style='font-weight:400; color:#BDC3C7;'>| 控制台</span></div>
            </div>
        """, unsafe_allow_html=True)
    
    with c3:
        is_online = check_db_connection()
        st.markdown(f"""
            <div style='display: flex; align-items: center; gap: 20px; justify-content: flex-end; margin-top: 5px;'>
                <!-- 在线状态紧贴用户头像 -->
                <div class="status-indicator-inline" style="padding: 2px 10px; border:none; background:transparent;">
                    <span class="status-pulse {"online" if is_online else "offline"}"></span>
                    <span style="color: {"#2ECC71" if is_online else "#E74C3C"}; font-size:12px;">{"在线" if is_online else "断开"}</span>
                </div>
                <div style='display: flex; align-items: center; gap: 10px; border-left: 1px solid #EDEDED; padding-left: 20px;'>
                     <div style='width: 32px; height: 32px; border-radius: 50%; background-color: #F1F2F6; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; color: #636E72;'>AD</div>
                     <div style='text-align: right;'>
                        <div style='color: #2D3436; font-size: 11px; font-weight: 600;'>管理员</div>
                        <div style='color: #636E72; font-size: 9px;'>超级中心</div>
                     </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

st.write("---")

# 7. 侧边栏 (Sidebar) 菜单与提醒
with st.sidebar:
    st.markdown(f"""
        <div style='padding: 10px 0; margin-bottom: 0.5rem;'>
            <div style='color: #2ECC71; font-weight: 700; font-size: 18px;'>⚡ 闪饮管理中心</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='font-weight: 600; font-size: 12px; color: #636E72; margin-bottom: 8px;'>⏰ 系统提醒</div>", unsafe_allow_html=True)
    # 使用新的时间规则引擎获取告警
    try:
        engine = TimeRuleEngine()
        result = engine.run(commit=False)  # 不提交，仅检查
        warnings = result.get('warnings', [])
        if warnings:
            for w in warnings:
                level_icon = "🔴" if w['warning_level'] == "红色" else "🟠"
                st.warning(f"{level_icon} {w['target_event']} ({w['related_type']} #{w['related_id']})")
        else:
            st.success("没有待处理的提醒")
    except Exception as e:
        st.info("暂无时间规则提醒")

    st.markdown('<div class="sidebar-section-header">MAIN MENU</div>', unsafe_allow_html=True)
    
    # 使用 streamlit-antd-components 的 Menu 组件替代原有 Button 组
    selected_key = sac.menu([
        sac.MenuItem('运行看板', icon='house-door'),
        sac.MenuItem('业务中心', icon='briefcase', children=[
            sac.MenuItem('业务管理', icon='kanban'),
            sac.MenuItem('供应链管理', icon='box-seam'),
        ]),
        sac.MenuItem('业务运营', icon='rocket', children=[
            sac.MenuItem('虚拟合同', icon='file-text'),
            sac.MenuItem('库存看板', icon='grid'),
        ]),
         sac.MenuItem('业务操作', icon='truck', children=[
            sac.MenuItem('物流管理', icon='truck-front'),
            sac.MenuItem('资金流管理', icon='cash-coin'),
        ]),
        sac.MenuItem('财务管理', icon='bank'),
        sac.MenuItem('信息录入', icon='pencil-square'),
    ], index=0, format_func='title', open_all=True, key='main_sidebar_menu')

    # 检测页面切换并清理临时状态
    if "last_page" not in st.session_state:
        st.session_state.last_page = "运行看板"
    
    if st.session_state.last_page != selected_key:
        prefixes = [
            "trigger_rule_mgr_", "show_proc_confirm_", "show_supply_confirm_", 
            "show_return_confirm_", "show_rule_editor_", "show_mat_proc_confirm",
            "show_stock_proc_confirm", "show_alloc_confirm_",
            "temp_proc_data_", "temp_supply_data_", "temp_return_data_", "temp_mat_proc_data",
            "temp_stock_proc_data", "temp_stock_proc_desc", "temp_alloc_data_", "temp_alloc_desc_",
            "proc_form_", "supply_form_", "edit_rule_mode_", "stock_proc_sc"
        ]
        for k in list(st.session_state.keys()):
            if any(k.startswith(p) for p in prefixes):
                del st.session_state[k]
        st.session_state.last_page = selected_key
        st.rerun()

    st.markdown("---")
    st.markdown('<div class="sidebar-section-header">SYSTEM</div>', unsafe_allow_html=True)

# 8. 全局弹窗触发控制 (响应各页面的 transient triggers)
def handle_global_dialogs():
    session = get_session()
    for key in list(st.session_state.keys()):
        # 1. 规则管理器
        if key.startswith("trigger_rule_mgr_") and isinstance(st.session_state[key], dict):
            from ui.rule_components import rule_manager_dialog
            mgr_data = st.session_state[key]
            rule_manager_dialog(mgr_data['type'], mgr_data['id'], allowed_inherit=mgr_data.get('allowed_inherit'))
            
        # 2. 其它确认弹窗 (由 operations.py 处理的具体业务确认)
        if key.startswith("show_proc_confirm_") and st.session_state[key]:
            from ui.operations import confirm_procurement_dialog
            biz_id = int(key.replace("show_proc_confirm_", ""))
            del st.session_state[key]
            confirm_procurement_dialog(session, biz_id)
            
        if key.startswith("show_supply_confirm_") and st.session_state[key]:
            from ui.operations import confirm_material_supply_dialog
            biz_id = int(key.replace("show_supply_confirm_", ""))
            del st.session_state[key]
            confirm_material_supply_dialog(session, biz_id)
            
        if key.startswith("show_return_confirm_") and st.session_state[key]:
            from ui.operations import confirm_return_dialog
            vc_id = int(key.replace("show_return_confirm_", ""))
            del st.session_state[key]
            confirm_return_dialog(session, vc_id)

        # 3. 规则编辑器触发器
        if key.startswith("show_rule_editor_") and st.session_state[key]:
            from ui.rule_components import rule_editor_dialog
            rule_data = st.session_state[key]
            del st.session_state[key]
            rule_editor_dialog(rule_data['type'], rule_data['id'])

    # 4. 物料采购确认 (特殊 Key 格式)
    if st.session_state.get("show_mat_proc_confirm"):
        from ui.operations import confirm_mat_procurement_dialog
        sc_id = st.session_state.get("mat_proc_sc_id")
        if sc_id:
            del st.session_state["show_mat_proc_confirm"]
            confirm_mat_procurement_dialog(session, sc_id)

    # 5. 库存采购确认
    if st.session_state.get("show_stock_proc_confirm"):
        from ui.operations import confirm_stock_procurement_dialog
        sc_id = st.session_state.get("stock_proc_sc_id")
        if sc_id:
            confirm_stock_procurement_dialog(session, sc_id)

    # 6. 库存拨付确认
    for key in list(st.session_state.keys()):
        if key.startswith("show_alloc_confirm_") and st.session_state[key]:
            from ui.operations import confirm_allocation_dialog
            biz_id = int(key.replace("show_alloc_confirm_", ""))
            confirm_allocation_dialog(session, biz_id)

    session.close()

handle_global_dialogs()

# 9. 页面分发
if selected_key == "运行看板":
    show_dashboard_page()
elif selected_key == "业务管理":
    show_business_management_page()
elif selected_key == "供应链管理":
    show_supply_chain_management_page()
elif selected_key == "虚拟合同":
    show_virtual_contract_page()
elif selected_key == "库存看板":
    show_inventory_dashboard_page()
elif selected_key == "物流管理":
    show_logistics_page()
elif selected_key == "资金流管理":
    show_cash_flow_page()
elif selected_key == "财务管理":
    show_finance_management_page()
elif selected_key == "信息录入":
    show_entry_page()
elif selected_key in ["业务中心", "业务运营", "业务操作"]:
    st.info(f"请选择 {selected_key} 侧边栏菜单下的具体子项")
else:
    show_dashboard_page()
