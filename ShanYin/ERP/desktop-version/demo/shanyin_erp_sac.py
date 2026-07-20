import streamlit as st
import streamlit_antd_components as sac
import pandas as pd
from datetime import datetime

# 页面基础配置
st.set_page_config(
    page_title="闪饮 ERP v3.0 - UI Demo",
    layout="wide",
    page_icon="🍹",
    initial_sidebar_state="expanded"
)

# 简约现代风格样式注入
st.markdown("""
    <style>
    /* 全局背景色微调 */
    .main { background-color: #f8fafc; }
    
    /* 隐藏 Streamlit 默认页眉 */
    header[data-testid="stHeader"] { background: rgba(255,255,255,0.8); backdrop-filter: blur(10px); }
    
    /* 卡片模拟容器 */
    .stat-card {
        padding: 1.5rem;
        background: white;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* 标题美化 */
    h1, h2, h3 { color: #1e293b !important; font-weight: 700 !important; }
    
    /* 侧边栏整体美化 */
    section[data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e2e8f0;
    }
    </style>
""", unsafe_allow_html=True)

# --- 侧边导航栏 (SAC Menu) ---
with st.sidebar:
    # 模拟 Logo 区
    st.markdown("""
        <div style='display: flex; align-items: center; gap: 12px; margin-bottom: 2rem; padding: 0 10px;'>
            <div style='background: linear-gradient(135deg, #1890ff 0%, #0050b3 100%); width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; border: 1px solid rgba(255,255,255,0.2);'>SY</div>
            <div style='font-size: 1.1rem; font-weight: 800; color: #1e293b;'>闪饮数字中枢 <span style='font-size: 0.7rem; color: #64748b; font-weight: 400;'>v3.0</span></div>
        </div>
    """, unsafe_allow_html=True)
    
    # SAC 多级导航菜单
    menu_item = sac.menu([
        sac.MenuItem('运行看板', icon='house-door-fill', description='实时监控中心'),
        sac.MenuItem('业务链条', icon='stack', children=[
            sac.MenuItem('虚拟合同', icon='file-earmark-text'),
            sac.MenuItem('物流链路', icon='truck'),
            sac.MenuItem('资金结算', icon='currency-dollar'),
        ]),
        sac.MenuItem('库存与供应链', icon='boxes', children=[
            sac.MenuItem('设备库存', icon='pc-display'),
            sac.MenuItem('物料仓储', icon='bag-fill'),
            sac.MenuItem('供应商管理', icon='person-vcard'),
        ]),
        sac.MenuItem('决策分析', icon='graph-up-arrow', children=[
            sac.MenuItem('财务报表', icon='table'),
            sac.MenuItem('ROI 分析', icon='pie-chart'),
        ]),
        sac.MenuItem(type='divider'),
        sac.MenuItem('系统设置', icon='gear-fill', children=[
            sac.MenuItem('时间规则配置', icon='clock-history'),
            sac.MenuItem('用户权限', icon='shield-lock'),
        ]),
    ], key='sac_main_menu', open_all=False, index=0)
    
    # 底部环境标识
    st.write("")
    sac.tags([
        sac.Tag(label='生产环境', color='blue', icon='check-circle-fill'),
        sac.Tag(label='API 联通', color='green', icon='plugin'),
    ], align='center')

# --- 主页面内容分发 ---

# 页面顶栏状态
col_header, col_user = st.columns([4, 1])
with col_user:
    sac.buttons([
        sac.ButtonsItem(icon='bell', color='secondary'),
        sac.ButtonsItem(icon='person-circle', label='管理员', color='primary'),
    ], align='end', variant='link')

