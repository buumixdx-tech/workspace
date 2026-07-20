import streamlit as st
import streamlit_antd_components as sac

# --- 页面配置 ---
st.set_page_config(
    page_title="SAC Visual Laboratory",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 3. 视觉注入策略 (From Design Guidelines) ---
st.markdown("""
    <style>
    /* 1. 引入现代字体 Inter */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    }

    /* 2. 强制背景色为专业灰 */
    .stApp {
        background-color: #F5F7FA;
    }
    
    /* 3. 隐藏默认的彩色 Header */
    header[data-testid="stHeader"] {
        display: none;
    }

    /* 4. 侧边栏精细化 - 纯白背景 + 极细右边框 */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E4E4E7; /* Zinc-200 */
        box-shadow: none;
    }
    
    /* 5. 主内容区模块卡片化 */
    .content-card {
        background: #FFFFFF;
        border: 1px solid #E4E4E7;
        border-radius: 8px;
        padding: 24px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        margin-bottom: 24px;
    }
    
    /* 标题样式微调 */
    h1, h2, h3 {
        color: #18181b; /* Zinc-900 */
        font-weight: 600;
        letter-spacing: -0.02em;
    }
    
    /* 修正 Streamlit 原生组件的边框颜色以匹配 SAC */
    .stTextInput input, .stSelectbox select {
        border-color: #E4E4E7;
    }
    </style>
""", unsafe_allow_html=True)

# --- 侧边栏多级导航 (SAC Menu) ---
with st.sidebar:
    # 模拟 Brand 区域
    st.markdown("""
        <div style="padding: 10px 5px; margin-bottom: 20px; display: flex; align-items: center; gap: 10px;">
            <div style="width: 32px; height: 32px; background: #2563EB; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">SY</div>
            <div style="font-weight: 600; font-size: 16px; color: #1e293b;">Design System</div>
        </div>
    """, unsafe_allow_html=True)

    menu_selection = sac.menu([
        sac.MenuItem('概览 (Overview)', icon='display'),
        sac.MenuItem('导航 (Navigation)', icon='compass', children=[
            sac.MenuItem('Steps 步骤条', icon='check-circle'),
            sac.MenuItem('Tabs 标签页', icon='filter-square'),
            sac.MenuItem('Segmented 分段', icon='segmented-nav'),
        ]),
        sac.MenuItem('录入 (Entry)', icon='input-cursor-text', children=[
            sac.MenuItem('Switch & Checkbox', icon='ui-checks-grid'),
            sac.MenuItem('Rate 评分', icon='star'),
            sac.MenuItem('Transfer 穿梭框', icon='arrow-left-right'),
        ]),
        sac.MenuItem('通用 (General)', icon='gear', children=[
            sac.MenuItem('Buttons 按钮', icon='hand-index-thumb'),
            sac.MenuItem('Alert & Result', icon='exclamation-circle'),
        ]),
    ], key='gallery_menu', open_all=True, index=0)
    
    st.write("")
    sac.alert(label='Version 3.0.1', size='sm', color='secondary', icon=True)

# --- 主内容渲染 ---

def card_container(title, content_func):
    """辅助函数：渲染统一风格的卡片容器"""
    st.markdown(f"""
        <div class="content-card">
            <h3 style="margin-top: 0; margin-bottom: 20px; font-size: 18px;">{title}</h3>
            <!-- Streamlit Content Placeholder -->
    """, unsafe_allow_html=True)
    content_func()
    st.markdown("</div>", unsafe_allow_html=True)

st.title(f"🎨 {menu_selection}")
st.write("---")

if menu_selection == '概览 (Overview)':
    st.markdown("""
    <div class="content-card">
        <h3>Design Principles Validation</h3>
        <p style="color: #64748b; margin-bottom: 20px;">
            This demo validates the "Enterprise-Grade" UI guidelines. 
            Notice the specific background color, the clean sidebar, and the card-based layout.
        </p>
        <div style="display: flex; gap: 16px;">
            <div style="flex: 1; padding: 16px; background: #eff6ff; border-radius: 6px; color: #1e40af; border: 1px solid #dbeafe;">
                <strong>Utility-First</strong><br>
                High density info
            </div>
            <div style="flex: 1; padding: 16px; background: #f0fdf4; border-radius: 6px; color: #166534; border: 1px solid #dcfce7;">
                <strong>Subtle UI</strong><br>
                Low noise borders
            </div>
            <div style="flex: 1; padding: 16px; background: #fef2f2; border-radius: 6px; color: #991b1b; border: 1px solid #fee2e2;">
                <strong>Clear Status</strong><br>
                Semantic colors
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

elif menu_selection == 'Steps 步骤条':
    def render_steps():
        st.write("**水平步骤 (Horizontal)**")
        sac.steps(
            items=[
                # 使用 Dict 格式最稳健
                {'title': '已下单', 'description': '2024-01-01'},
                {'title': '处理中', 'description': '仓库备货'},
                {'title': '待发货'},
            ], index=1
        )
        st.write("---")
        st.write("**带图标 (With Icons)**")
        sac.steps(
            items=[
                {'title': 'Login', 'icon': 'person'},
                {'title': 'Verify', 'icon': 'shield-lock'},
                {'title': 'Done', 'icon': 'check'},
            ], index=1, color='indigo'
        )
    
    card_container("Process Visualization", render_steps)

elif menu_selection == 'Tabs 标签页':
    def render_tabs():
        st.write("**基础标签页**")
        sac.tabs([
            sac.TabsItem(label='概览', icon='house'),
            sac.TabsItem(label='详情', icon='file-text'),
            sac.TabsItem(label='设置', icon='gear'),
        ], align='start')
        
        st.write("**居中胶囊 (Center Pills)**")
        sac.tabs([
            sac.TabsItem(label='Apple', icon='apple'),
            sac.TabsItem(label='Android', icon='android'),
        ], align='center', variant='outline') # 尝试 outline，如果不兼容 pills
    
    card_container("Tabbed Navigation", render_tabs)

elif menu_selection == 'Segmented 分段':
    def render_segmented():
        st.write("**视图切换器**")
        sac.segmented(
            items=[
                {'label': 'Daily', 'icon': 'calendar-day'},
                {'label': 'Weekly', 'icon': 'calendar-week'},
                {'label': 'Monthly', 'icon': 'calendar-month'},
            ], align='start'
        )
    card_container("View Control", render_segmented)

elif menu_selection == 'Switch & Checkbox':
    def render_inputs():
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Switch 开关**")
            sac.switch(label='开启通知', value=True, align='start')
            sac.switch(label='暗黑模式', value=False, align='start', size='sm')
        with c2:
            st.write("**Checkbox 多选**")
            sac.checkbox(
                items=['Admin', 'Editor', 'Viewer'],
                label='选择权限',
                align='start'
            )
    card_container("Interactive Inputs", render_inputs)

elif menu_selection == 'Rate 评分':
    def render_rate():
        st.write("**服务评分**")
        # 必须加 half=True 才能支持小数
        sac.rate(label='综合满意度', value=3.5, half=True, align='start')
        sac.rate(label='物流速度', value=5, align='start', color='orange')
    card_container("Feedback Inputs", render_rate)

elif menu_selection == 'Transfer 穿梭框':
    def render_transfer():
        st.write("**复杂数据调拨**")
        sac.transfer(
            items=['Item A', 'Item B', 'Item C', 'Item D'],
            label=['待选池', '已选池'],
            search=True,
            width='100%'
        )
    card_container("Data Transfer", render_transfer)

elif menu_selection == 'Buttons 按钮':
    def render_buttons():
        st.write("**操作按钮组**")
        # 基础按钮
        sac.buttons(['Save', 'Cancel'], align='start')
        # 状态按钮 (使用通用颜色名)
        sac.buttons(
            items=[
                sac.ButtonsItem(label='Publish', color='green'),
                sac.ButtonsItem(label='Delete', color='red'),
                sac.ButtonsItem(label='Export', color='blue'),
            ], align='start'
        )
    card_container("Action Buttons", render_buttons)

elif menu_selection == 'Alert & Result':
    def render_feedback():
        sac.alert(
            label='Operation Successful', 
            description='The data has been synchronized to the cloud.',
            color='success', icon=True
        )
        st.write("")
        sac.result(
            label='403 Forbidden', 
            description='You do not have permission to access this resource.', 
            status='error'
        )
    card_container("System Feedback", render_feedback)
