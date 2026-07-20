# first_limit_strategy.py
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta, date
import re
from clickhouse_driver import Client
from typing import List, Dict, Any

# 假设 strategy_interface.py 在同一目录下或在 Python 路径中
from strategy_interface import StockSelectionStrategy


# ----------------------------
# 工具函数 (从 flu1.txt 提取并稍作调整)
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


def load_stock_info():
    """
    从AllA.xlsx加载股票代码、名称和行业信息
    AllA.xlsx 中的代码是纯6位数字
    """
    if not os.path.exists('AllA.xlsx'):
        # 注意：在策略中，我们不抛出异常，而是返回空字典，让执行引擎处理
        print("警告：找不到AllA.xlsx文件，股票名称和行业将显示为'未知'")
        return {}
    try:
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
    except Exception as e:
        print(f"加载 AllA.xlsx 时出错: {e}")
        return {}


def extract_6digit_code(full_code):
    """
    从 'sh.600000' 或 'sz.000001' 提取 '600000'
    此函数仅用于从数据库代码匹配 AllA.xlsx 信息，不用于最终输出
    """
    match = re.search(r'\.(\d{6})$', full_code)
    return match.group(1) if match else None


def _get_config_limits(config_path='config.txt'):
    """
    从config.txt读取回调幅度上下限
    格式:
    UpperLimit:75%
    LowerLimit:10%
    EndDate:20250806 (可选，策略不使用)
    """
    # 默认配置
    config = {
        'lower_limit': 0.10,  # 默认10%
        'upper_limit': 0.75,  # 默认75%
    }
    if os.path.exists(config_path):
        # print("正在读取 config.txt...") # 策略内部日志可简化或移至DEBUG级别
        try:
            # 显式指定 encoding='utf-8' 以避免编码问题
            with open(config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip() # 去除首尾空白字符
                    if not line or ':' not in line: # 跳过空行和无冒号的行
                        continue
                    parts = line.split(':', 1) # 只分割一次
                    key = parts[0].strip()
                    value_raw = parts[1].strip()
                    if not value_raw:
                         continue
                    if key == 'LowerLimit':
                        if value_raw.endswith('%'):
                            try:
                                # 直接移除末尾的 '%' 并转换为小数
                                percent_value = float(value_raw[:-1])
                                config['lower_limit'] = percent_value / 100.0
                            except ValueError:
                                pass # 忽略无效值
                        # else: # 可选：打印警告
                    elif key == 'UpperLimit':
                        if value_raw.endswith('%'):
                            try:
                                percent_value = float(value_raw[:-1])
                                config['upper_limit'] = percent_value / 100.0
                            except ValueError:
                                pass # 忽略无效值
                        # else: # 可选：打印警告
                    # elif key == 'EndDate': # 策略不关心 EndDate
                    # else: # 可选：打印警告未知配置项
        except Exception as e:
            print(f"读取 {config_path} 时发生错误，使用默认值: {str(e)}")
    return config


# ----------------------------
# 策略实现类
# ----------------------------

class FirstLimitCallbackStrategy(StockSelectionStrategy):
    """
    首板回调策略实现。
    """

    def __init__(self, config_path='config.txt'):
        """
        初始化策略，读取配置。
        """
        self.config_path = config_path
        self.config = _get_config_limits(self.config_path)
        # 可以在这里加载 stock_info_dict 等不变数据
        self.stock_info_dict = load_stock_info()
        # print(f"首板回调策略初始化完成，参数: {self.get_parameters()}") # 可选日志

    def get_name(self) -> str:
        return "首板回调策略"

    def get_parameters(self) -> Dict[str, Any]:
        return {
            'upper_limit': self.config['upper_limit'],
            'lower_limit': self.config['lower_limit']
        }

    def select_stocks(self, t_date: date) -> List[Dict[str, Any]]:
        """
        实现 StockSelectionStrategy 接口的 select_stocks 方法。
        根据给定的T日执行选股逻辑。
        """
        print(f"[{self.get_name()}] 开始选股，T日为: {t_date.strftime('%Y-%m-%d')}")
        # 获取配置参数
        lower_limit = self.config['lower_limit']
        upper_limit = self.config['upper_limit']
        stock_info_dict = self.stock_info_dict

        # 创建ClickHouse客户端
        client = get_clickhouse_client()

        # ----------------------------
        # 获取交易日历并确定分析日期范围 (T-5 至 T)
        # ----------------------------
        # print("正在获取交易日历并确定分析日期范围...")
        try:
            # 获取足够多的交易日用于确定T日及之前的5天 (最多回溯30天)
            lookback_days = 30
            end_date_for_query = t_date # T日
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
            all_trading_dates.sort() # 升序排列

            # 找到 t_date 及之前的所有交易日，取最近的6个 (T-5 到 T)
            relevant_trading_dates = [d for d in all_trading_dates if d <= t_date]
            if len(relevant_trading_dates) < 6:
                 raise Exception(f"在T日({t_date})之前只找到 {len(relevant_trading_dates)} 个交易日，不足6个。")

            # 取最后6个
            final_trading_dates = relevant_trading_dates[-6:]
            t_minus_5_date = final_trading_dates[0]   # T-5日

            # 确认日期范围
            last_date_str = t_date.strftime('%Y-%m-%d') # T日
            six_days_ago_str = t_minus_5_date.strftime('%Y-%m-%d') # T-5日
            # print(f"确定的最近6个交易日: {[d.strftime('%Y-%m-%d') for d in final_trading_dates]}")
            # print(f"实际分析日期范围: {six_days_ago_str} 至 {last_date_str}")
        except Exception as e:
            print(f"[{self.get_name()}] 获取交易日历或确定日期范围失败: {e}")
            raise # 重新抛出异常，让执行引擎处理

        # ----------------------------
        # 核心策略查询 (使用 stock_data.daily_k)
        # ----------------------------
        # print("正在执行策略查询...")
        # 核心查询：获取原始数据用于处理
        query = """
        WITH 
            -- 1. 获取最近6天正常交易的股票 (tradestatus = 1)
            valid_stocks AS (
                SELECT code
                FROM (
                    SELECT code, tradestatus
                    FROM stock_data.daily_k
                    WHERE date >= %(start_date)s AND date <= %(end_date)s
                )
                GROUP BY code
                HAVING count() = 6 AND sum(tradestatus = 0) = 0 -- 6天记录且无停牌
            ),
            -- 2. 为有效股票定义板块涨跌幅限制
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
            limit_up_days AS (
                SELECT 
                    d.code,
                    d.date AS trade_date,
                    d.open,
                    d.high,
                    d.low,
                    d.close,
                    d.preclose,
                    abs(d.high - round(d.preclose * (1 + bl.limit_ratio), 2)) < 0.011 AND 
                    abs(d.close - d.high) < 0.001 AS is_limit_up
                FROM stock_data.daily_k d
                INNER JOIN board_limits bl ON d.code = bl.code
                WHERE d.date >= %(start_date)s AND d.date <= %(end_date)s
            ),
            -- 4. 识别符合条件的股票：最近6天只出现1次涨停，且在T-5至T-2之间
            qualified_stocks AS (
                SELECT 
                    code,
                    argMax(if(is_limit_up, trade_date, NULL), is_limit_up) AS first_limit_date,
                    argMax(if(is_limit_up, close, NULL), is_limit_up) AS first_limit_close,
                    sum(is_limit_up) AS limit_count
                FROM limit_up_days
                WHERE trade_date < %(last_date)s -- 排除T日
                GROUP BY code
                HAVING 
                    limit_count = 1 AND
                    first_limit_date >= toDate(%(start_date)s) AND -- 在T-5到T-1之间
                    first_limit_date <= toDate(%(last_date)s) - 2 -- 不晚于T-2
            )
        -- 5. 获取符合条件股票的完整6天数据
        SELECT 
            lud.code,
            qs.first_limit_date,
            qs.first_limit_close,
            lud.trade_date,
            lud.open,
            lud.close,
            lud.preclose,
            if(lud.trade_date > qs.first_limit_date, 1, 0) AS is_post_limit
        FROM limit_up_days lud
        INNER JOIN qualified_stocks qs ON lud.code = qs.code
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
            print(f"[{self.get_name()}] 执行策略查询失败: {e}")
            raise # 重新抛出异常

        # 处理结果
        if not results[0]: # 检查是否有数据
            print(f"[{self.get_name()}] 策略查询未返回任何数据。")
            return [] # 返回空列表

        columns = [col[0] for col in results[1]]
        df = pd.DataFrame(results[0], columns=columns)

        # --- 创建结果列表 ---
        # 存储筛选出的'稳定回调'股票结果
        stable_callback_results = []

        # --- 按股票代码分组处理 ---
        # print(f"正在处理 {df['code'].nunique()} 只符合条件的股票数据...")
        for full_code, group in df.groupby('code'):
            # 从完整代码提取6位数字代码，仅用于匹配 AllA.xlsx
            code_6d = extract_6digit_code(full_code)
            if not code_6d:
                print(f"[{self.get_name()}] 警告：无法从代码 '{full_code}' 提取6位数字，跳过。")
                continue

            # 获取股票名称和行业 (使用6位数字代码匹配)
            stock_info = stock_info_dict.get(code_6d, {
                '股票名称': '未知',
                '行业': '未知'
            })

            # 确定首板日期和首板价格
            first_limit_date = group['first_limit_date'].iloc[0]
            first_limit_close = group['first_limit_close'].iloc[0]

            # 获取首板前收盘价（用于计算涨幅）
            limit_row = group[group['trade_date'] == first_limit_date]
            if limit_row.empty:
                continue
            limit_pre_close = limit_row['preclose'].values[0]

            # 计算涨停涨幅
            limit_gain = first_limit_close - limit_pre_close

            # 获取板后数据（trade_date > first_limit_date）
            post_limit_df = group[group['trade_date'] > first_limit_date].copy()
            post_limit_days = len(post_limit_df)

            if post_limit_days == 0:
                # 理论上不会发生，但做防御性编程
                post_high = np.nan
                post_low = np.nan
                high_date_str = ''
                low_date_str = ''
                callback_ratio = np.nan
                trend = '无后续交易日'
            else:
                # 找出板后最高价和最低价（开盘价和收盘价）
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
                     # 理论上不会发生
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
                        callback_ratio = (first_limit_close - post_low) / limit_gain
                    else:
                        callback_ratio = np.nan

                    # 判断走势
                    if post_high > first_limit_close:
                        trend = '继续新高'
                    elif pd.isna(callback_ratio) or callback_ratio < 0:
                         trend = '异常'
                    elif lower_limit <= callback_ratio <= upper_limit:
                        trend = '稳定回调'
                    elif callback_ratio > upper_limit:
                        trend = '过度回调'
                    else:
                        trend = '微弱回调'

            # --- 创建股票结果字典 ---
            # 输出时使用原始的 full_code
            stock_result = {
                '股票代码': full_code,
                '股票名称': stock_info['股票名称'],
                '行业': stock_info['行业'],
                '首板日期': first_limit_date.strftime('%Y-%m-%d'),
                '首板价格': round(first_limit_close, 2),
                '回调周期': post_limit_days,
                '板后走势': trend,
                '板后最高价': round(post_high, 2) if not pd.isna(post_high) else np.nan,
                '板后最低价': round(post_low, 2) if not pd.isna(post_low) else np.nan,
                '最高价日期': high_date_str,
                '最低价日期': low_date_str,
                '板后回调(%)': round(callback_ratio * 100, 2) if not pd.isna(callback_ratio) else np.nan
            }

            # 只有'稳定回调'的股票加入结果列表
            if trend == '稳定回调':
                stable_callback_results.append(stock_result)

        # --- 结束 ---
        print(f"[{self.get_name()}] 选股完成，共选出 {len(stable_callback_results)} 只'稳定回调'股票。")
        return stable_callback_results # 返回符合策略条件的股票列表
