import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
import os
import re

# 导入基类
from strategies.strategy_base import StrategyBase
# 导入数据库连接
from modules.db import ClickHouseDB
# 导入工具函数
from modules.utils import (
    load_stock_info,
    get_t_date,
    convert_date_format,
    extract_6digit_code # 确保这个函数可用
)

class FirstLimitUpStrategy(StrategyBase):
    """
    首板回调策略 (优化版 - SQL筛选稳定回调并存储完整结果)。

    策略逻辑：
    1. 选取在 T-5 到 T 日（共6个交易日）内连续正常交易的股票。
    2. 在这些股票中，筛选出在 T-5 到 T-2 日（共4个交易日）内，期间只出现过一次涨停的股票。
    3. 计算这些股票在首次涨停后的走势（最高价、最低价、回调幅度）。
    4. 在 SQL 中直接筛选出“稳定回调”的股票（回调幅度在配置范围内）。
    5. run() 返回精简的选股结果 ['策略日期', '股票代码']。
    6. 完整的分析结果存储在 self._full_results_df 中，供 save_results 使用。
    """

    def __init__(
        self, 
        db: ClickHouseDB, 
        config: Dict[str, Any], 
        stock_codes: Optional[List[str]] = None
    ):
        """
        初始化首板回调策略。
        """
        # 调用基类初始化
        super().__init__(db, config, stock_codes)

        # 从配置中提取策略特定参数
        self.lower_limit = self.config.get('lower_limit') 
        self.upper_limit = self.config.get('upper_limit') 
        self.specified_end_date_str = self.config.get('end_date', None)
        
        # 定义一个内部函数来解析百分比字符串
        def parse_percentage(value_str: str, name: str) -> float:
            """将 '70%' 或 '0.7' 格式的字符串解析为 0.0-1.0 的浮点数"""
            if not isinstance(value_str, str):
                raise ValueError(f"配置项 {name} 的值必须是字符串，当前类型: {type(value_str)}")
            
            value_str = value_str.strip()
            if value_str.endswith('%'):
                try:
                    percent_value = float(value_str[:-1])
                    return percent_value / 100.0
                except ValueError as e:
                    raise ValueError(f"无法解析 {name} 的百分比值 '{value_str}': {e}")
            else:
                try:
                    decimal_value = float(value_str)
                    return decimal_value
                except ValueError as e:
                    raise ValueError(f"无法解析 {name} 的小数值 '{value_str}': {e}")

        # 解析配置
        raw_lower_limit = self.config.get('lower_limit')
        raw_upper_limit = self.config.get('upper_limit')
        try:
            self.lower_limit = parse_percentage(raw_lower_limit, 'lower_limit')
            self.upper_limit = parse_percentage(raw_upper_limit, 'upper_limit')
        except ValueError as e:
            raise ValueError(f"配置解析错误: {e}")
        
        # 验证配置参数
        if not (self.lower_limit < self.upper_limit):
             raise ValueError(
                f"配置错误: lower_limit ({self.lower_limit}) 必须小于 upper_limit ({self.upper_limit})，"
            )
        # 确保specified_end_date_str格式为YYYYMMDD
        convert_date_format(self.specified_end_date_str, 1)
        
        # 用于存储SQL执行返回的完整结果，可用于save_results输出执行报告，由_process_results赋值
        self._full_results_df: pd.DataFrame = pd.DataFrame()
        # 用于存储 run() 执行生成的结果，一个股票代码列表
        self._simple_results_df: pd.DataFrame = pd.DataFrame()
        # 用于存储 T 日，格式标准化为YYYY-MM-DD字符串
        self._t_date_str = convert_date_format(get_t_date(db, self.specified_end_date_str), 2)

    def run(self) -> pd.DataFrame:
        """
        执行首板回调策略的核心逻辑。

        :return: 一个包含两列的 DataFrame：['策略日期', '股票代码']，代表筛选出的稳定回调股票。
                 策略日期是 T 日 (self._t_date_str)。
        """
        print(f"开始执行策略: {self.get_name()}")
        # self._pre_run_hook()

        try:
            # --- 1. 加载辅助数据 ---
            stock_info_dict = load_stock_info()
                        
            # --- 2. 构建核心 SQL 查询 ---
            query = self._build_core_query()
            # print("【DEBUG】日期:", self._t_date_str)

            # return self._simple_results_df
            # 设置 SQL 执行填入的参数
            params = {
                'end_date': self._t_date_str,
                'lower_limit_val': self.lower_limit,
                'upper_limit_val': self.upper_limit,
            }
            # 如果指定了股票范围，则添加到参数中
            if self.stock_codes is not None:
                for i, code in enumerate(self.stock_codes):
                    params[f'stock_code_{i}'] = code            
            
            # --- 3. 执行查询 ---
            results = self.db.fetch_all(query, params)

            # --- 4. 处理查询结果为空 ---
            if not results:
                print("策略查询未返回任何数据。")
                # 清空内部存储并返回空的指定格式 DataFrame
                self._full_results_df = pd.DataFrame()
                return pd.DataFrame(columns=['策略日期', '股票代码']) # 列名是 '策略日期'

            # 定义 SQL 返回的列名，也作为_full_results_df的列定义
            sql_columns = [
                'code',
                'first_limit_close',
                'post_limit_max_price',        # 对应 SQL 的 post_limit_max_price
                'post_limit_min_price',        # 对应 SQL 的 post_limit_min_price
                'first_limit_preclose',
                'callback_from_max_percent',   # 对应 SQL 的 callback_from_max_percent
                'callback_from_min_percent'    # 对应 SQL 的 callback_from_min_percent
            ]

            # 创建包含稳定回调股票结果的 DataFrame
            df_sql_results = pd.DataFrame(results, columns=sql_columns)

            # --- 5. 数据整理与丰富 (在 Python 中完成) ---
            # 获取完整的分析结果 DataFrame
            run_df = self._process_results(df_sql_results, stock_info_dict)

            # --- 6. 存储简单股票代码列表，供_process_results函数内部把完整结果给_full_results_df赋值，save_results使用 ---
            self._simple_results_df = run_df
            return run_df

        except Exception as e:
            print(f"执行策略 {self.get_name()} 时发生错误: {e}")
            import traceback
            traceback.print_exc()
            # 清空内部存储并返回空的指定格式 DataFrame
            self._full_results_df = pd.DataFrame()
            return pd.DataFrame(columns=['策略日期', '股票代码']) # 列名是 '策略日期'
    
    def _build_core_query(self) -> str:
        """构建核心 SQL 查询，实现基于最高点/最低点回撤的首板回调策略。"""
        query = """
        WITH
            -- 参数设置
            end_date AS (SELECT toDate(%(end_date)s) AS dt),
            upper_limit AS (SELECT %(upper_limit_val)s AS val), -- 回撤幅度上限
            lower_limit AS (SELECT %(lower_limit_val)s AS val),  -- 回撤幅度下限

            -- 确定 T 日及相关的交易日
            T_date AS (
                SELECT max(date) AS t_dt -- <-- 直接命名为 t_dt
                FROM stock_data.index_k
                WHERE date <= (SELECT dt FROM end_date)
            ),
            T_date_scalar AS (
                SELECT t_dt FROM T_date -- <-- 直接选择 t_dt
            ),
            relevant_trading_days AS (
                SELECT
                    date AS trade_date,
                    row_number() OVER (ORDER BY date DESC) AS days_ago_rank
                FROM (
                    SELECT DISTINCT date
                    FROM stock_data.daily_k
                    WHERE date <= (SELECT t_dt FROM T_date_scalar)
                ) AS unique_dates
                ORDER BY date DESC
                LIMIT 6
            ),

            -- 步骤 2: T-5 到 T 日连续交易的股票
            trading_days_T_5_to_T AS (
            SELECT trade_date
            FROM relevant_trading_days
            WHERE days_ago_rank BETWEEN 1 AND 6
            ),
            valid_stocks_step2 AS (
                SELECT k.code
                FROM stock_data.daily_k AS k
                INNER JOIN trading_days_T_5_to_T AS td ON k.date = td.trade_date
                WHERE k.tradestatus = 1
                GROUP BY k.code
                HAVING count(*) = 6
            ),

            -- 步骤 3: T-5 到 T-2 日有且仅有一次涨停的股票
            trading_days_T_5_to_T_2 AS (
                SELECT trade_date
                FROM relevant_trading_days
                WHERE days_ago_rank BETWEEN 3 AND 6 -- T-2 (rank=3) 到 T-5 (rank=6)
            ),
            stocks_with_one_limit_up AS (
                SELECT
                    k.code AS stock_code,
                    any(k.date) AS limit_up_date
                FROM stock_data.daily_k AS k
                INNER JOIN trading_days_T_5_to_T_2 AS td ON k.date = td.trade_date
                INNER JOIN valid_stocks_step2 AS vs ON k.code = vs.code
                WHERE k.price_status = 1 -- 涨停封板
                GROUP BY k.code
                HAVING count(*) = 1
            ),

            -- 步骤 4: 获取 L+1 到 T 日的数据 (用于计算价格区间和获取 pre_limit_up_preclose)
            trading_days_L_plus_1_to_T AS (
                SELECT k.code AS stock_code, k.date, k.open, k.close -- 仅选择 open 和 close
                FROM stock_data.daily_k AS k
                INNER JOIN stocks_with_one_limit_up AS lu ON k.code = lu.stock_code
                WHERE k.date BETWEEN lu.limit_up_date + 1 AND (SELECT t_dt FROM T_date_scalar)
                AND k.tradestatus = 1
            ),
            -- *** 修正点 1: 价格区间计算 ***
            price_ranges_after_limit AS (
                SELECT
                    stock_code,
                    -- 计算 L+1 日到 T 日所有 open 和 close 价格中的最高价 (区间上限)
                    greatest(max(open), max(close)) AS high_after_limit,
                    -- 计算 L+1 日到 T 日所有 open 和 close 价格中的最低价 (区间下限)
                    least(min(open), min(close)) AS low_after_limit
                FROM trading_days_L_plus_1_to_T
                GROUP BY stock_code
            ),
            -- 获取涨停日 (L日) 的信息：收盘价 (封板价) 和 前一日收盘价 (pre_limit_up_preclose)
            -- *** 修正点 2: 正确获取 pre_limit_up_preclose ***
            limit_up_info AS (
                SELECT
                    k.code AS stock_code,
                    k.close AS limit_up_close_price,        -- L 日收盘价 (封板价)
                    k.preclose AS pre_limit_up_preclose     -- L-1 日的收盘价
                FROM stock_data.daily_k AS k
                INNER JOIN stocks_with_one_limit_up AS lu ON k.code = lu.stock_code AND k.date = lu.limit_up_date
            )

        -- 步骤 5 & 6: 计算回撤幅度并筛选最终结果
        SELECT
            final_result.stock_code AS code,
            final_result.limit_up_close_price AS first_limit_close,
            final_result.high_after_limit AS post_limit_max_price,
            final_result.low_after_limit AS post_limit_min_price,
            final_result.pre_limit_up_preclose AS first_limit_preclose,
            final_result.high_drawdown AS callback_from_max_percent,
            final_result.low_drawdown AS callback_from_min_percent
        FROM (
            SELECT
                pr.stock_code,
                lu.limit_up_close_price,       -- L 日收盘价 (封板价)
                pr.high_after_limit,           -- L+1 到 T 日所有 open/close 中的最高价
                pr.low_after_limit,            -- L+1 到 T 日所有 open/close 中的最低价
                lu.pre_limit_up_preclose,      -- L-1 日的收盘价
                -- 计算板后最高价的回撤幅度
                (lu.limit_up_close_price - pr.high_after_limit) / (lu.limit_up_close_price - lu.pre_limit_up_preclose) AS high_drawdown,
                -- 计算板后最低价的回撤幅度
                (lu.limit_up_close_price - pr.low_after_limit) / (lu.limit_up_close_price - lu.pre_limit_up_preclose) AS low_drawdown
             FROM price_ranges_after_limit AS pr
             INNER JOIN limit_up_info AS lu ON pr.stock_code = lu.stock_code
             WHERE
                -- 防止除以零错误
                lu.limit_up_close_price <> lu.pre_limit_up_preclose
        """
        # 如果指定了股票代码列表，则添加筛选条件
        if self.stock_codes is not None:
            placeholders = ', '.join([f'%({f"stock_code_{i}"})s' for i in range(len(self.stock_codes))])
            query += f" AND pr.stock_code IN ({placeholders})\n"

        query += """
                AND
                -- 板后最高价的回撤幅度 >= lower_limit (0.1)
                ((lu.limit_up_close_price - pr.high_after_limit) / (lu.limit_up_close_price - lu.pre_limit_up_preclose)) >= (SELECT val FROM lower_limit)
                AND
                -- 板后最低价的回撤幅度 <= upper_limit (0.75)
                ((lu.limit_up_close_price - pr.low_after_limit) / (lu.limit_up_close_price - lu.pre_limit_up_preclose)) <= (SELECT val FROM upper_limit)
        ) AS final_result
        ORDER BY final_result.stock_code;
        """
        return query

    def _process_results(
        self, 
        df_sql_results: pd.DataFrame, 
        stock_info_dict: Dict[str, Dict[str, str]]
    ) -> pd.DataFrame: # 只返回一个 DataFrame
        """
        处理 SQL 查询返回的选股数据，生成完整版df，并返回简版df。
        """
        # 定义最终输出的完整列顺序
        full_column_order = [
            '股票代码', '股票简称', '所属行业', '首板价格', 
            '板后最高价', '板后最低价', '震荡下限(%)', '震荡上限(%)'
        ]
        
        full_results_data = []

        for _, row in df_sql_results.iterrows():
            full_code = row['code']
            
            # 提取6位数字代码
            code_6d = extract_6digit_code(full_code)
            if not code_6d:
                print(f"警告：无法从代码 '{full_code}' 提取6位数字，跳过。")
                continue

            # 获取股票名称和行业
            stock_info = stock_info_dict.get(code_6d, {'股票名称': '未知', '行业': '未知'})

            # 提取并格式化数据
            first_limit_close = row['first_limit_close']
            post_high = row['post_limit_max_price']
            post_low = row['post_limit_min_price']
            callback_min_percent = row['callback_from_min_percent']
            callback_max_percent = row['callback_from_max_percent']
            # 创建完整结果字典
            full_stock_result = {
                '股票代码': full_code,
                '股票简称': stock_info['股票名称'],
                '所属行业': stock_info['行业'],
                '首板价格': round(first_limit_close, 2),
                '板后最高价': round(post_high, 2) if not pd.isna(post_high) else np.nan,
                '板后最低价': round(post_low, 2) if not pd.isna(post_low) else np.nan,
                '震荡下限(%)': callback_min_percent,
                '震荡上限(%)': callback_max_percent,
            }
            full_results_data.append(full_stock_result)

        # 创建完整 DataFrame
        if full_results_data: 
            full_df = pd.DataFrame(full_results_data)
        else:
            full_df = pd.DataFrame(columns=full_column_order)
        # 保存完整版df
        self._full_results_df = full_df
        
        # 生成并返回简版df
        result_data = {
                    '策略日期': [self._t_date_str] * len(df_sql_results), # 每行都是 T 日
                    '股票代码': df_sql_results['code'].tolist()      # 对应的股票代码
                }
        simple_result_df = pd.DataFrame(result_data)
        # 确保列的顺序
        simple_result_df = simple_result_df[['策略日期', '股票代码']]
        return simple_result_df # 只返回 full_df

    # 可以根据需要覆盖钩子函数
    # def _pre_run_hook(self) -> None:
    #     print(f"[{self.get_name()}] 开始执行前的准备工作...")
    #     super()._pre_run_hook()

    # def _post_run_hook(self, results: pd.DataFrame) -> pd.DataFrame:
    #     print(f"[{self.get_name()}] 执行完成，共筛选出 {len(results)} 只稳定回调股票。")
    #     return super()._post_run_hook(results)
