# strategies/base.py
from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
from datetime import datetime
# 根据你的实际项目结构调整导入路径
from modules.db import ClickHouseDB
import pandas as pd
import os

class StrategyBase(ABC):
    """
    策略的抽象基类。

    所有具体的策略类都应继承自此类，并实现其抽象方法。
    提供了标准的初始化、运行接口。
    策略是否保存结果以及如何保存由外部调用者决定。
    """

    def __init__(
        self, 
        db: ClickHouseDB, 
        config: Dict[str, Any], 
        stock_codes: Optional[List[str]] = None
    ):
        """
        初始化策略基类。

        :param db: 已连接的 ClickHouseDB 实例，用于数据查询。
        :param config: 策略配置字典，包含策略运行所需的各种参数。
        :param stock_codes: 可选的股票代码列表 (e.g., ['sh.600000', 'sz.000001'])。
                            如果提供，策略将只在这些股票范围内选股。
                            如果为 None (默认)，策略将在所有股票范围内选股。
        :raises TypeError: 如果 db 或 config 类型不正确，或 stock_codes 不是列表。
        :raises ValueError: 如果 stock_codes 列表中包含非字符串元素。
        """
        if not isinstance(db, ClickHouseDB):
            raise TypeError("db 参数必须是 ClickHouseDB 的实例")
        
        if not isinstance(config, dict):
            raise TypeError("config 参数必须是字典类型")

        if stock_codes is not None:
            if not isinstance(stock_codes, list):
                raise TypeError("stock_codes 参数必须是列表或 None")
            # 检查列表内元素是否都是字符串
            if not all(isinstance(code, str) for code in stock_codes):
                raise ValueError("stock_codes 列表中的所有元素都必须是字符串")

        self.db = db
        self.config = config
        # 存储选股范围。None 表示所有股票。
        self.stock_codes = stock_codes 
        
        # 用于存储策略执行返回的完整结果，可用于save_results输出执行报告，由_process_results赋值
        self._full_results_df: pd.DataFrame = pd.DataFrame()
        # 用于存储 run() 执行生成的结果，一个股票代码列表
        self._simple_results_df: pd.DataFrame = pd.DataFrame()

        # 可以在这里添加从 config 中提取通用参数的逻辑
        # 例如: self.some_common_param = config.get('some_key', 'default_value')

    @abstractmethod
    def run(self) -> Any:
        """
        (抽象方法) 执行策略的核心逻辑。

        这是策略的主要入口点。子类必须实现此方法来定义具体的选股、计算和分析过程。
        可以利用 self.db, self.config, self.stock_codes 等属性。

        :return: 策略执行结果。可以是 DataFrame, List[Dict], Tuple, 或其他任何类型。
                 具体类型由子类定义。
        """
        pass

    def save_results(self, results: pd.DataFrame, output_path: Optional[str] = None) -> None:
        """
        保存首板回调策略的结果到 Excel 文件。
        使用存储在 self._full_results_df 中的完整数据。
        :param results: 由 run() 方法返回的精简结果 (此参数在此实现中未直接使用，但符合基类签名)。
        :param output_path: 可选的输出路径。如果为 None，则按规则自动生成。
        """
        # 检查是否有完整结果数据
        if self._full_results_df.empty:
             print("警告: 没有完整结果数据可供保存。")
             # 仍然可以创建一个只有参数的文件
             full_df_to_save = pd.DataFrame() # 空的 DataFrame
        else:
            full_df_to_save = self._full_results_df

        # --- 1. 准备参数 Sheet 数据 ---
        # 策略执行日期使用当前时间
        execution_time = datetime.now()
        params_data = {
            '参数名': [
                '策略执行日期',
                'T日',
                '回调下限',
                '回调上限'
            ],
            '参数值': [
                execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                self._t_date_str, # 使用实例变量
                f"{self.lower_limit:.1%}",
                f"{self.upper_limit:.1%}"
            ]
        }
        params_df = pd.DataFrame(params_data)

        # --- 2. 确定输出文件路径 ---
        if output_path is None:
            timestamp = execution_time.strftime('%Y%m%d_%H%M%S')
            filename = f"{self.get_name()}_{timestamp}.xlsx"
            # 确保 data/output 目录存在
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'output')
            os.makedirs(output_dir, exist_ok=True)
            final_output_path = os.path.join(output_dir, filename)
        else:
            final_output_path = output_path

        # --- 3. 保存到 Excel ---
        try:
            with pd.ExcelWriter(final_output_path, engine='xlsxwriter') as writer:
                # 保存完整结果到 'results' sheet
                full_df_to_save.to_excel(writer, sheet_name='results', index=False)
                # 保存参数到 'params' sheet
                params_df.to_excel(writer, sheet_name='params', index=False)
            print(f"首板回调策略结果已保存至 {final_output_path}")
        except Exception as e:
            print(f"保存首板回调策略结果失败: {e}")
            raise # 重新抛出异常，让调用者决定如何处理

    # 可以添加其他通用的辅助方法或钩子函数
    # 例如，策略运行前后的钩子
    def _pre_run_hook(self) -> None:
        """
        (钩子函数) 在 run() 方法执行前调用。
        子类可以覆盖此方法来执行预处理任务，例如日志记录、参数验证等。
        """
        # 基类默认不执行任何操作
        pass

    def _post_run_hook(self, results: Any) -> Any:
        """
        (钩子函数) 在 run() 方法执行后调用。
        子类可以覆盖此方法来对结果进行后处理，例如添加额外指标、数据清洗等。

        :param results: run() 方法返回的原始结果。
        :return: 处理后的结果。
        """
        # 基类默认不修改结果
        return results

    # 可以添加一个便捷方法来获取策略名称
    def get_name(self) -> str:
        """
        获取策略的名称（类名）。
        :return: 策略类的名称。
        """
        return self.__class__.__name__

