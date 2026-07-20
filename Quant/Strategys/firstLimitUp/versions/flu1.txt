import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import configparser
from clickhouse_driver import Client
import re

# ----------------------------
# 1. ClickHouse连接配置 (已根据要求修改用户名和密码)
# ----------------------------
def get_clickhouse_client():
    """
    创建并返回ClickHouse客户端
    根据实际环境修改host, port, user, password
    """
    return Client(
        host='localhost',
        port=9000,
        user='admin',           # 已修改为 admin
        password='admin_password', # 已修改为 admin_password
        database='stock_data',
        settings={'use_numpy': True}
    )

# ----------------------------
# 2. 工具函数
# ----------------------------
def get_config():
    """
    从config.txt读取回调幅度上下限和EndDate
    格式: 
    UpperLimit:75%
    LowerLimit:10%
    EndDate:20250806 (可选)
    """
    # 默认配置
    config = {
        'lower_limit': 0.10,  # 默认10%
        'upper_limit': 0.75,  # 默认75%
        'end_date': None      # 默认None，表示使用最新交易日
    }
    
    if os.path.exists('config.txt'):
        print("正在读取 config.txt...")
        try:
            # 显式指定 encoding='utf-8' 以避免编码问题
            with open('config.txt', 'r', encoding='utf-8') as f:
                line_number = 0
                for line in f:
                    line_number += 1
                    original_line = line
                    line = line.strip() # 去除首尾空白字符
                    print(f"  读取第 {line_number} 行: '{original_line.strip()}'")
                    
                    if not line or ':' not in line: # 跳过空行和无冒号的行
                        if line: # 只对非空行给出警告
                            print(f"    -> 警告：格式不正确，跳过")
                        continue

                    parts = line.split(':', 1) # 只分割一次
                    key = parts[0].strip()
                    value_raw = parts[1].strip()
                    print(f"    -> 解析 Key: '{key}', Value: '{value_raw}'")
                    
                    if not value_raw:
                         print(f"    -> 警告：没有指定值，跳过")
                         continue

                    # --- 简化处理 ---
                    if key == 'LowerLimit':
                        if value_raw.endswith('%'):
                            try:
                                # 直接移除末尾的 '%' 并转换为小数
                                percent_value = float(value_raw[:-1]) # 去掉最后一个字符 ('%')
                                config['lower_limit'] = percent_value / 100.0
                                print(f"    -> 解析为小数: {config['lower_limit']}")
                            except ValueError:
                                print(f"    -> 警告：'{value_raw}' 不是有效的百分比格式，跳过。")
                        else:
                            print(f"    -> 警告：LowerLimit 值 '{value_raw}' 必须以 '%' 结尾，跳过。")
                    
                    elif key == 'UpperLimit':
                        if value_raw.endswith('%'):
                            try:
                                percent_value = float(value_raw[:-1])
                                config['upper_limit'] = percent_value / 100.0
                                print(f"    -> 解析为小数: {config['upper_limit']}")
                            except ValueError:
                                print(f"    -> 警告：'{value_raw}' 不是有效的百分比格式，跳过。")
                        else:
                            print(f"    -> 警告：UpperLimit 值 '{value_raw}' 必须以 '%' 结尾，跳过。")
                    
                    elif key == 'EndDate':
                        if value_raw.isdigit() and len(value_raw) == 8:
                            config['end_date'] = value_raw
                            print(f"    -> EndDate: {config['end_date']}")
                        else:
                           print(f"    -> 警告：EndDate 值 '{value_raw}' 格式不正确 (应为 YYYYMMDD)，跳过。")
                    else:
                        print(f"    -> 警告：未知的配置项 '{key}'，跳过。")
                    # --- 结束 ---
                    
        except Exception as e:
            print(f"读取config.txt时发生错误，使用默认值: {str(e)}")
            # import traceback
            # traceback.print_exc() # 如需详细堆栈可取消注释
    
    # --- 打印读取到的实际配置值 ---
    print(f"最终读取到的配置:")
    print(f"  - 回调幅度下限: {config['lower_limit'] * 100:.2f}%")
    print(f"  - 回调幅度上限: {config['upper_limit'] * 100:.2f}%")
    if config['end_date']:
        print(f"  - 指定结束日期: {config['end_date']}")
    else:
        print(f"  - 指定结束日期: 未设置 (将使用最新交易日)")
    # --- 结束 ---
    
    return config


