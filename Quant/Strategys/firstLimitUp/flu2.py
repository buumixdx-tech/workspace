# flu2.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from clickhouse_driver import Client
from typing import List, Dict, Any, Tuple, Optional
import os

# 从 utils 模块导入所有需要的工具函数
from modules.utils import (
    get_clickhouse_client,
    get_config_specified, # 如果你仍然想用这个特定的配置读取函数
    get_config,          # 通用的配置读取函数
    load_stock_info,
    extract_6digit_code,
    get_t_date,
    get_n_before_T_date,
    fetch_trading_calendar
)

# ----------------------------
# 5. 主策略查询
# ----------------------------
def execute_strategy():
    """
    执行首板回调策略，使用 index_k 作为交易日历，daily_k 作为个股数据源
    """
    # --- 获取配置 ---
    # 你可以选择使用哪个配置函数，或者根据你的 config.txt 格式进行调整
    # 方式1: 使用 get_config_specified (针对特定格式)
    # config_specified = get_config_specified()
    # lower_limit = config_specified['lower_limit']
    # upper_limit = config_specified['upper_limit']
    # specified_end_date_str = config_specified['end_date']

    # 方式2: 使用 get_config (更通用)
    config_general = get_config('config.txt') # 明确指定配置文件路径
    # get_config 会自动将 X% 转换为 X/100.0 的浮点数
    lower_limit = config_general.get('lower_limit', 0.10) # 默认10%
    upper_limit = config_general.get('upper_limit', 0.75) # 默认75%
    # get_config 读取的 end_date 会是原始字符串 (如 '20231201' 或 None)
    specified_end_date_str_from_config = config_general.get('end_date', None) 
    # 如果配置文件中的 end_date 是字符串，需要进一步处理
    if isinstance(specified_end_date_str_from_config, str) and specified_end_date_str_from_config.isdigit() and len(specified_end_date_str_from_config) == 8:
        specified_end_date_str = specified_end_date_str_from_config
    elif specified_end_date_str_from_config is None:
        specified_end_date_str = None
    else:
        print(f"警告：配置文件中的 end_date '{specified_end_date_str_from_config}' 格式不正确，将忽略。")
        specified_end_date_str = None

    # --- 结束获取配置 ---

    # 获取全市场股票基本信息 (Key: 6位数字代码)
    try:
        stock_info_dict = load_stock_info()
        print(f"成功加载 {len(stock_info_dict)} 只股票的基本信息。")
    except FileNotFoundError as e:
        print(f"错误：{e}")
        return # 或 raise
    except Exception as e:
        print(f"加载股票信息时发生未知错误: {e}")
        return

    # 创建ClickHouse客户端
    try:
        client = get_clickhouse_client()
        print("成功连接到ClickHouse数据库。")
    except Exception as e:
        print(f"连接ClickHouse数据库失败: {e}")
        return # 或 raise

    # ----------------------------
    # 获取交易日历，确定T日和T-5日
    # ----------------------------
    try:
        t_date_str, t_minus_5_date_str = get_n_before_T_date(client, 6, specified_end_date_str)
        print(f"分析日期范围已确定: T-5 ({t_minus_5_date_str}) 至 T ({t_date_str})")
    except Exception as e:
        print(f"获取交易日历或确定日期范围失败: {e}")
        return # 或 raise

    # --- 结束 ---

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
                'start_date': t_minus_5_date_str, # T-5日
                'end_date': t_date_str,      # T日
                'last_date': t_date_str      # T日
            },
            with_column_types=True
        )
        print("策略查询执行成功。")
    except Exception as e:
        print(f"执行策略查询失败: {e}")
        # import traceback
        # traceback.print_exc()
        return # 或 raise

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
    print(f"查询返回 {len(df)} 条记录，涉及 {df['code'].nunique()} 只股票。")
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
            print(f"警告：股票 {full_code} 的首板日期 {first_limit_date} 数据缺失，跳过。")
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
            '板后回调(%)': round(callback_ratio * 100, 2) if not pd.isna(callback_ratio) else np.nan # 重命名
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

    # 定义期望的列顺序
    column_order = [
        '股票代码', '股票名称', '行业', '首板日期', '首板价格', '回调周期',
        '板后走势', '板后最高价', '板后最低价',
        '最高价日期', '最低价日期', '板后回调(%)'
    ]

    # 函数：安全地准备 DataFrame
    def prepare_dataframe(data_list):
        if data_list:
            df = pd.DataFrame(data_list)
        else:
            # 创建空的DataFrame，列名与期望的一致
            df = pd.DataFrame(columns=column_order)
        # 确保所有期望的列都存在，缺失的用 NaN 填充
        for col in column_order:
            if col not in df.columns:
                df[col] = np.nan
        # 按期望的顺序选择和排列列
        df = df[column_order]
        return df

    # 准备两个DataFrame
    stable_callback_df = prepare_dataframe(stable_callback_results)
    all_first_limit_df = prepare_dataframe(all_first_limit_up_results)

    # 保存到Excel，包含两个sheet
    try:
        output_file = 'result.xlsx'
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            stable_callback_df.to_excel(writer, sheet_name='results', index=False)
            all_first_limit_df.to_excel(writer, sheet_name='candidates', index=False)
        print(f"结果已保存至 {output_file}，包含 'results' 和 'candidates' 两个Sheet。")
    except Exception as e:
        print(f"保存Excel文件失败: {e}")
        # import traceback
        # traceback.print_exc()
    # --- 结束 ---

# ----------------------------
# 6. 执行
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
