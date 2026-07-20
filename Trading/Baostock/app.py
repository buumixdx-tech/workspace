import streamlit as st
import pandas as pd
import os
import toml
import time
import logging
from datetime import datetime, date, timedelta
import plotly.graph_objects as go
import sys

# Silence Streamlit's scriptrunner warnings
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").setLevel(logging.ERROR)

# Add src to path
# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import New Architecture Components
from src.storage.ck_client import ck_client
from src.storage.data_loader import get_price
from backtest.engine import BacktestEngine
from analysis.strategies.topology_swing import TopologySwingStrategy
from analysis.strategy import TradeSignalGenerator, SimulationState
from src.analysis.topology_trend import TopologicalTrendIdentifier


# Import ETL components for UI triggers
from src.etl import etl_calendar
from src.etl import etl_factors
from src.config_loader import CK_HOST, get_clickhouse_config

# ==============================================================================
# CACHED DATA LOADING FUNCTIONS
# 这些函数使用 Streamlit 缓存来避免每次页面刷新都重新查询 ClickHouse
# ==============================================================================

@st.cache_data(ttl=300, show_spinner=False)  # 缓存5分钟
def get_dashboard_stats():
    """获取仪表盘统计数据（缓存5分钟）"""
    try:
        # 使用更快的 SQL 优化查询
        # 1. 个股 K线统计 - 使用物化视图如果有的话，或者优化查询
        res_stock = ck_client.query_df("""
            SELECT 
                count() as cnt, 
                max(date) as last_dt 
            FROM stock_data.stock_kline_day
        """)
        stock_cnt = res_stock['cnt'].iloc[0] if not res_stock.empty else 0
        stock_last = res_stock['last_dt'].iloc[0] if not res_stock.empty else 'N/A'
        
        # 2. 指数 K线行数
        res_idx = ck_client.query_df("SELECT count() as cnt FROM stock_data.index_kline_day")
        idx_cnt = res_idx['cnt'].iloc[0] if not res_idx.empty else 0
        
        # 3. 当前上市A股数量 (小表，查询快)
        res_sec = ck_client.query_df("""
            SELECT count() as cnt 
            FROM stock_data.securities_info 
            WHERE type=1 AND out_date = '2999-12-31'
        """)
        sec_cnt = res_sec['cnt'].iloc[0] if not res_sec.empty else 0
        
        return {
            'stock_cnt': stock_cnt,
            'stock_last': stock_last,
            'idx_cnt': idx_cnt,
            'sec_cnt': sec_cnt,
            'error': None
        }
    except Exception as e:
        return {
            'stock_cnt': 0, 'stock_last': 'N/A', 'idx_cnt': 0, 'sec_cnt': 0,
            'error': str(e)
        }

@st.cache_data(ttl=300, show_spinner=False)  # 缓存5分钟
def get_warehouse_status():
    """获取数据仓库状态（缓存5分钟）"""
    try:
        # 最新行情日期和更新时间
        last_kline = ck_client.query_df("""
            SELECT max(date) as dt, max(update_time) as ut 
            FROM stock_data.stock_kline_day
        """)
        last_date = last_kline['dt'].iloc[0] if not last_kline.empty else 'N/A'
        last_update = last_kline['ut'].iloc[0] if not last_kline.empty else 'N/A'
        
        # 证券信息统计
        sec_stock_list = ck_client.query_df("""
            SELECT out_date = '2999-12-31' as is_active, count() as c 
            FROM stock_data.securities_info 
            WHERE type=1 
            GROUP BY is_active
        """)
        stock_stats = dict(zip(sec_stock_list['is_active'], sec_stock_list['c'])) if not sec_stock_list.empty else {}
        active_cnt = stock_stats.get(1, 0)
        delisted_cnt = stock_stats.get(0, 0)
        
        # K线股票覆盖数
        kline_stock_cnt = ck_client.query_df("SELECT uniq(code) as c FROM stock_data.stock_kline_day")['c'].iloc[0] if True else 0
        
        # 指数统计
        sec_index_cnt = ck_client.query_df("SELECT count() as c FROM stock_data.securities_info WHERE type=2")['c'].iloc[0] if True else 0
        kline_index_cnt = ck_client.query_df("SELECT uniq(code) as c FROM stock_data.index_kline_day")['c'].iloc[0] if True else 0
        
        # 缺失股票数
        missing_stocks = ck_client.query_df("""
            SELECT count() as c 
            FROM stock_data.securities_info 
            WHERE type=1 AND out_date = '2999-12-31' 
            AND code NOT IN (SELECT code FROM stock_data.stock_kline_day)
        """)['c'].iloc[0] if True else 0
        
        return {
            'last_date': last_date,
            'last_update': str(last_update)[:19] if last_update else 'N/A',
            'active_cnt': active_cnt,
            'delisted_cnt': delisted_cnt,
            'kline_stock_cnt': kline_stock_cnt,
            'sec_index_cnt': sec_index_cnt,
            'kline_index_cnt': kline_index_cnt,
            'missing_stocks': missing_stocks,
            'error': None
        }
    except Exception as e:
        return {
            'last_date': 'N/A', 'last_update': 'N/A',
            'active_cnt': 0, 'delisted_cnt': 0, 'kline_stock_cnt': 0,
            'sec_index_cnt': 0, 'kline_index_cnt': 0, 'missing_stocks': 0,
            'error': str(e)
        }