# --- 使用说明 ---
#
# 1. 创建具体策略类
# -------------------
# 创建一个新的策略文件，例如 strategies/my_new_strategy.py
#
# from strategies.base import StrategyBase
# from typing import List, Dict, Any, Tuple # 根据需要导入
# import pandas as pd # 如果使用 DataFrame
#
# class MyNewStrategy(StrategyBase):
#     def __init__(self, db: ClickHouseDB, config: dict, stock_codes: List[str] = None):
#         super().__init__(db, config, stock_codes)
#         # 可以在这里处理特定于该策略的配置
#         # self.my_param = self.config.get('my_param_key', 'default_value')
#
#     def run(self) -> Any: # 例如 pd.DataFrame 或 Tuple[pd.DataFrame, ...]
#         print(f"开始执行策略: {self.get_name()}")
#         
#         # 1. (可选) 调用预处理钩子
#         self._pre_run_hook() 
#         
#         # 2. 核心逻辑
#         # --- 使用 self.db, self.config, self.stock_codes ---
#         # 示例：构建 SQL 查询，根据 self.stock_codes 添加筛选
#         query = "SELECT code, date, close FROM stock_data.daily_k WHERE date = '2023-10-26'"
#         params = {}
#         
#         if self.stock_codes is not None:
#             # 注意：实际应用中需要使用安全的参数化方法处理 IN 列表
#             # 例如: placeholders = ', '.join([f'%({i})s' for i in range(len(self.stock_codes))])
#             #      query += f" AND code IN ({placeholders})"
#             #      for i, code in enumerate(self.stock_codes): params[str(i)] = code
#             placeholders = ', '.join([f"'{code}'" for code in self.stock_codes])
#             query += f" AND code IN ({placeholders})"
#         
#         print(f"执行查询: {query}")
#         raw_results = self.db.fetch_all(query) # 假设 fetch_all 存在
#         
#         # 3. 数据处理 (示例)
#         if not raw_results:
#             print("查询未返回任何数据。")
#             return pd.DataFrame() # 或其他表示空结果的方式
#             
#         # 假设处理成 DataFrame
#         results_df = pd.DataFrame(raw_results, columns=['code', 'date', 'close'])
#         print(f"策略执行完成，找到 {len(results_df)} 条记录。")
#         
#         # 4. (可选) 调用后处理钩子
#         final_results = self._post_run_hook(results_df)
#         
#         return final_results
#
#     # 5. (可选) 覆盖 save_results 方法
#     def save_results(self, results: pd.DataFrame, output_path: str) -> None:
#         try:
#             results.to_csv(output_path, index=False)
#             print(f"{self.get_name()} 结果已保存至 CSV {output_path}")
#         except Exception as e:
#             print(f"保存 {self.get_name()} 结果失败: {e}")
#             raise # 重新抛出异常让调用者处理
#
#
# 2. 外部调用策略
# -------------------
# 在 main.py 或其他脚本中
#
# if __name__ == '__main__':
#     from modules.db import ClickHouseDB
#     # from your_config_loader import get_config # 你的配置加载函数
#
#     # 1. 准备依赖
#     db = ClickHouseDB() 
#     config = {...} # 加载你的配置字典
#
#     # 2. 创建策略实例
#     # 默认范围（所有股票）
#     strategy_all = MyNewStrategy(db, config)
#     
#     # 指定范围
#     selected_stocks = ['sh.600000', 'sz.000001']
#     strategy_selected = MyNewStrategy(db, config, stock_codes=selected_stocks)
#
#     # 3. 执行策略
#     print("--- 执行全市场策略 ---")
#     results_all = strategy_all.run()
#     
#     # 4. (可选) 外部决定是否保存
#     if not results_all.empty: # 假设返回 DataFrame
#         # 调用策略自己的保存方法
#         strategy_all.save_results(results_all, 'result_all.csv') 
#     else:
#         print("全市场策略未产生结果。")
#
#     print("\n--- 执行指定范围策略 ---")
#     results_selected = strategy_selected.run()
#     if not results_selected.empty:
#         # 也可以选择不保存，或保存到不同路径
#         # strategy_selected.save_results(results_selected, 'result_selected.csv')
#         print("指定范围策略执行完成，结果在内存中。")
#         # ... 进行其他操作 ...
#     else:
#         print("指定范围策略未产生结果。")
#
#     db.close() # 关闭数据库连接
