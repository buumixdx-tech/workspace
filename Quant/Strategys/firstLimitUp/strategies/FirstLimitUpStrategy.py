import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

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
        # 确保specified_end_date_str格式为YYYY-MM-DD
        self.specified_end_date_str = convert_date_format(self.specified_end_date_str, 2)
        
        # 用于存储SQL执行返回的完整结果，可用于save_results输出执行报告，由_process_results赋值
        self._full_results_df: pd.DataFrame = pd.DataFrame()
        # 用于存储 run() 执行生成的结果，一个股票代码列表
        self._simple_results_df: pd.DataFrame = pd.DataFrame()
        # 用于存储 T 日，格式标准化为YYYY-MM-DD字符串
        self._t_date_str = convert_date_format(get_t_date(db, convert_date_format(self.specified_end_date_str, 1)), 2)

    def run(self) -> pd.DataFrame:
        """
        执行首板回调策略的核心逻辑。

        执行流程：
        1. 更新 ClickHouse 参数表：strategy_flu_params
        2. 若指定了 stock_codes，则更新股票池表：strategy_flu_stock_pool
        3. 根据是否指定股票池，选择对应的 View 执行
        4. 返回标准化结果：['策略日期', '股票代码']

        :return: pd.DataFrame，包含两列：['策略日期', '股票代码']
        """
        print(f"开始执行策略: {self.get_name()}")
        # self._pre_run_hook()
        
        try:
            # --- 1. 更新参数表 ---
            try:
                # 确保是 float
                upper_limit_clean = np.float64(self.upper_limit)
                lower_limit_clean = np.float64(self.lower_limit)

                # 清空旧参数
                self.db.execute("TRUNCATE TABLE stock_data.strategy_flu_params")

                # 列式插入：每一列是一个列表
                self.db.client.execute(
                    "INSERT INTO stock_data.strategy_flu_params (end_date, upper_limit, lower_limit) VALUES",
                    [
                        np.array([self._t_date_str], dtype='object'),        # 字符串列
                        np.array([self.upper_limit], dtype='float64'),       # float64 列
                        np.array([self.lower_limit], dtype='float64')        # float64 列
                    ],
                    columnar=True
                )

                print("✅ 参数已更新到 stock_data.strategy_flu_params")
            except Exception as e:
                print(f"❌ 更新参数表失败: {e}")
                raise

            # --- 2. 加载辅助数据（如股票名称、行业）---
            stock_info_dict = load_stock_info()

            # --- 3. 更新股票池表（如需要）并选择 View ---
            if self.stock_codes and len(self.stock_codes) > 0:
                # 清空并写入股票池
                self.db.execute("TRUNCATE TABLE stock_data.strategy_flu_stock_pool")
                self.db.client.execute(
                    "INSERT INTO stock_data.strategy_flu_stock_pool (code) VALUES",
                    [
                        np.array(self.stock_codes, dtype='object')  # 字符串列
                    ],
                    columnar=True
                )
                print(f"✅ 股票池已设置，共 {len(self.stock_codes)} 只股票")
                # 使用股票池视图
                query = "SELECT * FROM stock_data.view_strategy_flu_pool"
            else:
                print("🌍 全市场选股")
                # 使用全市场视图
                query = "SELECT * FROM stock_data.view_strategy_flu"

            # --- 4. 执行查询 ---
            print("📊 正在执行策略查询...")
            results = self.db.fetch_all(query)

            # --- 5. 处理空结果 ---
            if not results:
                print("⚠️  策略查询未返回任何数据。")
                self._full_results_df = pd.DataFrame()
                return pd.DataFrame(columns=['策略日期', '股票代码'])

            # --- 6. 定义视图输出列名（与 VIEW 保持一致）---
            sql_columns = [
                'code',                      # 股票代码
                'limit_up_close_price',     # 封板价
                'high_after_limit',         # 板后最高价
                'low_after_limit',          # 板后最低价
                'pre_limit_up_preclose',    # 涨停前一日收盘价
                'high_drawdown',            # 从封板价到板后最高价的回撤比例
                'low_drawdown'              # 从封板价到板后最低价的回撤比例
            ]
            df_sql_results = pd.DataFrame(results, columns=sql_columns)

            # --- 7. 数据处理与丰富（调用已有方法）---
            run_df = self._process_results(df_sql_results, stock_info_dict)

            # --- 8. 存储完整结果用于后续保存 ---
            self._simple_results_df = run_df

            # --- 9. 构造最终返回结果 ---
            if not run_df.empty:
                run_df['策略日期'] = self._t_date_str
                run_df = run_df[['策略日期', '股票代码']]  # 保证列顺序
            else:
                run_df = pd.DataFrame(columns=['策略日期', '股票代码'])

            print(f"✅ 策略执行完成，共筛选出 {len(run_df)} 只股票。")
            return run_df

        except Exception as e:
            print(f"❌ 执行策略 {self.get_name()} 时发生错误: {e}")
            import traceback
            traceback.print_exc()
            self._full_results_df = pd.DataFrame()
            return pd.DataFrame(columns=['策略日期', '股票代码'])
    
    def _build_core_query(self) -> str:
        """构建核心 SQL 查询"""
        query = ""
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
            first_limit_close = row['limit_up_close_price']
            post_high = row['high_after_limit']
            post_low = row['low_after_limit']
            callback_min_percent = row['low_drawdown']
            callback_max_percent = row['high_drawdown']
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