# Helper to get stock codes from CK
def get_all_stock_codes(date=None):
    """Fetch all unique stock codes from ClickHouse."""
    try:
        df = ck_client.query_df("SELECT distinct code FROM stock_data.securities_info ORDER BY code")
        return df['code'].tolist()
    except Exception as e:
        print(f"Error fetching codes: {e}")
        return []

# Load Config
def load_config():
    # Helper to load config from anywhere in src
    if os.path.exists("config.toml"):
        return toml.load("config.toml")
    return {}

CONFIG = load_config()

# Page Config
st.set_page_config(
    page_title="A股数据中心 (ClickHouse Edition)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CSS Injection ---
st.markdown("""
<style>
    html, body, [class*="css"]  { font-family: "PingFang SC", "Microsoft YaHei", sans-serif; }
    h1, h2, h3 { color: #1f77b4; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("📈 A股数据中心 (ClickHouse v3)")

# Sidebar
with st.sidebar:
    st.header("⚙️ 系统配置")
    st.info("数据源: ClickHouse (v3)")
    st.info(f"Host: {CK_HOST}")
    
    st.divider()
    st.subheader("🖥️ 服务状态")
    
    # Check CK Connection
    try:
        ver = ck_client.execute_query("SELECT version()")
        st.success(f"ClickHouse 在线 ({ver})")
    except Exception as e:
        st.error("ClickHouse 连接失败")
        st.caption(f"{e}")
        
    st.divider()
    st.subheader("📅 交易日历")
    if st.button("🔄 同步交易日历", use_container_width=True):
        with st.spinner("正在校对并同步交易日历到 ClickHouse..."):
            try:
                success, msg = etl_calendar.run_etl()
                if success:
                    st.success(msg)
                else:
                    st.warning(msg)
            except Exception as e:
                st.error(f"同步失败: {e}")

# Tabs
tab1, tab2, tab4, tab5, tab6 = st.tabs(["📊 仪表盘", "🛠️ 数据维护", "🔎 数据透视", "📈 趋势分析", "🚀 批量回测"])

# --- TAB 1: DASHBOARD ---
with tab1:
    st.subheader("📊 数据仓储总览")
    
    col_header, col_btn = st.columns([4, 1])
    with col_btn:
        if st.button("🔄 刷新", use_container_width=True, key="refresh_dashboard"):
            get_dashboard_stats.clear()
            st.rerun()
    
    col1, col2, col3 = st.columns(3)
    
    # 使用缓存函数自动加载数据
    stats = get_dashboard_stats()
    
    if stats['error']:
        st.error(f"无法获取统计信息: {stats['error']}")
    else:
        stock_cnt = stats['stock_cnt']
        stock_last = stats['stock_last']
        idx_cnt = stats['idx_cnt']
        sec_cnt = stats['sec_cnt']
        
        col1.metric("个股日线记录", f"{stock_cnt/10000:.1f}万", f"最新: {stock_last}")
        col2.metric("指数日线记录", f"{idx_cnt/10000:.1f}万")
        col3.metric("当前上市 A 股", f"{sec_cnt} 只")

    st.divider()
    st.caption("💡 本系统使用 ClickHouse 存算分离架构。统计数据缓存5分钟，点击刷新按钮获取最新状态。")

# ... imports ...
from src.etl import etl_calendar
from src.etl import etl_factors
from src.etl import etl_securities
from src.etl import etl_kline_loader

# ... (Config and Sidebar) ...

# Remove Sidebar Calendar Button to keep it clean (or keep it as fallback)
# But user asked for "One Click", so let's put it in Tab 2 central place.

# --- TAB 2: DATA MANAGER ---
# --- TAB 2: DATA MANAGER ---
with tab2:
    st.markdown("### 🛠️ 数据维护中心")
    st.markdown("---")

    col_action, col_monitor = st.columns([1, 1.2], gap="large")
    
    with col_action:
        st.markdown("#### 🚀 增量更新 (Incremental Update)")
        st.info(
            """
            **一键流水线 (Pipeline):**
            1.  **证券列表** (发现新股/退市)
            2.  **日线行情** (A股个股 + 核心指数增量)
            
            *💡 复权因子建议每周手动刷新一次*
            """
        )

        
        st.write("") # Spacer
        if st.button("▶️ 立即开始更新 (Start)", type="primary", use_container_width=True):
            status_container = st.container(border=True)
            with status_container:
                st.write("**执行日志:**")
                status_box = st.empty()
                progress_bar = st.progress(0)
            
            def log(msg, step=0, total_steps=4):
                status_box.markdown(f"> `[{step}/{total_steps}]` {msg}")
                progress_bar.progress(step/total_steps)

            try:
                # 日常增量更新只需要2步：证券列表 + K线
                # 复权因子仅在除权除息日需要更新，可手动或每周刷新一次
                total_steps = 2
                
                # Step 1: Securities
                log("正在刷新证券列表 (Securities)...", 0, total_steps)
                suc, msg = etl_securities.run_etl()
                if not suc:
                    st.error(f"❌ 证券列表刷新失败: {msg}")
                    st.stop()
                
                # Step 2: K-Lines (Incremental)
                log("正在增量补齐日线行情 (K-Lines)...", 1, total_steps)
                suc, msg = etl_kline_loader.run_etl(mode='incremental')
                if not suc:
                    st.error(f"❌ 行情更新失败: {msg}")
                else:
                    log("✅ 所有更新任务完成！", 2, total_steps)
                    st.balloons()

                    st.success(f"🎉 更新成功! {msg}")
                    time.sleep(3)
                    st.rerun()
                    
            except Exception as e:
                st.error(f"💣 发生致命错误: {e}")

        st.write("")
        with st.expander("🧩 高级维护 (复权因子)", expanded=False):
            st.info("说明：复权因子通常只需在分红送转密集期更新。日常更新只需点击上方的【立即开始更新】。")
            if st.button("🔄 执行因子增量更新", use_container_width=True):
                with st.status("正在更新复权因子...", expanded=True) as status:
                    st.write("初始化因子加载器...")
                    suc, msg = etl_factors.run_etl(mode='incremental')
                    if suc:
                        status.update(label="✅ 更新成功", state="complete", expanded=False)
                        st.success(msg)
                    else:
                        status.update(label="❌ 更新失败", state="error")
                        st.error(msg)



    with col_monitor:
        st.markdown("#### 📊 数据仓库状态 (Warehouse Status)")
        
        if st.button("🔄 刷新状态", use_container_width=True, key="refresh_warehouse"):
            get_warehouse_status.clear()
            st.rerun()
        
        # 使用缓存函数自动加载
        status = get_warehouse_status()
        
        if status['error']:
            st.error(f"⚠️ 无法连接数据库: {status['error']}")
        else:
            m_c1, m_c2 = st.columns(2)
            m_c1.metric("📅 最新行情日期", f"{status['last_date']}")
            m_c2.metric("⏱️ 上次更新时间", f"{status['last_update']}")
            
            st.divider()
            
            active_cnt = status['active_cnt']
            delisted_cnt = status['delisted_cnt']
            kline_stock_cnt = status['kline_stock_cnt']
            sec_index_cnt = status['sec_index_cnt']
            kline_index_cnt = status['kline_index_cnt']
            missing_stocks = status['missing_stocks']
            
            st.write(f"**A股覆盖率 (Stocks):**")
            st.progress(min(kline_stock_cnt / (active_cnt if active_cnt>0 else 1), 1.0))
            st.caption(f"已收录: `{kline_stock_cnt}` / 上市中: `{active_cnt}` (历史退市: {delisted_cnt})")
            
            st.write(f"**指数覆盖率 (Indexes):**")
            st.progress(min(kline_index_cnt / (sec_index_cnt if sec_index_cnt>0 else 1), 1.0))
            st.caption(f"已收录: `{kline_index_cnt}` / 总数: `{sec_index_cnt}`")

            if missing_stocks > 0:
                st.warning(f"⚠️ 警告: 有 {missing_stocks} 只上市个股缺失行情数据！请立即运行更新。")
            else:
                st.success(f"✅ 数据完整性校验通过 (100% 覆盖)")



# --- TAB 4: DATA VIEWER ---
with tab4:
    st.subheader("🔎 数据透视")
    
    v_col1, v_col2, v_col3 = st.columns(3)
    
    code_input = v_col1.text_input("股票代码 (如 sh.600000)", value="sh.600000")
    
    # 从配置读取默认开始日期
    default_start_str = CONFIG.get('ui', {}).get('default_view_start_date', '2025-01-01')
    default_start = datetime.strptime(default_start_str, "%Y-%m-%d")
    
    start_input = v_col2.date_input("开始日期", default_start)
    end_input = v_col3.date_input("结束日期", datetime.now())
    
    adjust_opt = st.radio("复权方式", ["后复权 (hfq)", "前复权 (qfq)", "不复权 (none)"], horizontal=True)
    adjust_map = {"后复权 (hfq)": "hfq", "前复权 (qfq)": "qfq", "不复权 (none)": "none"}
    
    if st.button("📈 加载并绘图"):
        s_str = start_input.strftime("%Y-%m-%d")
        e_str = end_input.strftime("%Y-%m-%d")
        
        with st.spinner("正在从快照中提取数据并计算复权..."):
            df = get_price(code_input, s_str, e_str, adjust_map[adjust_opt])
            
        if df.empty:
            st.warning("在此时间段内未找到该股票数据。(请确认是否已在【数据管理】中下载了对应日期的快照)")
        else:
            st.success(f"加载成功: 共 {len(df)} 条交易记录")
            # st.dataframe(df.head(), use_container_width=True) # Removed as requested

            
            # --- Calculation ---
            # Calculate Moving Averages
            for ma in [5, 10, 20]:
                df[f'MA{ma}'] = df['close'].rolling(window=ma).mean()
                df[f'V_MA{ma}'] = df['volume'].rolling(window=ma).mean()
            
            # --- Visualization ---
            # Ensure date is string YYYY-MM-DD to allow 'category' axis without time
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            from plotly.subplots import make_subplots
            
            # Create subplots: 2 rows (Price, Volume), shared x-axis
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.7, 0.3],
                specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
            )
            
            # 1. Candlestick (Row 1)
            fig.add_trace(go.Candlestick(
                x=df['date'],
                open=df['open'], high=df['high'], low=df['low'], close=df['close'],
                name="K线",
                increasing_line_color='#ef5350', decreasing_line_color='#26a69a'
            ), row=1, col=1)
            
            # 2. Price MAs (Row 1)
            colors = {5: '#ff9800', 10: '#9c27b0', 20: '#2196f3'} # Orange, Purple, Blue
            for ma in [5, 10, 20]:
                fig.add_trace(go.Scatter(
                    x=df['date'], y=df[f'MA{ma}'], 
                    mode='lines', 
                    name=f'MA{ma}',
                    line=dict(color=colors[ma], width=1)
                ), row=1, col=1)
            
            # 3. Volume Bar (Row 2)
            # Color volume based on close > open (or close > prev_close?)
            # Usually red if close >= open, green if close < open
            vol_colors = ['#ef5350' if c >= o else '#26a69a' for c, o in zip(df['close'], df['open'])]
            
            fig.add_trace(go.Bar(
                x=df['date'], y=df['volume'],
                name="成交量",
                marker_color=vol_colors
            ), row=2, col=1)
            
            # 4. Volume MAs (Row 2) - Optional, but requested
            vol_ma_colors = {5: '#ff9800', 10: '#9c27b0', 20: '#2196f3'}
            for ma in [5, 10, 20]:
                fig.add_trace(go.Scatter(
                    x=df['date'], y=df[f'V_MA{ma}'],
                    mode='lines',
                    name=f'Vol MA{ma}',
                    line=dict(color=vol_ma_colors[ma], width=1),
                    opacity=0.7
                ), row=2, col=1)
            
            # Layout Updates
            # Get Name for Title
            try:
                name_res = ck_client.query_df(f"SELECT symbol FROM stock_data.securities_info WHERE code='{code_input}' LIMIT 1")
                stock_name = name_res['symbol'].iloc[0] if not name_res.empty else ""
            except:
                stock_name = ""

            fig.update_layout(
                title=f"<b>{code_input} {stock_name}</b> 历史K线图 ({adjust_opt})",
                template='plotly_white',
                hovermode='x unified',
                height=800,
                margin=dict(l=50, r=50, t=80, b=50),
                xaxis_rangeslider_visible=False, # Hide default range slider to save space
                font=dict(family="PingFang SC, Microsoft YaHei, sans-serif"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            # X-Axis: Remove gaps
            fig.update_xaxes(type='category', nticks=20, tickangle=-45, row=2, col=1)
            fig.update_xaxes(type='category', visible=False, row=1, col=1) # Hide x-labels on top chart
            
            # Y-Axis configuration: Fix range to prevent vertical zooming/panning
            fig.update_yaxes(title_text="价格", row=1, col=1, fixedrange=True)
            fig.update_yaxes(title_text="成交量", row=2, col=1, fixedrange=True)

            
            st.plotly_chart(fig, use_container_width=True)


# --- TAB 5: TREND ANALYSIS ---
with tab5:
    st.subheader("📈 趋势波段识别 (Topological Trend)")
    st.info("基于《高低点讨论》文档中的拓扑学/分形逻辑，自动识别股价的结构性波动。")
    
    t_col1, t_col2, t_col3 = st.columns(3)
    
    t_code = t_col1.text_input("分析-股票代码", value="sh.600000", key="trend_code")
    t_start = t_col2.date_input("分析-开始日期", default_start, key="trend_start")
    t_end = t_col3.date_input("分析-结束日期", datetime.now(), key="trend_end")
    
    st.divider()
    
    # --- UI Logic: Auto vs Manual ---
    p_col1, p_col2, p_col3 = st.columns([1, 1, 1])
    
    with p_col1:
        thresh_method = st.selectbox("阈值算法", ["ATR波动率 (自适应)", "固定百分比", "固定数值"], index=0)
        method_map = {"ATR波动率 (自适应)": "atr", "固定百分比": "fixed", "固定数值": "val"}
        
    with p_col2:
        mode = st.radio("参数模式", ["🤖 自动 (肘部法则)", "🔧 手动设置"], horizontal=True)
        
    with p_col3:
        if mode == "🔧 手动设置":
            default_val = 1.5 if thresh_method == "ATR波动率 (自适应)" else (0.05 if thresh_method == "固定百分比" else 0.5)
            manual_val = st.number_input("阈值系数", value=default_val, step=0.1, format="%.2f", key="manual_thresh")
        else:
            st.info("系统将自动计算最佳阈值")
    
    # Button to Trigger Logic
    if st.button("🌊 识别波段", type="primary"):
        s_str_t = t_start.strftime("%Y-%m-%d")
        e_str_t = t_end.strftime("%Y-%m-%d")
        
        with st.spinner("正在执行拓扑分析..."):
            # 1. Load Data
            # Always fetch up to Today to allow "Walk Forward" simulation after t_end
            e_str_today = datetime.now().strftime("%Y-%m-%d")
            # User Request: Use Forward Adjustment (qfq) instead of Backward Adjustment (hfq)
            df_all = get_price(t_code, s_str_t, e_str_today, adjust='qfq')
            
            # Slice for Analysis Visualization (Up to t_end)
            if not df_all.empty:
                # Ensure date column is datetime for comparison
                # ClickHouse date is string? NO, query_df returns what?
                # Usually pandas converts Date column to datetime64[ns]
                if not pd.api.types.is_datetime64_any_dtype(df_all['date']):
                     df_all['date'] = pd.to_datetime(df_all['date'])
                
                # t_end is datetime.date from st.date_input
                # Convert to Timestamp for comparison
                t_end_ts = pd.Timestamp(t_end)
                
                df_t = df_all[df_all['date'] <= t_end_ts]
            else:
                df_t = pd.DataFrame() # Empty
            
            if df_t.empty:
                st.error("未找到数据，请先下载或检查日期范围。")
                # Clear session state if data not found
                if 'trend_results' in st.session_state:
                    del st.session_state['trend_results']
            else:
                algo = TopologicalTrendIdentifier(df_t)
                
                # 2. Determine Threshold Value
                final_val = 0.0
                debug_info = None
                
                if mode == "🤖 自动 (肘部法则)":
                    with st.spinner("算力介入：正在寻找最佳肘部..."):
                        if thresh_method == "固定百分比":
                            final_val, debug_info = algo.optimize_threshold_elbow(method='fixed', start=0.01, end=0.20, step=0.01)
                        elif thresh_method == "ATR波动率 (自适应)":
                            final_val, debug_info = algo.optimize_threshold_elbow(method='atr', start=0.5, end=5.0, step=0.1)
                        else:
                            final_val, debug_info = algo.optimize_threshold_elbow(method='val', start=1, end=50, step=1)
                        
                        st.success(f"🤖 自动优化完成：最佳阈值 = {final_val:.2f}")
                else:
                    final_val = manual_val
                
                # 3. Run Swing Analysis
                swings = algo.identify_swings(threshold_method=method_map[thresh_method], threshold_value=final_val)
                
                # 4. Volume Price Analysis (New Step)
                swings = algo.analyze_volume_price(swings)
                swings = algo.analyze_signals(swings) # New Signal Diagnosis
                swings = algo.calculate_trend_score(swings) # Quant Scoring
                
                # Store in Session State
                st.session_state['trend_results'] = {
                    'df_t': df_t,
                    'df_all': df_all, # Store full data for simulation
                    'swings': swings,
                    'final_val': final_val,
                    'debug_info': debug_info,
                    't_code': t_code,
                    't_start': t_start,
                    't_end': t_end
                }
    
    # --- RENDER RESULTS (Persisted) ---
    if 'trend_results' in st.session_state:
        res = st.session_state['trend_results']
        
        # Check if code changed, maybe warn or clear? 
        # For simple UX, we show what was last analyzed.
        
        df_t = res['df_t']
        df_all = res.get('df_all', df_t) # Fallback for old state
        swings = res['swings']
        final_val = res['final_val']
        debug_info = res['debug_info']
        layout_code = res['t_code']
        layout_t_start = res.get('t_start', date.today())
        layout_t_end = res.get('t_end', date.today())
        
        # 5. Visualization (Indent level 2)
        
        # If Auto mode, show the Elbow Curve first (small)
        if mode == "🤖 自动 (肘部法则)" and debug_info:
            with st.expander("查看参数优化过程 (肘部曲线)", expanded=False):
                fig_elbow = go.Figure()
                fig_elbow.add_trace(go.Scatter(x=debug_info['x'], y=debug_info['y'], mode='lines+markers', name='波段数量'))
                fig_elbow.add_trace(go.Scatter(
                    x=[debug_info['elbow_x']], 
                    y=[debug_info['elbow_y']], 
                    mode='markers', 
                    marker=dict(color='red', size=12, symbol='star'),
                    name='Elbow (最佳点)'
                ))
                fig_elbow.update_layout(title="阈值优化曲线", height=300, margin=dict(t=30, b=20))
                st.plotly_chart(fig_elbow, use_container_width=True)

        st.info(f"当前分析参数: {thresh_method} | 阈值: {final_val:.2f} | 发现转折点: {len(swings)} 个 | 标的: {layout_code}")
        
        
        # Plot
        # Ensure date is string YYYY-MM-DD to hide time on category axis
        df_t['date'] = pd.to_datetime(df_t['date']).dt.strftime('%Y-%m-%d')
        
        fig_t = go.Figure()
        
        # Layer 1: Candlestick
        fig_t.add_trace(go.Candlestick(
            x=df_t['date'],
            open=df_t['open'],
            high=df_t['high'],
            low=df_t['low'],
            close=df_t['close'],
            name="K线 (后复权)",
            increasing_line_color='#ef5350',
            decreasing_line_color='#26a69a'
        ))
        
        # Layer 2: Trend Waves (Connect Swings)
        show_vol_labels = st.checkbox("在图表上显示波段量价数据", value=True)
        
        if swings:
            swing_dates = [pd.to_datetime(s.date).strftime('%Y-%m-%d') for s in swings]
            swing_prices = [s.price for s in swings]
            
            # Construct Annotation Text
            text_labels = []
            for s in swings:
                if s.vol_sum > 0:
                    v_str = f"{s.vol_sum/100000000:.2f}亿" if s.vol_sum > 100000000 else f"{s.vol_sum/10000:.0f}万"
                    eff_str = f"{s.efficiency:.1f}"
                    desc = s.desc_text if s.desc_text else f"S:{s.score:.0f}"
                    label = f"V:{v_str}<br>E:{eff_str}<br><b>{desc}</b>"
                    
                    if not s.desc_text and s.signal_text:
                            label += f"<br><b>{s.signal_text}</b>"
                        
                    text_labels.append(label)
                else:
                    text_labels.append("")
            
            mode_combine = 'lines+markers+text' if show_vol_labels else 'lines+markers'
            
            fig_t.add_trace(go.Scatter(
                x=swing_dates,
                y=swing_prices,
                mode=mode_combine,
                name='趋势波段 (ZigZag)',
                line=dict(color='blue', width=2),
                marker=dict(symbol='circle', size=6, color='yellow', line=dict(width=1, color='black')),
                text=text_labels,
                textposition="top center",
                textfont=dict(size=11, color='#E6A800')
            ))
        
        # Get Name for Title
        try:
            name_res = ck_client.query_df(f"SELECT symbol FROM stock_data.securities_info WHERE code='{layout_code}' LIMIT 1")
            stock_name = name_res['symbol'].iloc[0] if not name_res.empty else ""
        except:
            stock_name = ""

        fig_t.update_layout(
            title=f"<b>{layout_code} {stock_name}</b> 趋势波段识别 (量价诊断)",
            template='plotly_white',
            height=700,
            xaxis=dict(type='category', rangeslider_visible=False),
            yaxis=dict(fixedrange=True),
            hovermode='x unified'
        )

        
        st.plotly_chart(fig_t, use_container_width=True)
        
        # --- Volume Bar Chart (Inter-Wave) ---
        if swings and len(swings) > 1:
            st.markdown("### 📊 波段能量对比 (Inter-Wave Volume)")
            st.caption("红色柱: 上涨波段的总成交量 (做多能量); 绿色柱: 下跌波段的总成交量 (做空抛压)。通过高低柱对比可发现背离。")
            
            v_dates = []
            v_vols = []
            v_colors = []
            v_hover = []
            
            for i in range(1, len(swings)):
                s = swings[i]
                v_dates.append(s.date)
                v_vols.append(s.vol_sum)
                
                color = '#ef5350' if s.type == 'HIGH' else '#26a69a'
                v_colors.append(color)
                
                txt = f"{s.type} leg<br>Vol: {s.vol_sum/10000:.0f}万<br>{s.signal_text}"
                v_hover.append(txt)
                
            fig_v = go.Figure(data=[go.Bar(
                x=v_dates,
                y=v_vols,
                marker_color=v_colors,
                hovertext=v_hover,
                name="波段成交量"
            )])
            
            fig_v.update_layout(
                title="各波段累计成交量 (Volume Flow)",
                template='plotly_white',
                height=300,
                xaxis=dict(type='category'),
                yaxis=dict(title="成交量 (手)", fixedrange=True)
            )

            st.plotly_chart(fig_v, use_container_width=True)
        
        # Show details
        with st.expander("查看波段量价分析详情", expanded=True):
            s_data = []
            for s in swings:
                # Calculate Lag
                lag = "-"
                conf_date = "-"
                if s.conf_index != -1:
                    conf_date = s.conf_date
                    lag = f"{s.conf_index - s.index} bars"
                    
                s_data.append({
                    "日期": s.date,
                    "类型": s.type,
                    "价格": f"{s.price:.2f}",
                    "评分": int(s.score),
                    "信号": s.signal_text,
                    "幅度(%)": f"{s.amplitude*100:.2f}%" if s.amplitude != 0 else "-",
                    "持续(天)": s.duration if s.duration > 0 else "-",
                    "累计成交(手)": f"{s.vol_sum/100:.0f}", 
                    "量价效率": f"{s.efficiency:.2f}",
                    "确认日期": conf_date,
                    "滞后": lag
                })
            st.dataframe(pd.DataFrame(s_data))
            
        st.divider()
        st.subheader("🔮 趋势推演与回测 (Strategy Simulation)")
        st.caption("基于‘有限状态机’的逐日推演。系统模拟每天只知道当天数据的情况，根据确认信号和验证期进行交易决策。")
        
        with st.form("sim_parameters_form"):
            col_sim1, col_sim2, col_sim3 = st.columns(3)
            with col_sim1:

                # Smart Default Logic
                # User Request: Default should be "Analysis End Date + 1 Day"
                
                # 1. Calculate the preferred default: Next Day after Analysis End
                default_sim_start = layout_t_end + timedelta(days=1)
                
                # 2. Check Data Boundaries
                if not df_all.empty:
                    # df_all usually goes up to Today
                    max_date_in_data = df_all['date'].iloc[-1] 
                    if isinstance(max_date_in_data, datetime):
                        max_date_in_data = max_date_in_data.date()
                    
                    # If preferred default is beyond available data (e.g. Analysis End was already Today),
                    # Fallback to Analysis Start Date (Full Backtest Mode)
                    if default_sim_start > max_date_in_data:
                        default_sim_start = layout_t_start
                
                sim_start_date = st.date_input("推演开始日期", value=default_sim_start)
            with col_sim2:
                # Add End Date Picker
                sim_end_date = st.date_input("推演结束日期", value=datetime.today())
                
            with col_sim3:
                st.write("")
                st.write("")
                run_sim = st.form_submit_button("▶️ 开始推演", type="primary")
            
        if run_sim:
            with st.spinner("正在进行逐日推演 (可能需要几秒钟)..."):
                sim_engine = TradeSignalGenerator(df_all)
                start_str = sim_start_date.strftime("%Y-%m-%d")
                end_str = sim_end_date.strftime("%Y-%m-%d")
                
                df_states = sim_engine.run_simulation(
                    start_date=start_str, 
                    end_date=end_str,
                    threshold_method=method_map[thresh_method], 
                    threshold_value=final_val
                )
                
                if not df_states.empty:
                    signals = sim_engine.signals
                    
                    # --- Visualization ---
                    fig_sim = go.Figure()
                    
                    # 1. Price Line
                    fig_sim.add_trace(go.Scatter(
                        x=df_states['date'], 
                        y=df_states['close'], 
                        mode='lines', 
                        name='收盘价',
                        line=dict(color='gray', width=1)
                    ))
                    
                    # Add Signals
                    if signals:
                        buy_x = [s.date for s in signals if s.type == 'BUY']
                        buy_y = [s.price for s in signals if s.type == 'BUY']
                        buy_text = [s.reason for s in signals if s.type == 'BUY']
                        
                        sell_x = [s.date for s in signals if s.type == 'SELL']
                        sell_y = [s.price for s in signals if s.type == 'SELL']
                        sell_text = [s.reason for s in signals if s.type == 'SELL']
                        
                        fig_sim.add_trace(go.Scatter(
                            x=buy_x, y=buy_y, mode='markers', name='买入信号',
                            marker=dict(symbol='triangle-up', size=12, color='red'),
                            text=buy_text, hoverinfo='text+x+y'
                        ))
                        
                        fig_sim.add_trace(go.Scatter(
                            x=sell_x, y=sell_y, mode='markers', name='卖出信号',
                            marker=dict(symbol='triangle-down', size=12, color='green'),
                            text=sell_text, hoverinfo='text+x+y'
                        ))
                    
                    # Status Bands
                    color_map = {
                        SimulationState.HOLD_LONG.value: '#ef5350', # Red
                        SimulationState.HOLD_CASH.value: '#eeeeee', # Grey
                    }
                    state_colors = [color_map.get(s, 'black') for s in df_states['state']]
                    
                    fig_sim.add_trace(go.Scatter(
                        x=df_states['date'], 
                        y=df_states['close'],
                        mode='markers',
                        name='持仓状态',
                        marker=dict(size=4, color=state_colors)
                    ))

                    fig_sim.update_layout(
                        title="策略推演结果 (State Machine Walk-Forward)",
                        height=500,
                        template='plotly_white',
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig_sim, use_container_width=True)
                    
                    # Log Table
                    if signals:
                        st.write("📝 **交易信号日志**")
                        sig_df = pd.DataFrame([vars(s) for s in signals])
                        st.dataframe(sig_df)
                    else:
                        st.info("在此期间未触发交易信号。")
                        
                else:
                    st.warning("推演数据为空，请检查开始日期。")

# ==========================================
# TAB 6: BATCH BACKTEST
# ==========================================
with tab6:
    st.header("🚀 批量策略回测 (Batch Strategy Backtest)")
    st.write("在多只股票上验证策略的统计学优势。")
    
    with st.expander("📝 回测配置 (Settings)", expanded=True):
        col_b1, col_b2 = st.columns(2)
        
        with col_b1:
            st.subheader("1. 标的选择")
            stock_input_mode = st.radio("选择模式", ["手工输入", "全市场批量 (自动过滤停牌)"], index=1, horizontal=True)
            
            stock_codes_input = ""
            if stock_input_mode == "手工输入":
                stock_codes_txt = st.text_area("输入股票代码 (逗号分隔)", value="sh.600000, sh.600036, sz.000001", height=100)
                stock_codes_input = stock_codes_txt
            else:
                st.info("系统将自动遍历全市场所有 A 股标的，并自动剔除在回测区间内发生过停牌的股票。这可能需要较长时间。")
                stock_codes_input = "ALL_MARKET"

        with col_b2:
            st.subheader("2. 时间区间 & 参数")
            
            # 1. Analysis Period (for Threshold Calculation)
            st.markdown("##### (1) 分析区间 (用于计算阈值)")
            col_d1, col_d2 = st.columns(2)
            ana_start = col_d1.date_input("分析开始", value=date(2025, 1, 1))
            ana_end = col_d2.date_input("分析结束", value=date(2025, 9, 1))
            
            # 2. Backtest Period
            st.markdown("##### (2) 回测区间 (模拟交易)")
            bt_start_default = ana_end + timedelta(days=1)
            bt_end_default = date.today()
            
            col_d3, col_d4 = st.columns(2)
            bt_start = col_d3.date_input("回测开始", value=bt_start_default, disabled=True, help="自动设为分析结束日期的下一天")
            bt_end = col_d4.date_input("回测结束", value=bt_end_default)
            
            st.divider()
            
            init_capital = st.number_input("初始资金 (每只票)", value=5000000)
            min_pos = st.slider("底仓比例 (Min Position %)", 0.0, 1.0, 0.4, 0.05)
            
            # Threshold is now AUTO
            st.info("阈值设定: 将基于【分析区间】的数据，使用肘部法则自动计算每只股票的最佳阈值。")
            thresh_mode = 'auto_elbow' 
            thresh_val = 0.0 # Placeholder
            
    run_batch = st.button("▶️ 开始批量回测", type="primary", use_container_width=True)
    
    if run_batch:
        if stock_codes_input == "ALL_MARKET":
            with st.spinner("正在获取全市场股票列表..."):
                codes = get_all_stock_codes(date=None) # Fetch latest
        else:
            codes = [c.strip() for c in stock_codes_input.split(',') if c.strip()]
        
        if not codes:
            st.error("请先输入股票代码列表")
        else:
            # Progress placeholders
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(current, total, msg):
                progress_bar.progress(current / total if total > 0 else 1.0)
                status_text.text(msg)

            # --- New Architecture: Strategy + Engine ---
            strategy = TopologySwingStrategy()
            strategy.initialize({'auto_elbow': True, 'threshold_value': 1.5})
            
            engine = BacktestEngine(
                strategy=strategy,
                data_loader=data_loader_get_price,
                portfolio_config={
                    'initial_capital': 5000000.0,
                    'min_pos_pct': min_pos
                }
            )
            
            df_results = engine.run(
                stock_codes=codes,
                analysis_start=ana_start.strftime("%Y-%m-%d"),
                analysis_end=ana_end.strftime("%Y-%m-%d"),
                backtest_start=bt_start.strftime("%Y-%m-%d"),
                backtest_end=bt_end.strftime("%Y-%m-%d"),
                auto_filter=True,
                progress_callback=update_progress
            )
                
            if not df_results.empty:
                st.success("回测完成！")
                
                # --- SUMMARY ---
                st.divider()
                st.subheader("📊 汇总报告 (Aggregate Report)")
                
                # Metrics
                avg_ret = df_results['total_return'].mean()
                med_ret = df_results['total_return'].median()
                pos_ret_stocks = len(df_results[df_results['total_return'] > 0])
                total_stocks = len(df_results)
                win_stock_rate = pos_ret_stocks / total_stocks if total_stocks > 0 else 0
                avg_trade_win_rate = df_results['win_rate'].mean()
                
                # Benchmark Metrics
                avg_hold_ret = df_results['hold_return'].mean()
                index_ret = df_results['index_return'].iloc[0] if not df_results.empty else 0
                
                cm1, cm2, cm3, cm4, cm5 = st.columns(5)
                cm1.metric("策略平均收益", f"{avg_ret*100:.2f}%", f"{(avg_ret-avg_hold_ret)*100:+.2f}% vs 持有")
                cm2.metric("标的平均涨幅", f"{avg_hold_ret*100:.2f}%")
                cm3.metric("同期上证指数", f"{index_ret*100:.2f}%", f"{(avg_ret-index_ret)*100:+.2f}% 跑赢")
                cm4.metric("平均胜率", f"{avg_trade_win_rate*100:.1f}%")
                cm5.metric("标的数量", f"{total_stocks}")

                st.info(f"💡 策略正收益比例: {win_stock_rate*100:.1f}% | 收益中位数: {med_ret*100:.2f}%")
                
                # --- DETAILED TABLE ---
                st.subheader("📋 详细数据 (Details)")
                st.dataframe(
                    df_results.style.format({
                        'total_return': "{:.2%}",
                        'hold_return': "{:.2%}",
                        'index_return': "{:.2%}",
                        'win_rate': "{:.2%}",
                        'max_drawdown': "{:.2%}",
                        'final_value': "{:,.0f}",
                        'initial_value': "{:,.0f}"
                    }),
                    use_container_width=True
                )
                
                # --- CHARTS ---
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.markdown("##### 收益率分布 (Return Distribution)")
                    fig_dist = go.Figure()
                    fig_dist.add_trace(go.Histogram(x=df_results['total_return'], nbinsx=20, name='Return'))
                    st.plotly_chart(fig_dist, use_container_width=True)
                    
                with col_c2:
                    st.markdown("##### 收益率 vs 交易次数")
                    fig_sc = go.Scatter(
                        x=df_results['trade_count'],
                        y=df_results['total_return'],
                        mode='markers',
                        text=df_results['stock_code']
                    )
                    st.plotly_chart(go.Figure(fig_sc), use_container_width=True)
                    
            else:
                st.warning("未生成回测结果，可能是数据缺失或代码错误。")
