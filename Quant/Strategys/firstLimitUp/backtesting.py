import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import re

# --- 1. 导入工具函数 ---
# 将当前脚本目录加入Python路径，以便导入同目录下的模块
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

# 导入 utils.py 中的函数
# 注意：根据新的需求，我们可能不再需要 fetch_trading_calendar，
# 但如果 utils.py 中有其他有用函数（如 get_clickhouse_client），仍需导入。
# 如果 utils.py 为空或不存在，这部分会失败，需要处理。
try:
    from modules.utils import get_clickhouse_client, fetch_stock_data_for_date # 假设 utils.py 至少包含这个
    print("[INFO] 成功从 utils.py 导入所需函数。")
except ImportError as e:
    print(f"[WARNING] 无法从 utils.py 导入所需函数: {e}")
    # 如果 utils.py 不存在或没有所需函数，可以在这里处理
    # 例如，定义一个模拟的 get_clickhouse_client 或者设置一个标志位
    # 为了兼容性，我们暂时保留导入，但如果失败，后续使用 ClickHouse 的部分会出错
    get_clickhouse_client = None
    print("[INFO] utils.py 未找到或不完整，部分功能（如从数据库获取日历）可能不可用。")

# --- 2. 配置读取 ---
def load_config(config_path: str) -> Dict[str, Any]:
    """读取配置文件 (简单的 key: value 格式)"""
    config = {}
    print(f"[DEBUG] 尝试读取配置文件: {config_path}")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件 {config_path} 未找到。")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                original_line = line
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                match = re.split(r':\s*', line, maxsplit=1)
                if len(match) == 2:
                    key, value_raw = match[0].strip(), match[1].strip()
                    
                    final_value = value_raw
                    if value_raw.endswith('%'):
                        try:
                            final_value = float(value_raw[:-1]) / 100.0
                        except ValueError:
                            print(f"[DEBUG]   -> 百分比转换失败，保持原字符串: '{final_value}'")
                    else:
                        try:
                            final_value = int(value_raw)
                            print(f"[DEBUG]   -> 转换为整数: {final_value}")
                        except ValueError:
                            try:
                                final_value = float(value_raw)
                                print(f"[DEBUG]   -> 转换为浮点数: {final_value}")
                            except ValueError:
                                print(f"[DEBUG]   -> 保持为字符串: '{final_value}'")
                    
                    config[key] = final_value
                    print(f"[DEBUG]   -> 已存储到 config: {key} = {config[key]} (类型: {type(config[key])})")
                else:
                    print(f"[WARNING] 配置文件 {config_path} 第 {line_num} 行格式不正确，已跳过: '{original_line.strip()}'")
        print(f"[DEBUG] 配置文件读取完毕。最终 config 字典: {config}")
    except Exception as e:
        print(f"[ERROR] 读取配置文件 {config_path} 时发生错误: {e}")
        import traceback
        traceback.print_exc()
        raise

    # 验证必要配置项
    required_keys = ['initial_capital', 'holding_period']
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"配置文件缺少必要项: {missing_keys}")

    return config