if menu_item == '运行看板':
    st.markdown("## 📊 实时运行看板")
    
    # 第一行：数据指标
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.caption("📈 本月成交总额 (GMV)")
        st.markdown("### ¥ 1,482,000")
        st.progress(75, text='完成目标')
        st.markdown('</div>', unsafe_allow_html=True)
        
    with c2:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.caption("🚚 活跃物流单量")
        st.markdown("### 284 <small style='font-size:0.8rem; font-weight:normal; color:#64748b'>单</small>", unsafe_allow_html=True)
        st.progress(45, text='运力负荷')
        st.markdown('</div>', unsafe_allow_html=True)
        
    with c3:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.caption("🏢 在营点位总数")
        st.markdown("### 1,024 <small style='font-size:0.8rem; font-weight:normal; color:#64748b'>个</small>", unsafe_allow_html=True)
        st.progress(92, text='点位在线率')
        st.markdown('</div>', unsafe_allow_html=True)
        
    with c4:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.caption("⚠️ 待处理预警")
        st.markdown("<h3 style='color:#ef4444 !important'>12 <small style='font-size:0.8rem; font-weight:normal; color:#64748b'>条</small></h3>", unsafe_allow_html=True)
        st.progress(10, text='低优先级')
        st.markdown('</div>', unsafe_allow_html=True)

    st.write("")
    
    # 第二行：主要内容区与侧边动态
    left_col, right_col = st.columns([3, 1])
    
    with left_col:
        # SAC 分段器控制视图
        view = sac.segmented(
            items=[
                sac.SegmentedItem(label='业务热度', icon='fire'),
                sac.SegmentedItem(label='资金流向', icon='cash-stack'),
                sac.SegmentedItem(label='异常监控 (3)', icon='exclamation-triangle-fill'),
            ], align='start', size='sm'
        )
        
        # 业务模拟数据表格
        table_data = pd.DataFrame({
            "业务编号": ["VC10294", "VC10301", "VC10305", "VC10308", "VC10312"],
            "客户名称": ["北京市朝阳区经营部", "华南区分销中心", "上海静安仓", "成都核心代理", "杭州旗舰店"],
            "业务类型": ["设备采购", "物料补给", "退货管理", "设备维护", "设备采购"],
            "金额": ["¥24,000", "¥8,500", "-¥1,200", "¥400", "¥12,800"],
            "更新时间": ["10分钟前", "1小时前", "3小时前", "5小时前", "昨日"]
        })
        st.table(table_data)
        
        # 使用 SAC 卡片展示详细信息
        sac.alert(label='节点提醒', description='由于受强冷空气影响，华北地区物流可能延迟 1-2 天。', icon=True, closable=True, color='info')

    with right_col:
        st.markdown("#### ⚡ 快速发起")
        sac.buttons([
            sac.ButtonsItem(label='创建虚拟合同', icon='plus-circle-fill'),
            sac.ButtonsItem(label='录入资金流水', icon='wallet-fill'),
            sac.ButtonsItem(label='导出日运行报表', icon='file-earmark-spreadsheet-fill'),
        ], direction='vertical', align='start', size='sm')
        
        st.write("")
        st.markdown("#### 🕒 时间规则预警")
        # 使用 SAC Result 展示警告
        sac.result(label='押金退还逾期', description='VC #10221 已由系统锁定信号', status='error')
        
        # 简单的进度步骤
        st.write("**最近物流流转**")
        sac.steps(
            items=[
                sac.StepsItem(title='北京顺义仓', description='已出库'),
                sac.StepsItem(title='运输中', description='顺丰速运'),
                sac.StepsItem(title='已签收', status='wait'),
            ], size='sm', direction='vertical'
        )

elif menu_item == '虚拟合同':
    st.markdown("## 📋 虚拟合同管理")
    
    # SAC Tabs 组织内容
    sac.tabs([
        sac.TabsItem(label='执行中', icon='play-circle-fill'),
        sac.TabsItem(label='待审核 (5)', icon='hourglass-split'),
        sac.TabsItem(label='已完成', icon='check-all'),
        sac.TabsItem(label='异常中止', icon='patch-exclamation-fill'),
    ], align='start')
    
    st.info("💡 在这里集成过滤器和复杂的合同生命周期管理界面...")
    
    # 搜索框示例
    c_s1, c_s2 = st.columns([3, 1])
    c_s1.text_input("搜索编号或客户关键词")
    c_s2.selectbox("按负责人筛选", ["全部", "管理员", "财务助理", "物流调度"])
    
    # 展示穿梭框
    st.subheader("批量任务分配")
    sac.transfer(
        items=['合同 #1024', '合同 #1025', '合同 #1026', '合同 #1027', '合同 #1028'],
        label=['待分配池', '已分配至华东区'],
        titles=['数据源', '目标'],
        search=True
    )

elif menu_item == '时间规则配置':
    st.markdown("## ⚙️ 时间规则逻辑定义")
    sac.alert(label='核心逻辑说明', description='时间规则是闪饮 ERP 的自动机核心。它根据业务事件（如签收时间）自动计算后续任务（如 30 天后结算）的截止期。', icon=True)
    
    # 引导步骤
    sac.steps(
        items=[
            sac.StepsItem(title='定义触发事件', description='例如: 物流签收'),
            sac.StepsItem(title='设置时间偏移', description='例如: +30 自然日'),
            sac.StepsItem(title='绑定目标动作', description='例如: 状态转为待结算'),
            sac.StepsItem(title='完成发布', icon='send-check'),
        ], index=1, align='center'
    )
    
    st.write("---")
    st.write("此处可以放置规则编辑器...")

else:
    st.write(f"正在开发中: {menu_item}")