def load_stock_info():
    """
    从AllA.xlsx加载股票代码、名称和行业信息
    AllA.xlsx 中的代码是纯6位数字
    """
    if not os.path.exists('AllA.xlsx'):
        raise FileNotFoundError("找不到AllA.xlsx文件，请确保该文件与脚本在同一目录")
    
    df_info = pd.read_excel('AllA.xlsx')
    
    # 标准化股票代码为6位数字 (处理 = "000032" 这种格式)
    df_info['股票代码'] = df_info['股票代码'].astype(str).str.replace(r'[^\d]', '', regex=True).str.zfill(6)
    
    # 构建股票信息字典 (Key: 6位数字代码)
    stock_info_dict = {}
    for _, row in df_info.iterrows():
        code = row['股票代码'] # 6位数字
        name = str(row['股票简称']).strip().replace('Ａ', 'A')
        industry = str(row['所属行业']).strip()
        stock_info_dict[code] = {
            '股票名称': name,
            '行业': industry
        }
    
    return stock_info_dict

# ----------------------------
# 3. 从完整代码提取6位数字代码 (保留此函数用于匹配 stock_info_dict)
# ----------------------------
def extract_6digit_code(full_code):
    """
    从 'sh.600000' 或 'sz.000001' 提取 '600000'
    此函数仅用于从数据库代码匹配 AllA.xlsx 信息，不用于最终输出
    """
    match = re.search(r'\.(\d{6})$', full_code)
    return match.group(1) if match else None