# --- 3. 数据加载 ---
def load_sampling_results(filepath: str) -> Dict[datetime.date, List[str]]:
    """从Excel加载选股结果 (samplingresults 页)"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"选股结果文件 {filepath} 未找到。")

    try:
        df = pd.read_excel(filepath, sheet_name='samplingresults', header=None)
    except Exception as e:
        raise ValueError(f"读取选股结果文件 'samplingresults' 页失败: {e}")

    if df.empty:
        raise ValueError("选股结果文件 'samplingresults' 页为空。")

    results = {}
    current_col_map = {} # 用于存储当前块的列名映射 {索引: 名称}

    for index, row in df.iterrows():
        # 检查是否是新的数据块开始 (包含 '交易日' 的行)
        if '交易日' in str(row.iloc[0]) and '股票代码' in str(row.iloc[1]):
            # 重新构建列名映射
            current_col_map = {}
            for col_idx, cell_value in enumerate(row):
                if '交易日' in str(cell_value):
                    current_col_map[col_idx] = '交易日'
                elif '股票代码' in str(cell_value):
                    # 提取 '股票代码X' 中的 X 作为键
                    current_col_map[col_idx] = str(cell_value).strip()
            print(f"[DEBUG] 在行 {index} 检测到新数据块表头，更新列映射。")
            continue # 跳过表头行本身

        # 尝试将第一列解析为日期
        date_cell = row.iloc[0] if len(row) > 0 else None
        if pd.isna(date_cell):
            continue # 跳过空行
        
        try:
            # 尝试多种日期格式
            if isinstance(date_cell, str):
                date_obj = datetime.strptime(date_cell, '%Y%m%d').date()
            elif isinstance(date_cell, (int, float)): # Excel 有时将日期存储为数字
                 date_obj = datetime.strptime(str(int(date_cell)), '%Y%m%d').date()
            else:
                # 如果是 datetime 类型
                date_obj = pd.to_datetime(date_cell).date()
        except (ValueError, TypeError):
            # print(f"[DEBUG] 行 {index} 第一列 '{date_cell}' 不是有效日期，跳过。")
            continue # 跳过非日期行

        # 收集该行的股票代码
        stocks_for_this_date = []
        for col_idx, col_name in current_col_map.items():
            if col_name.startswith('股票代码') and col_idx < len(row):
                stock_code = row.iloc[col_idx]
                if pd.notna(stock_code) and str(stock_code).strip() != '':
                    stocks_for_this_date.append(str(stock_code).strip())
        
        if stocks_for_this_date:
            results[date_obj] = stocks_for_this_date
            # print(f"[DEBUG] 加载日期 {date_obj}: {len(stocks_for_this_date)} 只股票")

    print(f"[INFO] 成功加载 {len(results)} 个交易日的选股数据。")
    if results:
        sorted_keys = sorted(results.keys())
        print(f"[DEBUG] 示例数据 - 第一个日期: {sorted_keys[0]}, 选股数量: {len(results[sorted_keys[0]])}")
        print(f"[DEBUG] 示例数据 - 最后一个日期: {sorted_keys[-1]}, 选股数量: {len(results[sorted_keys[-1]])}")
    return results

# --- 3.5. 从Excel加载交易日历 ---
def load_trading_calendar_from_excel(filepath: str) -> List[datetime.date]:
    """从Excel的 'calendar' 页加载交易日历"""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件 {filepath} 未找到。")

    try:
        # 读取 'calendar' 页
        df_calendar = pd.read_excel(filepath, sheet_name='calendar', header=None)
        print(f"[DEBUG] 成功读取 'calendar' 页，形状: {df_calendar.shape}")
    except Exception as e:
        raise ValueError(f"读取 'calendar' 页失败: {e}")

    if df_calendar.empty:
        print("[WARNING] 'calendar' 页为空。")
        return []

    calendar_dates = []
    # 遍历所有单元格
    for row_idx in range(df_calendar.shape[0]):
        for col_idx in range(df_calendar.shape[1]):
            cell_value = df_calendar.iat[row_idx, col_idx]
            if pd.isna(cell_value):
                continue
            try:
                # 假设日期格式是 YYYYMMDD 的字符串或整数
                if isinstance(cell_value, str) and cell_value.isdigit() and len(cell_value) == 8:
                    date_obj = datetime.strptime(cell_value, '%Y%m%d').date()
                    calendar_dates.append(date_obj)
                elif isinstance(cell_value, (int, float)) and len(str(int(cell_value))) == 8:
                    date_obj = datetime.strptime(str(int(cell_value)), '%Y%m%d').date()
                    calendar_dates.append(date_obj)
                # 可以添加其他日期格式的处理
            except (ValueError, TypeError):
                # 忽略无法解析的单元格
                pass
                
    # 去重并排序
    unique_sorted_dates = sorted(list(set(calendar_dates)))
    print(f"[INFO] 从 'calendar' 页成功加载并解析了 {len(unique_sorted_dates)} 个交易日。")
    if unique_sorted_dates:
        print(f"[DEBUG] 示例日期 - 第一个: {unique_sorted_dates[0]}, 最后一个: {unique_sorted_dates[-1]}")
    return unique_sorted_dates

# --- 4. 账户类定义 ---
class PortfolioAccount:
    def __init__(self, account_id: int, initial_cash: float):
        self.account_id = account_id
        self.cash = initial_cash
        # {code: {'quantity': int, 'cost_price': float, 'entry_date': date, 'holding_days': int}}
        self.positions: Dict[str, Dict[str, Any]] = {} 
        self.last_operation_date: Optional[datetime.date] = None

    def reset(self):
        """重置账户状态，用于清仓后"""
        self.cash = 0
        self.positions = {}
        self.last_operation_date = None

# --- 5. 核心回测逻辑 ---
class RollingPortfolioBacktester:
    def __init__(self, config: Dict[str, Any]):
        self.initial_capital = float(config['initial_capital'])
        self.holding_period = int(config['holding_period'])
        self.num_accounts = self.holding_period

        if self.holding_period <= 0:
            raise ValueError("持仓周期 (holding_period) 必须大于0。")

        # 初始化账户
        self.accounts = [PortfolioAccount(i, self.initial_capital / self.num_accounts) for i in range(self.num_accounts)]

        # --- 1. 加载选股数据 ---
        sampling_file_path = os.path.join(script_dir, 'data', 'sampling_result.xlsx')
        self.sampling_results = load_sampling_results(sampling_file_path)
        self.sampling_dates = sorted(list(self.sampling_results.keys()))
        
        if not self.sampling_dates:
            raise ValueError("选股结果文件中未找到任何日期数据。")

        # --- 2. 确定核心回测周期 (基于选股数据) ---
        # T_day: 回测开始日期 (第一个有选股的日期)
        self.T_day = self.sampling_dates[0]  
        # L_day: 回测结束日期 (最后一个有选股的日期)
        self.L_day = self.sampling_dates[-1] 

        print(f"[INFO] 根据选股结果确定的核心回测周期: T_day ({self.T_day}) 至 L_day ({self.L_day})")

        # --- 3. 获取交易日历 ---
        self.trading_calendar = []
        self.trading_calendar_set = set()
        
        # 首先尝试从 sampling_result.xlsx 的 'calendar' 页加载
        try:
            self.trading_calendar = load_trading_calendar_from_excel(sampling_file_path)
            if self.trading_calendar:
                self.trading_calendar_set = set(self.trading_calendar)
                print(f"[INFO] 成功从 'sampling_result.xlsx' 的 'calendar' 页加载了交易日历。")
            else:
                 print(f"[WARNING] 从 'calendar' 页加载的日历为空。")
        except Exception as cal_e:
            print(f"[WARNING] 从 'sampling_result.xlsx' 的 'calendar' 页加载日历失败 ({cal_e})。")
            # 注意：根据新需求，不再回退到本地CSV或ClickHouse
            # 如果从Excel加载失败，则无法继续
            raise ValueError("无法从 'sampling_result.xlsx' 的 'calendar' 页加载交易日历，回测无法进行。") from cal_e

        # --- 4. 确定完整的回测日期序列 (包括清仓期 L+1 到 L+n) ---
        print(f"[DEBUG] 开始计算完整回测日期序列...")
        print(f"[DEBUG] T_day: {self.T_day}, L_day: {self.L_day}, 持仓周期 n: {self.holding_period}")

        # 在交易日历中找到 T_day 和 L_day 的索引
        try:
            T_day_index_in_calendar = self.trading_calendar.index(self.T_day)
            L_day_index_in_calendar = self.trading_calendar.index(self.L_day)
        except ValueError as e:
            raise ValueError(f"T日 ({self.T_day}) 或 L日 ({self.L_day}) 不在获取的交易日历中: {e}")

        # 计算最终清仓日期索引 (L_day 索引 + 持仓周期 n)
        final_clearance_day_index_in_calendar = L_day_index_in_calendar + self.holding_period
        
        # 检查交易日历是否足够长
        if final_clearance_day_index_in_calendar >= len(self.trading_calendar):
            raise ValueError(
                f"交易日历不足以覆盖从 L日({self.L_day}) 开始的 {self.holding_period} 个持仓周期。"
                f"需要的最终清仓日索引为 {final_clearance_day_index_in_calendar}，但日历长度只有 {len(self.trading_calendar)}。"
            )

        # 获取实际的最终清仓日期
        self.final_clearance_day = self.trading_calendar[final_clearance_day_index_in_calendar]
        print(f"[DEBUG] 计算出的最终清仓日期 L+n: {self.final_clearance_day} (索引: {final_clearance_day_index_in_calendar})")

        # 生成最终的回测日期序列 (从 T_day 到 final_clearance_day)
        start_idx = T_day_index_in_calendar
        end_idx = final_clearance_day_index_in_calendar
        self.backtest_dates = self.trading_calendar[start_idx : end_idx + 1]

        # 验证生成的日期序列长度
        min_required_length = self.holding_period + 1
        if len(self.backtest_dates) < min_required_length:
             raise ValueError(f"生成的回测日期序列长度不足 ({len(self.backtest_dates)})，无法完成至少一个完整的持仓周期 (需要 {min_required_length} 天)。")

        print(f"回测配置: 初始资金 {self.initial_capital:,.2f}, 持仓周期 {self.holding_period}")
        print(f"完整回测日期范围: {self.backtest_dates[0]} 至 {self.backtest_dates[-1]} (共 {len(self.backtest_dates)} 天)")
        print(f"核心选股日期范围: {self.T_day} 至 {self.L_day}")

        # --- 5. 初始化价格缓存 ---
        self.price_cache: Dict[Tuple[str, datetime.date], Dict[str, float]] = {}

        # 在 RollingPortfolioBacktester 类内部

    def _get_price_data(self, date: datetime.date, account_positions: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, float]]:
        """
        从ClickHouse获取指定日期的股票价格数据。
        如果提供了 account_positions，则只查询其中的股票代码。
        否则，查询所有相关股票
        
        Args:
            date (datetime.date): 目标日期。
            account_positions (Optional[Dict[str, Any]]): 账户持仓字典 {code: {...}}。
                                                        如果为 None，则需要从外部提供 codes。

        Returns:
            Dict[str, Dict[str, float]]: 价格数据字典 {code: {open, close, tradestatus}}。
        """

        
        # 检查是否已成功导入必要的函数
        if get_clickhouse_client is None or fetch_stock_data_for_date is None:
            raise RuntimeError("无法连接到ClickHouse数据库或缺少 fetch_stock_data_for_date 函数。")

        # 2. 从 account_positions 提取股票代码
        if account_positions is not None:
            codes = list(account_positions.keys())            
        else:
            # 如果没有提供 positions，可以考虑抛出异常或返回空（取决于调用场景）
            # 为了兼容性，暂时允许 codes 为 None，但实际调用时应提供
            codes = None
        if not codes: # 如果 codes 为空或 None
            return {}
        try:
            client = get_clickhouse_client() # 获取客户端连接

            # 3. 调用 utils 中的新函数
            stock_data_list = fetch_stock_data_for_date(client, date, codes)
            # ---- 添加打印输出：查询到的原始行情信息 ----
            # print(f"    [DEBUG] 从数据库查询到 {date} 的 {len(stock_data_list)} 条股票数据:")
            for stock_data in stock_data_list:
                # 打印每条数据的关键字段，格式化一下方便查看
                code = stock_data.get('code', 'N/A')
                open_p = stock_data.get('open')
                close_p = stock_data.get('close')
                high_p = stock_data.get('high') # 如果需要的话
                low_p = stock_data.get('low')   # 如果需要的话
                status = stock_data.get('tradestatus', 1)
                # 格式化价格，如果是None则显示'N/A'
                open_str = f"{open_p:.2f}" if open_p is not None else "N/A"
                close_str = f"{close_p:.2f}" if close_p is not None else "N/A"
                # print(f"      代码: {code:>10}, 开盘: {open_str:>6}, 收盘: {close_str:>6}, 状态: {status}")
            # ---- 添加打印输出 ----
            
            price_data = {}
            # 将返回的列表转换为以 code 为键的字典
            for stock_data in stock_data_list:
                code = stock_data['code']
                price_data[code] = {
                    'open': float(stock_data['open']) if stock_data['open'] is not None else None,
                    'close': float(stock_data['close']) if stock_data['close'] is not None else None,
                    'preclose': float(stock_data['preclose']) if stock_data['preclose'] is not None else None,
                    # 可以根据需要添加更多字段，如 high, low 等
                    'tradestatus': int(stock_data['tradestatus']) if stock_data['tradestatus'] is not None else 1
                }
            return price_data

        except Exception as e:
            print(f"[WARNING] 查询 {date} 的价格数据失败: {e}")
            return {code: {} for code in codes}
    
    def _get_stocks_for_buying(self, buy_date: datetime.date) -> List[str]:
        """
        根据建仓日期，获取其前一个交易日选股结果中的股票列表。
        
        Args:
            buy_date (datetime.date): 建仓日期 (T+1日)。
            
        Returns:
            List[str]: 前一个交易日 (T日) 选股结果中的股票列表。
                    如果前一个交易日没有选股或日期无效，则返回空列表。
        """
        try:
            # 1. 在交易日历中找到建仓日期的索引
            buy_date_index = self.trading_calendar.index(buy_date)
            
            # 2. 检查是否存在前一个交易日
            if buy_date_index <= 0:
                print(f"[WARNING] 建仓日期 {buy_date} 是交易日历中的第一天，没有前一个交易日用于选股。")
                return []
            
            # 3. 获取前一个交易日的日期
            selection_date = self.trading_calendar[buy_date_index - 1]
            
            # 4. 从选股结果中获取该日期的股票列表
            stocks_to_buy = self.sampling_results.get(selection_date, [])
            
            # print(f"[DEBUG] _get_stocks_for_buying: buy_date={buy_date}, selection_date={selection_date}, stocks_to_buy={stocks_to_buy}")
            return stocks_to_buy
            
        except ValueError:
            # buy_date 不在交易日历中 (理论上不应该发生，因为 run 是遍历 self.backtest_dates)
            print(f"[ERROR] 建仓日期 {buy_date} 不在交易日历中，无法确定选股日期。")
            return []
        except Exception as e:
            # 捕获其他潜在错误
            print(f"[ERROR] 获取 {buy_date} 的选股列表时发生未知错误: {e}")
            return []

    def _buy_stocks(self, account: PortfolioAccount, target_date: datetime.date, stock_codes: List[str]):
        """T+1日建仓操作"""
        print(f"  账户 {account.account_id} 在 {target_date} 尝试建仓: {stock_codes}")
        if not stock_codes:
            print(f"  账户 {account.account_id}: 无股票可建仓。")
            return

        # --- 修改部分：将 stock_codes 列表转换为类似 account.positions 的字典格式 ---
        # 创建一个临时字典，键为股票代码，值为空字典 {}
        # 这是为了适配 _get_price_data 的新签名: def _get_price_data(self, date, account_positions_dict)
        temp_positions_dict = {code: {} for code in stock_codes}
        # --- 修改部分结束 ---

        # --- 修改部分：调用 _get_price_data 时传入临时字典 ---
        price_data = self._get_price_data(target_date, temp_positions_dict)
        # --- 修改部分结束 ---
        
        valid_stocks = []
        for code in stock_codes:
            
            # 判断这个票的涨跌幅限制
            code_digits = code[3:6]
            # 如果第4-6位是 "300" 或 "688"，则认为是 20% 涨停板
            if code_digits in ["300", "688"]:
                limit_ratio = 1.2
            else:
                limit_ratio = 1.1
            data = price_data.get(code, {})
            #计算涨停板价格
            upper_limit = round(data['preclose'] * limit_ratio, 2)
            if not data or data.get('tradestatus', 1) == 0 or data.get('open') is None or data['open'] <= 0 or data['open'] == upper_limit:
                print(f"    股票 {code} 在 {target_date} 停牌、无有效开盘价、涨停开盘或价格非正，跳过。")
                continue
            valid_stocks.append((code, data['open']))

        if not valid_stocks:
            print(f"  账户 {account.account_id}: 所有目标股票在 {target_date} 均无效。")
            return

        num_stocks = len(valid_stocks)
        budget_per_stock = account.cash / num_stocks
        fee_rate = 0.0003 # 万分之三

        for code, open_price in valid_stocks:
            max_amount_pre_trade = budget_per_stock / (1 + fee_rate)
            max_lots = int(max_amount_pre_trade / (open_price * 100))
            
            if max_lots > 0:
                quantity = max_lots * 100
                cost = quantity * open_price
                fee = cost * fee_rate
                total_cost = cost + fee

                if account.cash >= total_cost:
                    account.cash -= total_cost
                    account.positions[code] = {
                        'quantity': quantity,
                        'cost_price': open_price,
                        'entry_date': target_date,
                        'holding_days': 1 # 建仓当天算第一天
                    }
                    print(f"    成功买入 {code}: {quantity} 股 @ {open_price:.2f}, 费用 {total_cost:.2f}")
                else:
                    print(f"    资金不足，无法买入 {code}。")
            else:
                print(f"    资金不足以买入1手 {code}。")

        if account.positions:
            account.last_operation_date = target_date

    def _sell_stocks(self, account: PortfolioAccount, target_date: datetime.date):
        """T+n日清仓操作"""
        print(f"  账户 {account.account_id} 在 {target_date} 执行清仓...")
        if not account.positions:
            print(f"  账户 {account.account_id}: 无需清仓，当前无持仓。")
            account.reset()
            return

        price_data = self._get_price_data(target_date, account.positions)
        fee_rate = 0.0013 # 千分之1.3

        sold_codes = []
        for code, pos_info in list(account.positions.items()):
            data = price_data.get(code, {})
            close_price = data.get('close') if data else None
            
            if close_price is not None and close_price > 0:
                quantity = pos_info['quantity']
                sell_value = quantity * close_price
                fee = sell_value * fee_rate
                net_proceeds = sell_value - fee
                
                account.cash += net_proceeds
                print(f"    成功卖出 {code}: {quantity} 股 @ {close_price:.2f}, 收入 {net_proceeds:.2f} (含费用 {fee:.2f})")
                sold_codes.append(code)
            else:
                print(f"    警告: 股票 {code} 在 {target_date} 无有效收盘价，无法卖出。持仓将被保留。")

        for code in sold_codes:
            del account.positions[code]

    def run(self):
        """执行回测"""
        print("开始执行回测...")
        results = []

        for i, current_date in enumerate(self.backtest_dates):
            
            # if i>6:
            #     return
            
            if current_date > self.L_day:
                phase = "最终清仓期" 
            elif i < self.holding_period:
                phase = "初始建仓期"
            else:
                phase = "滚动持仓期"
            print(f"\n--- 处理日期: {current_date} (第 {i+1}/{len(self.backtest_dates)} 天, 阶段: {phase}) ---")
            
            total_market_value = 0.0
            total_cash_balance = 0.0            

            # --- 2. 遍历所有账户并执行操作 ---
            for acc_idx, account in enumerate(self.accounts):
                # --- 2.1 更新所有持仓的持有天数 ---
                for pos_code in account.positions:
                    account.positions[pos_code]['holding_days'] += 1
                                # --- 添加调试输出：账户当前持仓状态 ---
                if account.positions: # 检查账户是否有持仓
                    # 遍历所有持仓并打印详细信息
                    for pos_code, pos_info in account.positions.items():
                         print(f"    [DEBUG] 账户 {account.account_id} 持有 {pos_code}: {pos_info['quantity']} 股, 已持有 {pos_info['holding_days']} 天")
                else:
                    # 如果没有持仓，也打印一条信息
                    print(f"    [DEBUG] 账户 {account.account_id} 当前无持仓。")
                # --- 调试输出结束 ---

                # --- 2.2 计算该账户的首次建仓日期索引 ---
                first_buy_date_index = acc_idx + 1

                # --- 2.3 根据阶段和账户状态决定操作 ---
                if phase == "初始建仓期":
                    # --- 初始建仓期逻辑 ---
                    # 条件：已到或超过该账户的激活日，且账户当前无持仓
                    if i >= first_buy_date_index and not account.positions:
                        stocks_to_buy = self._get_stocks_for_buying(current_date)
                        if stocks_to_buy:
                            print(f"  [初始建仓期] 账户 {acc_idx} 在 {current_date} 建仓。")
                            self._buy_stocks(account, current_date, stocks_to_buy)
                        else:
                            print(f"  [初始建仓期] 账户 {acc_idx} 在 {current_date} 无选股，跳过建仓。")

                elif phase in ["滚动持仓期", "最终清仓期"]:
                    # --- 滚动持仓期 & 最终清仓期逻辑 ---
                    # 两个阶段的判断逻辑相同，因此合并处理
                    if not account.positions:
                        # --- 情况一：账户空仓 ---
                        # 在滚动持仓期，可以建仓；在最终清仓期，不再建仓。
                        if phase == "滚动持仓期":
                            # 检查是否是选股日 (T日)
                            stocks_to_buy = self._get_stocks_for_buying(current_date)
                            if stocks_to_buy:
                                print(f"  [{phase}] 账户 {acc_idx} 在 {current_date} 建仓。")
                                self._buy_stocks(account, current_date, stocks_to_buy)
                            else:
                                print(f"  [{phase}] 账户 {acc_idx} 在 {current_date} 无选股，跳过建仓。")
                        # else: phase == "最终清仓期" 且空仓，无操作

                    else:
                        # --- 情况二：账户有持仓 ---
                        # 检查是否达到持仓周期，决定是否清仓
                        # 持仓天数在循环开始时已更新，'holding_days' == 1 是建仓当天
                        if account.positions: # 再次确认有持仓（虽然上面if已经判断）
                            # 随机取一个持仓的股票代码来检查其信息（假设同账户同时买入，持有期相同）
                            # 更严谨的方式是检查所有持仓，但通常它们是同一天买入的
                            some_pos_info = next(iter(account.positions.values()))
                            holding_days = some_pos_info['holding_days']
                            
                            if holding_days >= self.holding_period:
                                # 达到持仓周期，执行清仓
                                print(f"  [{phase}] 账户 {acc_idx} 在 {current_date} 清仓。")
                                self._sell_stocks(account, current_date)
                            # else: 持仓未到期，无操作

                # --- 2.4 累计当日所有账户的资产 ---
                price_data_today = self._get_price_data(current_date, account.positions)
                total_cash_balance += account.cash
                account_value = 0
                for pos_code, pos_info in account.positions.items():
                    quantity = pos_info['quantity']
                    # 使用当日收盘价计算市值
                    close_price = price_data_today.get(pos_code, {}).get('close')
                    if close_price is not None and close_price > 0:
                        pos_value = quantity * close_price
                        total_market_value += pos_value
                        account_value += pos_value
                    # else: 无法获取价格，该持仓不计入当日市值
                print(f"  账户{acc_idx}: 市值 {account_value:,.2f}, 现金 {account.cash:,.2f}")

            # --- 3. 记录当日合并资产情况 ---
            total_asset = total_market_value + total_cash_balance
            results.append({
                'date': current_date,
                'total_market_value': round(total_market_value, 2),
                'total_cash_balance': round(total_cash_balance, 2),
                'total_asset': round(total_asset, 2),
            })
            print(f"  当日汇总: 市值 {total_market_value:,.2f}, 现金 {total_cash_balance:,.2f}, 总资产 {total_asset:,.2f}")

        print("\n回测完成。")
        return results

    def save_results(self, results: List[Dict], filename: str = "btresult.xlsx"):
        """保存回测结果到Excel"""
        if not results:
            print("[WARNING] 回测结果为空，未生成输出文件。")
            return

        output_data = []
        for res in results:
            output_data.append({
                '日期': res['date'],
                '持仓总市值': res['total_market_value'],
                '资金余额': res['total_cash_balance'],
                '总资产': res['total_asset']
            })
        
        df_output = pd.DataFrame(output_data)
        output_path = os.path.join(script_dir, filename)
        
        try:
            df_output.to_excel(output_path, index=False)
            print(f"[INFO] 回测结果已保存至: {output_path}")
        except Exception as e:
            print(f"[ERROR] 保存回测结果到 {output_path} 失败: {e}")


# --- 6. 主程序入口 ---
if __name__ == "__main__":
    try:
        config_path = os.path.join(script_dir, "backtesting_config.txt")
        config = load_config(config_path)
        backtester = RollingPortfolioBacktester(config)
        results = backtester.run()
        backtester.save_results(results)
    except Exception as e:
        print(f"回测过程中发生致命错误: {e}")
        import traceback
        traceback.print_exc()
