"""
RSS 管理与监控总入口 (RSS App)
集成监控仪表盘、任务管理、结果查看以及系统控制功能
"""
import streamlit as st
import sqlite3
import json
import os
import pandas as pd
import subprocess
import sys
import time
import signal
import psutil
from datetime import datetime
from config import DB_PATH

# 页面配置
st.set_page_config(
    page_title="RSS 管理控制台",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式
st.markdown("""
<style>
    .stMetric {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
    }
    .stMetric label { color: rgba(255,255,255,0.8) !important; }
    .stMetric [data-testid="stMetricValue"] { color: white !important; }
    .news-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid #667eea;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_queue_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) as count FROM task_queue GROUP BY status")
    stats = {row['status']: row['count'] for row in cursor.fetchall()}
    conn.close()
    return stats

def get_task_list(status_filter=None, limit=1000):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM task_queue"
    params = []
    
    if status_filter and status_filter != "全部":
        query += " WHERE status = ?"
        params.append(status_filter)
        
    query += " ORDER BY created_at DESC"
    
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
        
    cursor.execute(query, tuple(params))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_results_list(limit=50, search_term=None):
    conn = get_connection()
    cursor = conn.cursor()
    if search_term:
        cursor.execute(
            "SELECT * FROM news_results WHERE 标题 LIKE ? OR 综述 LIKE ? ORDER BY processed_at DESC LIMIT ?",
            (f"%{search_term}%", f"%{search_term}%", limit)
        )
    else:
        cursor.execute("SELECT * FROM news_results ORDER BY processed_at DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def reset_task(task_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE task_queue SET status = 'pending', retries = 0 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

# --- Process Management ---
def save_pid(pid):
    if 'engine_pids' not in st.session_state:
        st.session_state.engine_pids = []
    st.session_state.engine_pids.append(pid)

def get_running_pids():
    if 'engine_pids' not in st.session_state:
        st.session_state.engine_pids = []
    
    # Clean up dead PIDs
    active_pids = []
    for pid in st.session_state.engine_pids:
        if psutil.pid_exists(pid):
            try:
                p = psutil.Process(pid)
                if p.status() != psutil.STATUS_ZOMBIE:
                    active_pids.append(pid)
            except:
                pass
    st.session_state.engine_pids = active_pids
    return active_pids

def stop_process():
    pids = get_running_pids()
    killed_count = 0
    for pid in pids:
        try:
            p = psutil.Process(pid)
            p.terminate()
            killed_count += 1
        except Exception as e:
            st.error(f"无法终止进程 {pid}: {e}")
    
    st.session_state.engine_pids = [] # Clear
    return killed_count

def run_script_async(script_name, args=[], silent=False):
    """异步运行脚本"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(base_dir, script_name)
    cmd = [sys.executable, script_path] + args
    
    try:
        # 根据 silent 参数决定是否显示窗口
        # Windows 专用标志
        flags = subprocess.CREATE_NO_WINDOW if silent else subprocess.CREATE_NEW_CONSOLE
        
        process = subprocess.Popen(cmd, creationflags=flags)
        save_pid(process.pid)
        mode_str = "后台" if silent else "窗口"
        return True, f"已以[{mode_str}]模式启动进程 PID: {process.pid}"
    except Exception as e:
        return False, str(e)

def run_script_sync(script_name, args=[]):
    """同步运行脚本并返回结果"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(base_dir, script_name)
    cmd = [sys.executable, script_path] + args
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, f"执行出错:\n{e.stderr}\n{e.stdout}"
    except Exception as e:
        return False, f"未知错误: {str(e)}"

# --- Dialogs ---
@st.dialog("🚀 确认批量处理")
def confirm_batch_dialog(pending_count):
    st.write(f"检测到当前有 **{pending_count}** 条待处理任务。")
    st.write("是否立即启动后台引擎处理所有这些任务？")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("✅ 确认执行", type="primary", use_container_width=True):
            st.info(f"正在启动后台引擎，处理 {pending_count} 条任务...")
            success, msg = run_script_async("news_engine.py", args=["--limit", str(pending_count)])
            if success:
                st.success(f"已启动! {msg}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"启动失败: {msg}")
    with col2:
        if st.button("❌ 取消", use_container_width=True):
            st.rerun()

@st.dialog("📅 选择时间区间")
def date_range_dialog():
    st.write("请选择用于筛选分析结果的日期范围：")
    today = datetime.now().date()
    
    # 从 session_state 获取当前值，默认为今天
    current_val = st.session_state.get('filter_date_range')
    if not current_val or len(current_val) != 2:
        current_val = (today, today)
        
    selected_range = st.date_input("日期范围 (起止日期)", value=current_val)
    
    st.caption("提示：在日历中点击两次分别选择开始和结束日期。")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 确认筛选", type="primary", use_container_width=True):
            if isinstance(selected_range, tuple) and len(selected_range) == 2:
                st.session_state.filter_date_range = selected_range
                st.rerun()
            else:
                st.warning("请选择完整的起止日期")
    with col2:
        if st.button("🗑️ 清除日期", use_container_width=True):
            st.session_state.filter_date_range = None
            st.rerun()

# 侧边栏
st.sidebar.title("📡 RSS 管理控制台")
page = st.sidebar.radio("导航", ["📊 仪表盘", "🕹️ 系统控制", "📥 任务队列", "✅ 处理结果"])

# ==================== 仪表盘 ====================
if page == "📊 仪表盘":
    st.title("📊 仪表盘")
    
    stats = get_queue_stats()
    pending = stats.get('pending', 0)
    processing = stats.get('processing', 0)
    done = stats.get('done', 0)
    error = stats.get('error', 0)
    total = sum(stats.values())
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("总任务数", total)
    col2.metric("待处理", pending, delta=None)
    col3.metric("处理中", processing)
    col4.metric("已完成", done)
    col5.metric("失败", error, delta=None if error == 0 else f"-{error}")
    
    st.divider()
    
    if total > 0:
        progress = done / total
        st.progress(progress, text=f"完成进度: {done}/{total} ({progress*100:.1f}%)")
    
    st.subheader("🕐 最近处理的新闻")
    recent = get_results_list(limit=5)
    for item in recent:
        with st.container():
            timestamp = item.get('processed_at', '')
            st.markdown(f"""
            <div class="news-card">
                <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                    <strong>{item.get('标题', '无标题')}</strong>
                    <span style="color:#666; font-size:0.9em;">{timestamp}</span>
                </div>
                <div style="margin-bottom:8px;">
                    <span style="background:#e3f2fd; color:#1976d2; padding:2px 8px; border-radius:12px; font-size:0.8em;">{item.get('消息类型', '未分类')}</span>
                    <span style="background:#f3e5f5; color:#7b1fa2; padding:2px 8px; border-radius:12px; font-size:0.8em;">{item.get('发布来源', '未知来源')}</span>
                </div>
                <p style="color:#444; font-size:0.95em; line-height:1.5;">{item.get('综述', '')}</p>
            </div>
            """, unsafe_allow_html=True)

# ==================== 系统控制 ====================
elif page == "🕹️ 系统控制":
    st.title("🕹️ 系统控制中心")
    
    # ========== 守护进程管理 ==========
    st.subheader("🔄 守护进程管理")
    st.caption("启动 Engine 和 Pusher 守护进程后，抓取的新闻将自动被处理和推送。")
    
    # 选项：是否静默启动
    is_silent = st.checkbox("🤫 静默启动 (不弹出黑色控制台窗口)", value=False, help="启用后，进程将在后台默默运行。")
    
    daemon_col1, daemon_col2, daemon_col3 = st.columns(3)    
    # 检查当前运行的进程
    running_pids = get_running_pids()
    
    with daemon_col1:
        st.write("**🤖 AI Engine**")
        if st.button("▶️ 启动 Engine", use_container_width=True, key="start_engine"):
            success, msg = run_script_async("news_engine.py", args=["--daemon"], silent=is_silent)
            if success:
                st.success(f"已启动! {msg}")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(f"启动失败: {msg}")
    
    with daemon_col2:
        st.write("**📢 Jami Pusher**")
        if st.button("▶️ 启动 Pusher", use_container_width=True, key="start_pusher"):
            success, msg = run_script_async("jami_pusher.py", args=["--daemon"], silent=is_silent)
            if success:
                st.success(f"已启动! {msg}")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(f"启动失败: {msg}")
    
    with daemon_col3:
        st.write("**⏹️ 停止所有**")
        if running_pids:
            if st.button("🛑 终止所有进程", use_container_width=True, type="primary", key="stop_all"):
                killed = stop_process()
                if killed > 0:
                    st.success(f"已停止 {killed} 个进程")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("未找到可停止的进程")
        else:
            st.button("🛑 终止所有进程", use_container_width=True, disabled=True, key="stop_all_disabled")
    
    # 显示运行状态
    if running_pids:
        st.success(f"✅ 守护进程运行中 (PID: {', '.join(map(str, running_pids))})")
    else:
        st.warning("⚠️ 守护进程未运行。请先启动 Engine 和 Pusher，否则抓取的新闻不会被自动处理。")
    
    st.divider()
    
    # ========== 手动操作区 ==========
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### 📥 抓取新闻")
        st.info("从配置的 RSS 源抓取最新新闻并入库。")
        if st.button("🚀 立即抓取 (RSS Fetcher)", type="primary"):
            with st.spinner("正在抓取 RSS 源..."):
                success, output = run_script_sync("rss_fetcher.py")
                if success:
                    st.success("抓取完成！")
                    with st.expander("查看详细日志", expanded=True):
                        st.code(output, language="text")
                else:
                    st.error("抓取失败")
                    st.code(output, language="text")

    with col2:
        st.write("### 🤖 手动批量处理")
        
        # 统计待处理数量
        stats = get_queue_stats()
        pending_count = stats.get('pending', 0)
        
        if pending_count > 0:
            st.warning(f"当前有 {pending_count} 条待处理任务")
        else:
            st.success("暂无待处理任务")
            
        # 批量处理按钮（传统模式，一次性处理）
        if st.button("⚡ 批量处理 (一次性)", help="启动临时进程处理所有待处理任务"):
            if pending_count > 0:
                confirm_batch_dialog(pending_count)
            else:
                st.warning("当前没有待处理任务")

    st.divider()


# ==================== 任务队列 ====================
elif page == "📥 任务队列":
    st.title("📥 任务队列管理")
    
    # 1. 布局：定义顶部控制栏 (Status | Limit | Refresh | Process | Reset)
    # 使用 container 或直接 columns
    # 注意：按钮需要根据下方表格的选择状态来启用/禁用
    # 因此我们先定义占位符 columns，等获取到 selection 后再填充按钮
    
    # 调整列宽比例以适配按钮
    col_filter, col_limit, col_refresh, col_act1, col_act2 = st.columns([1.2, 0.8, 0.8, 1.2, 1.2], vertical_alignment="bottom")
    
    with col_filter:
        status_filter = st.selectbox("状态筛选", ["全部", "pending", "processing", "done", "error"])
    with col_limit:
        limit_option = st.selectbox("显示数量", [100, 500, 1000, "全部"])
        limit = None if limit_option == "全部" else limit_option
    with col_refresh:
        if st.button("🔄 刷新列表", use_container_width=True):
            st.rerun()
            
    # 2. 获取数据
    tasks = get_task_list(status_filter=status_filter, limit=limit)
    
    if tasks:
        # Prepare DataFrame with a 'Select' column
        df = pd.DataFrame(tasks)
        display_cols = ['id', 'title', 'publisher', 'status', 'retries', 'created_at', 'error_msg']
        df = df[[c for c in display_cols if c in df.columns]]
        df.columns = ['ID', '标题', '发布源', '状态', '重试', '创建时间', '错误信息'][:len(df.columns)]
        
        # Insert Select column at beginning
        df.insert(0, "选择", False)
        
        # 3. 显示表格 (可编辑)
        edited_df = st.data_editor(
            df,
            column_config={
                "选择": st.column_config.CheckboxColumn(
                    "选择",
                    help="选择要操作的任务",
                    default=False,
                )
            },
            disabled=[c for c in df.columns if c != "选择"],
            hide_index=True,
            use_container_width=True,
            key="task_editor_table" # 加 key 保持状态
        )
        
        # 4. 获取选择的 ID
        selected_rows = edited_df[edited_df["选择"]]
        selected_ids = selected_rows["ID"].tolist()
        has_selection = len(selected_ids) > 0
        
        # 5. 回填顶部按钮 (使用之前定义的 columns)
        
        # 按钮 1: 处理选中
        with col_act1:
            # 按钮 label 动态显示数量
            label = f"▶️ 处理选中 ({len(selected_ids)})" if has_selection else "▶️ 处理选中"
            if st.button(label, disabled=not has_selection, use_container_width=True):
                ids_str = ",".join(map(str, selected_ids))
                with st.spinner(f"启动处理..."):
                    success, msg = run_script_async("news_engine.py", args=["--ids", ids_str])
                    if success:
                        st.toast(f"✅ 已启动处理进程! {msg}")
                        # 给点时间让后台启动
                        time.sleep(1)
                    else:
                        st.error(f"启动失败: {msg}")
                        
        # 按钮 2: 重置选中
        with col_act2:
            label = f"🔁 重置状态 ({len(selected_ids)})" if has_selection else "🔁 重置状态"
            if st.button(label, disabled=not has_selection, use_container_width=True):
                count = 0
                for tid in selected_ids:
                    reset_task(tid)
                    count += 1
                st.toast(f"✅ 已重置 {count} 个任务")
                time.sleep(1)
                st.rerun()

    else:
        st.info("暂无任务数据")

# ==================== 处理结果 ====================
elif page == "✅ 处理结果":
    st.title("✅ AI 分析结果")
    
    # 获取所有结果用于构建筛选选项的缓存
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT 发布来源 FROM news_results")
    all_sources = [r[0] for r in cursor.fetchall() if r[0]]
    cursor.execute("SELECT DISTINCT 消息类型 FROM news_results")
    all_types = [r[0] for r in cursor.fetchall() if r[0]]
    conn.close()
    
    with st.expander("🔍 高级筛选", expanded=True):
        col1, col2, col3, col4, col5 = st.columns([1, 1, 0.8, 1.2, 1.2], vertical_alignment="bottom")
        with col1:
            filter_source = st.selectbox("发布来源", ["全部"] + sorted(all_sources))
        with col2:
            filter_type = st.selectbox("消息类型", ["全部"] + sorted(all_types))
        with col3:
            filter_importance = st.selectbox("重要性", ["全部", 5, 4, 3, 2, 1])
        with col4:
            search_query = st.text_input("关键词搜索")
        with col5:
            # 日期区间按钮
            current_dr = st.session_state.get('filter_date_range')
            dr_label = "🗓️ 全部日期"
            if current_dr and len(current_dr) == 2:
                dr_label = f"🗓️ {current_dr[0]} ~ {current_dr[1]}"
            
            if st.button(dr_label, use_container_width=True, help="点击选择日期范围"):
                date_range_dialog()
            
    # 构建查询
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM news_results WHERE 1=1"
    params = []
    
    if filter_source != "全部":
        query += " AND 发布来源 = ?"
        params.append(filter_source)
    if filter_type != "全部":
        query += " AND 消息类型 = ?"
        params.append(filter_type)
    if filter_importance != "全部":
        query += " AND 重要度 = ?"
        params.append(int(filter_importance))
    
    current_date_range = st.session_state.get('filter_date_range')
    if current_date_range and len(current_date_range) == 2:
        # 修改筛选字段为新闻的『发布时间』，使用 DATE() 函数提取日期部分
        query += " AND DATE(发布时间) BETWEEN ? AND ?"
        params.append(str(current_date_range[0]))
        params.append(str(current_date_range[1]))

    if search_query:
        query += " AND (标题 LIKE ? OR 综述 LIKE ?)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
        
    query += " ORDER BY processed_at DESC LIMIT 100"
    
    cursor.execute(query, tuple(params))
    filtered_results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if filtered_results:
        st.caption(f"显示前 {len(filtered_results)} 条匹配结果")
        
        # 使用自定义 CSS 稍微调整一下 Expander 的样式 (可选)
        st.markdown("""
        <style>
        .streamlit-expanderHeader {
            font-size: 1rem;
            color: #333;
        }
        </style>
        """, unsafe_allow_html=True)

        for item in filtered_results:
            # 数据预处理
            time_str = item.get('发布时间', '')[5:16] # MM-DD HH:MM
            news_type = item.get('消息类型', '资讯')
            title = item.get('标题', '无标题')
            summary = item.get('综述', '暂无内容')
            source = item.get('发布来源', 'Unknown')
            link = item.get('原文链接', '#')
            
            try:
                sectors = json.loads(item.get('影响板块', '[]') or '[]')
                sectors_str = " ".join(sectors)
            except:
                sectors_str = ""

            try:
                stocks = json.loads(item.get('直接提到的个股', '[]') or '[]')
            except:
                stocks = []

            # 1. 标题行格式: 时间 | 类型 | 标题
            importance = item.get('重要度', 3)
            header_label = f"{time_str} | {news_type} | {title}"
            
            with st.expander(header_label, expanded=False):
                # 顶部元数据行
                stars = "⭐" * importance
                st.markdown(f"**重要度**: {stars} ({importance}/5) &nbsp; | &nbsp; **发布源**: {source} &nbsp; | &nbsp; [🔗 原文链接]({link})")
                
                st.divider()
                
                # 内容布局: 左侧主要信息，右侧摘要
                # 或者: 上方摘要，下方个股/板块 (更符合阅读顺序)
                
                # 这里采用左右布局：左侧显示板块/个股，右侧显示 AI 综述（因为综述通常较长）
                col_meta, col_summary = st.columns([1, 3])
                
                with col_meta:
                    if sectors_str:
                        st.info(f"**影响板块**\n\n{sectors_str}")
                    
                    if stocks:
                        st.write("**相关个股**")
                        # 罗列最多5个 (一行显示)，使用加粗文本以匹配正文字体大小
                        top_stocks_md = "  ".join([f"**{s}**" for s in stocks[:5]])
                        st.markdown(top_stocks_md)
                        
                        # 超过5个折叠显示
                        if len(stocks) > 5:
                            with st.expander(f"更多 ({len(stocks)-5})"):
                                for s in stocks[5:]:
                                    st.caption(s)
                
                with col_summary:
                    st.success(f"**AI 综述**\n\n{summary}")
    else:
        st.info("没有找到符合条件的结果")

st.sidebar.divider()
st.sidebar.caption("RSS App v2.3 | Power by Streamlit")