# ----------------------------
# 4. 主策略查询
# ----------------------------
def execute_strategy():
    """
    执行首板回调策略，使用 index_k 作为交易日历，daily_k 作为个股数据源
    """
    # 获取配置
    config = get_config()
    lower_limit = config['lower_limit']
    upper_limit = config['upper_limit']
    specified_end_date_str = config['end_date'] # YYYYMMDD 格式的字符串或 None
    
    # 获取股票基本信息 (Key: 6位数字代码)
    stock_info_dict = load_stock_info()
    
    # 创建ClickHouse客户端
    client = get_clickhouse_client()
    
    # ----------------------------
    # 获取交易日历并确定T日
    # ----------------------------
    print("正在获取交易日历并确定T日...")
    try:
        # 获取足够多的交易日用于确定T日 (最多回溯30天)
        lookback_days = 30
        end_date_for_query = datetime.now().date()
        start_date_for_query = end_date_for_query - timedelta(days=lookback_days)
        
        trading_calendar_query = """
        SELECT date
        FROM stock_data.index_k
        WHERE code = 'sh.000001' AND date >= %(start_date)s AND date <= %(end_date)s
        ORDER BY date DESC
        """
        
        trading_dates_result = client.execute(
            trading_calendar_query,
            {
                'start_date': start_date_for_query.strftime('%Y-%m-%d'),
                'end_date': end_date_for_query.strftime('%Y-%m-%d')
            }
        )
        
        if not trading_dates_result:
             raise Exception(f"交易日历中未找到任何交易日。")
        
        # 处理 numpy.datetime64 类型并排序 (最新的在前)
        raw_dates = [row[0] for row in trading_dates_result]
        all_trading_dates = []
        for d in raw_dates:
            if isinstance(d, np.datetime64):
                dt = pd.to_datetime(d).to_pydatetime()
                all_trading_dates.append(dt.date() if hasattr(dt, 'date') else dt)
            else:
                all_trading_dates.append(d if not hasattr(d, 'date') else d.date())
        
        all_trading_dates.sort(reverse=True) # 最新的在前
        # print(f"获取到的交易日列表 (最新在前): {[d.strftime('%Y-%m-%d') for d in all_trading_dates]}") # 调试用
        
        # --- 新增：确定T日逻辑 ---
        t_date = None
        if specified_end_date_str:
            try:
                # 尝试将配置的日期字符串解析为 date 对象
                specified_date = datetime.strptime(specified_end_date_str, '%Y%m%d').date()
                print(f"配置文件指定了结束日期: {specified_date.strftime('%Y-%m-%d')}")
                
                # 检查指定日期是否是交易日
                if specified_date in all_trading_dates:
                    t_date = specified_date
                    print(f"指定日期 {t_date.strftime('%Y-%m-%d')} 是交易日，将作为T日。")
                else:
                    # 如果不是交易日，找到早于指定日期的最近一个交易日
                    # all_trading_dates 是按日期降序排列的
                    for trade_date in all_trading_dates:
                        if trade_date < specified_date:
                            t_date = trade_date
                            break
                    if t_date:
                        print(f"指定日期 {specified_date.strftime('%Y-%m-%d')} 不是交易日，最近的交易日是 {t_date.strftime('%Y-%m-%d')}，将作为T日。")
                    else:
                        # 理论上不太可能，但如果回溯范围内没有更早的交易日
                        t_date = all_trading_dates[0] # 使用最新的交易日
                        print(f"在回溯范围内未找到早于指定日期的交易日，使用最新的交易日 {t_date.strftime('%Y-%m-%d')} 作为T日。")
                        
            except ValueError as e:
                print(f"配置文件中的 EndDate 格式错误 ({specified_end_date_str})，将忽略该设置: {e}")
                specified_end_date_str = None # 重置，使用默认逻辑
        
        # 如果没有指定日期或指定日期无效，则使用最新的交易日
        if t_date is None:
            t_date = all_trading_dates[0]
            print(f"未指定有效结束日期，使用最新交易日 {t_date.strftime('%Y-%m-%d')} 作为T日。")
        # --- 结束 ---
        
        # 确定T-5日 (需要最近的6个交易日)
        # 从 all_trading_dates 中找到 t_date 及之前的所有交易日，取最近的6个
        relevant_trading_dates = [d for d in all_trading_dates if d <= t_date]
        relevant_trading_dates.sort() # 升序排列
        
        if len(relevant_trading_dates) < 6:
             raise Exception(f"在T日({t_date})之前只找到 {len(relevant_trading_dates)} 个交易日，不足6个。")
        
        # 取最后6个
        final_trading_dates = relevant_trading_dates[-6:]
        t_minus_5_date = final_trading_dates[0]   # T-5日
        
        # 打印确认后的日期范围
        last_date_str = t_date.strftime('%Y-%m-%d') # T日
        six_days_ago_str = t_minus_5_date.strftime('%Y-%m-%d') # T-5日
        print(f"确定的最近6个交易日: {[d.strftime('%Y-%m-%d') for d in final_trading_dates]}")
        print(f"实际分析日期范围: {six_days_ago_str} 至 {last_date_str}")
        
    except Exception as e:
        print(f"获取交易日历或确定T日失败: {e}")
        raise

    # ----------------------------
    # 核心策略查询 (使用 stock_data.daily_k)
    # ----------------------------
    print("正在执行策略查询...")
    
    # 核心查询：获取原始数据用于处理
    # 1. 获取最近6天正常交易的股票列表
    # 2. 识别这些股票中的涨停情况
    # 3. 筛选只出现一次涨停且在T-5至T-2之间的股票
    query = """
    WITH 
        -- 1. 获取最近6天正常交易的股票 (tradestatus = 1)
        -- daily_k 和 index_k 表的 code 列都是 'sh.600000' 格式
        valid_stocks AS (
            SELECT code -- daily_k 表使用 code 列 ('sh.600000')
            FROM (
                SELECT code, tradestatus
                FROM stock_data.daily_k
                WHERE date >= %(start_date)s AND date <= %(end_date)s
            )
            GROUP BY code
            HAVING count() = 6 AND sum(tradestatus = 0) = 0 -- 6天记录且无停牌
        ),
        
        -- 2. 为有效股票定义板块涨跌幅限制 (根据 code 前缀)
        board_limits AS (
            SELECT 
                code,
                if(
                    code LIKE 'sh.600%%' OR code LIKE 'sh.601%%' OR code LIKE 'sh.603%%' OR
                    code LIKE 'sz.00%%' OR code LIKE 'sz.001%%' OR code LIKE 'sz.002%%' OR code LIKE 'sz.003%%',
                    0.10, 
                    0.20
                ) AS limit_ratio
            FROM valid_stocks
        ),
        
        -- 3. 标记所有有效股票在分析期间的涨停日
        -- 注意：daily_k 表的列名是 code, date, open, high, low, close, preclose
        limit_up_days AS (
            SELECT 
                d.code, -- 使用 code 列 ('sh.600000')
                d.date AS trade_date, -- 使用 date 列
                d.open,
                d.high,
                d.low,
                d.close,
                d.preclose, -- 使用 preclose 列
                -- 判断是否涨停 (使用 preclose 和 limit_ratio)
                abs(d.high - round(d.preclose * (1 + bl.limit_ratio), 2)) < 0.011 AND 
                abs(d.close - d.high) < 0.001 AS is_limit_up
            FROM stock_data.daily_k d -- 使用正确的表名 stock_data.daily_k
            INNER JOIN board_limits bl ON d.code = bl.code -- 使用 code 列关联
            WHERE d.date >= %(start_date)s AND d.date <= %(end_date)s -- 使用 date 列
        ),
        
        -- 4. 识别符合条件的股票：最近6天只出现1次涨停，且在T-5至T-2之间
        qualified_stocks AS (
            SELECT 
                code,
                argMax(if(is_limit_up, trade_date, NULL), is_limit_up) AS first_limit_date,
                argMax(if(is_limit_up, close, NULL), is_limit_up) AS first_limit_close, -- 新增：获取首板收盘价
                sum(is_limit_up) AS limit_count
            FROM limit_up_days
            WHERE trade_date < %(last_date)s -- 排除T日
            GROUP BY code
            HAVING 
                limit_count = 1 AND
                first_limit_date >= toDate(%(start_date)s) AND -- 在T-5到T-1之间
                first_limit_date <= toDate(%(last_date)s) - 2 -- 不晚于T-2 (根据要求)
        )
    
    -- 5. 获取符合条件股票的完整6天数据
    SELECT 
        lud.code, -- 使用 code 列 ('sh.600000') - 保留原始格式
        qs.first_limit_date,
        qs.first_limit_close, -- 新增：选择首板收盘价
        lud.trade_date,
        lud.open,
        lud.close,
        lud.preclose, -- 使用 preclose 列
        if(lud.trade_date > qs.first_limit_date, 1, 0) AS is_post_limit
    FROM limit_up_days lud
    INNER JOIN qualified_stocks qs ON lud.code = qs.code -- 使用 code 列关联
    WHERE 
        lud.trade_date >= qs.first_limit_date - 1 AND -- 包含涨停前1天用于计算涨幅
        lud.trade_date <= %(last_date)s -- 到T日结束
    ORDER BY lud.code, lud.trade_date
    """
    
    # 执行查询
    try:
        results = client.execute(
            query, 
            {
                'start_date': six_days_ago_str, # T-5日
                'end_date': last_date_str,      # T日
                'last_date': last_date_str      # T日
            },
            with_column_types=True
        )
    except Exception as e:
        print(f"执行策略查询失败: {e}")
        raise
    
    # 处理结果
    if not results[0]: # 检查是否有数据
        print("策略查询未返回任何数据。")
        # 创建空的DataFrame用于输出
        empty_df = pd.DataFrame(columns=[
            '股票代码', '股票名称', '行业', '首板日期', '首板价格', '回调周期',
            '板后走势', '板后最高价', '板后最低价',
            '最高价日期', '最低价日期', '板后回调(%)'
        ])
        try:
            with pd.ExcelWriter('result.xlsx', engine='xlsxwriter') as writer:
                empty_df.to_excel(writer, sheet_name='results', index=False)
                empty_df.to_excel(writer, sheet_name='candidates', index=False)
            print("策略执行完成，但未筛选出任何符合条件的首板股票，已生成空的结果文件 result.xlsx。")
        except Exception as e:
            print(f"保存空结果文件失败: {e}")
        return
        
    columns = [col[0] for col in results[1]]
    df = pd.DataFrame(results[0], columns=columns)
    
    # --- 创建两个结果列表 ---
    # 1. 存储所有符合条件的首板股票结果
    all_first_limit_up_results = []
    # 2. 存储筛选出的'稳定回调'股票结果
    stable_callback_results = []
    # --- 结束 ---
    
    # 按股票代码分组处理
    print(f"正在处理 {df['code'].nunique()} 只符合条件的股票数据...")
    
    for full_code, group in df.groupby('code'): # full_code 例如 'sh.600000'
        # 从完整代码提取6位数字代码，仅用于匹配 AllA.xlsx
        code_6d = extract_6digit_code(full_code) # 例如 '600000'
        if not code_6d:
            print(f"警告：无法从代码 '{full_code}' 提取6位数字，跳过。")
            continue
            
        # 获取股票名称和行业 (使用6位数字代码匹配)
        stock_info = stock_info_dict.get(code_6d, {
            '股票名称': '未知',
            '行业': '未知'
        })
        
        # 确定首板日期和首板价格
        first_limit_date = group['first_limit_date'].iloc[0]
        first_limit_close = group['first_limit_close'].iloc[0] # 获取首板收盘价
        
        # 获取首板前收盘价（用于计算涨幅）
        limit_row = group[group['trade_date'] == first_limit_date]
        if limit_row.empty:
            continue
        limit_pre_close = limit_row['preclose'].values[0] # 使用 preclose
        
        # 计算涨停涨幅
        limit_gain = first_limit_close - limit_pre_close # 使用首板收盘价和前收盘价
        
        # 获取板后数据（trade_date > first_limit_date）
        post_limit_df = group[group['trade_date'] > first_limit_date].copy()
        post_limit_days = len(post_limit_df)
        
        if post_limit_days == 0:
            # 根据策略筛选条件（T-5到T-2涨停，T日为终点），这种情况理论上不会发生
            # 为保持一致性，我们仍创建一个记录
            post_high = np.nan
            post_low = np.nan
            high_date_str = ''
            low_date_str = ''
            callback_ratio = np.nan
            trend = '无后续交易日' # 或者 '数据异常'
        else:
            # 找出板后最高价和最低价（开盘价和收盘价）
            # 构造一个包含日期、价格、价格类型的列表
            all_prices_with_info = []
            for _, row in post_limit_df.iterrows():
                all_prices_with_info.append({
                    'date': row['trade_date'],
                    'price': row['open'],
                    'type': '开盘价'
                })
                all_prices_with_info.append({
                    'date': row['trade_date'],
                    'price': row['close'],
                    'type': '收盘价'
                })
            
            if not all_prices_with_info:
                 # 理论上不会发生，但做防御性编程
                post_high = np.nan
                post_low = np.nan
                high_date_str = ''
                low_date_str = ''
                callback_ratio = np.nan
                trend = '数据异常'
            else:
                # 按价格排序找最高价
                all_prices_with_info.sort(key=lambda x: x['price'], reverse=True)
                post_high_info = all_prices_with_info[0]
                post_high = post_high_info['price']
                high_date = post_high_info['date']
                high_type = post_high_info['type']
                
                # 按价格排序找最低价
                all_prices_with_info.sort(key=lambda x: x['price'])
                post_low_info = all_prices_with_info[0]
                post_low = post_low_info['price']
                low_date = post_low_info['date']
                low_type = post_low_info['type']
                
                # 格式化日期为"YYYYMMDD开盘价/收盘价"格式
                high_date_str = high_date.strftime('%Y%m%d') + high_type
                low_date_str = low_date.strftime('%Y%m%d') + low_type
                
                # 计算回调幅度
                if limit_gain > 0.001:
                    callback_ratio = (first_limit_close - post_low) / limit_gain # 使用首板收盘价
                else:
                    callback_ratio = np.nan
                
                # 判断走势 (与原shouban.txt逻辑一致)
                if post_high > first_limit_close: # 使用首板收盘价
                    trend = '继续新高'
                elif pd.isna(callback_ratio) or callback_ratio < 0:
                     trend = '异常' # 或 '数据异常'
                elif lower_limit <= callback_ratio <= upper_limit: # 使用配置的上下限
                    trend = '稳定回调'
                elif callback_ratio > upper_limit:
                    trend = '过度回调'
                else:
                    trend = '微弱回调'
        
        # --- 创建股票结果字典 ---
        # 修改：输出时使用原始的 full_code
        stock_result = {
            '股票代码': full_code, # 修改：输出原始格式的股票代码
            '股票名称': stock_info['股票名称'],
            '行业': stock_info['行业'],
            '首板日期': first_limit_date.strftime('%Y-%m-%d'),
            '首板价格': round(first_limit_close, 2), # 新增：首板收盘价
            '回调周期': post_limit_days,
            '板后走势': trend,
            '板后最高价': round(post_high, 2) if not pd.isna(post_high) else np.nan,
            '板后最低价': round(post_low, 2) if not pd.isna(post_low) else np.nan,
            '最高价日期': high_date_str,
            '最低价日期': low_date_str,
            '板后回调': round(callback_ratio * 100, 2) if not pd.isna(callback_ratio) else np.nan
        }
        # 将所有首板股结果加入 all_first_limit_up_results
        all_first_limit_up_results.append(stock_result)
        
        # 只有'稳定回调'的股票加入 stable_callback_results
        if trend == '稳定回调':
            stable_callback_results.append(stock_result)
        # --- 结束 ---
    
    # --- 准备并输出Excel文件 ---
    print(f"数据处理完成。")
    print(f"  - 共筛选出 {len(all_first_limit_up_results)} 只符合条件的首板股票。")
    print(f"  - 其中 {len(stable_callback_results)} 只为'稳定回调'。")
    
    # 定义期望的列顺序和最终列名 (重命名前的列名必须与 DataFrame 的列名一致)
    column_order_before_rename = [
        '股票代码', '股票名称', '行业', '首板日期', '首板价格', '回调周期',
        '板后走势', '板后最高价', '板后最低价',
        '最高价日期', '最低价日期', '板后回调'
    ]
    # final_column_names = [
    #     '股票代码', '股票名称', '行业', '首板日期', '首板价格', '回调周期',
    #     '板后走势', '板后最高价', '板后最低价',
    #     '最高价日期', '最低价日期', '板后回调(%)'
    # ]
    
    # 重命名映射
    rename_dict = {
        '板后回调': '板后回调(%)'
    }
    
    # 函数：安全地准备 DataFrame
    def prepare_dataframe(data_list):
        if data_list:
            df = pd.DataFrame(data_list)
        else:
            # 创建空的DataFrame，列名与期望的一致
            df = pd.DataFrame(columns=column_order_before_rename)
        
        # 确保所有期望的列都存在，缺失的用 NaN 填充
        for col in column_order_before_rename:
            if col not in df.columns:
                df[col] = np.nan
                
        # 按期望的顺序选择和排列列，然后重命名
        df = df[column_order_before_rename].rename(columns=rename_dict)
        return df

    # 准备两个DataFrame
    stable_callback_df = prepare_dataframe(stable_callback_results)
    all_first_limit_df = prepare_dataframe(all_first_limit_up_results)

    # 保存到Excel，包含两个sheet
    try:
        with pd.ExcelWriter('result.xlsx', engine='xlsxwriter') as writer:
            stable_callback_df.to_excel(writer, sheet_name='results', index=False)
            all_first_limit_df.to_excel(writer, sheet_name='candidates', index=False)
        
        print("结果已保存至 result.xlsx，包含 'results' 和 'candidates' 两个Sheet。")
        
    except Exception as e:
        print(f"保存Excel文件失败: {e}")
    # --- 结束 ---

# ----------------------------
# 5. 执行
# ----------------------------
if __name__ == '__main__':
    print("开始执行首板回调策略...")
    try:
        execute_strategy()
    except Exception as e:
        print(f"策略执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
    print("策略执行完成。")