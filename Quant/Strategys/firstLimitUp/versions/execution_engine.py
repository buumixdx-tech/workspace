# execution_engine.py
import pandas as pd
import os
from datetime import datetime, date
from clickhouse_driver import Client
from typing import List, Dict, Any, Optional

# 导入策略接口和具体策略实现
# 确保 first_limit_strategy.py 和 strategy_interface.py 在同一目录下或在 Python 路径中
from strategy_interface import StockSelectionStrategy
from first_limit_strategy import FirstLimitCallbackStrategy # 导入具体的策略类


# ----------------------------
# 工具函数 (从 flu1.txt 提取并调整)
# ----------------------------

def get_config_limits(config_path: str = 'config.txt') -> Dict[str, Any]:
    """
    从config.txt读取EndDate。
    格式:
    UpperLimit:75%
    LowerLimit:10%
    EndDate:20250806 (可选)
    """
    # 默认配置
    config = {
        'end_date': None      # 默认None，表示使用最新交易日
    }
    if os.path.exists(config_path):
        # print("正在读取 config.txt...") # 可简化日志
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
                    if key == 'EndDate':
                        if value_raw.isdigit() and len(value_raw) == 8:
                            config['end_date'] = value_raw
                            # print(f"    -> EndDate: {config['end_date']}") # 可简化日志
                        # else:
                           # print(f"    -> 警告：EndDate 值 '{value_raw}' 格式不正确 (应为 YYYYMMDD)，跳过。") # 可简化日志
                    # else: # 策略不关心 UpperLimit/LowerLimit
                        # print(f"    -> 警告：未知的配置项 '{key}'，跳过。") # 可简化日志
        except Exception as e:
            print(f"读取 {config_path} 时发生错误，使用默认值: {str(e)}")
    # --- 打印读取到的 T 日确定相关配置值 ---
    # print(f"读取到的 T 日配置:")
    if config['end_date']:
        print(f"  - 指定结束日期: {config['end_date']}")
    else:
        print(f"  - 指定结束日期: 未设置 (将使用最新交易日)")
    # --- 结束 ---
    return config


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


def get_latest_trading_date(client: Client, specified_date_str: Optional[str] = None) -> Optional[date]:
    """
    根据指定日期或最新日期获取 T 日。
    如果指定了日期且是交易日，则为 T 日。
    否则，找到指定日期前最近的交易日或最新交易日作为 T 日。
    """
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
        # 升序排列以便查找
        all_trading_dates.sort()

        # --- 确定T日逻辑 ---
        t_date = None
        if specified_date_str:
            try:
                # 尝试将配置的日期字符串解析为 date 对象
                specified_date = datetime.strptime(specified_date_str, '%Y%m%d').date()
                print(f"配置文件指定了结束日期: {specified_date.strftime('%Y-%m-%d')}")
                # 检查指定日期是否是交易日
                if specified_date in all_trading_dates:
                    t_date = specified_date
                    print(f"指定日期 {t_date.strftime('%Y-%m-%d')} 是交易日，将作为T日。")
                else:
                    # 如果不是交易日，找到早于指定日期的最近一个交易日
                    # all_trading_dates 是按日期升序排列的
                    for trade_date in reversed(all_trading_dates): # 从后往前找
                        if trade_date < specified_date:
                            t_date = trade_date
                            break
                    if t_date:
                        print(f"指定日期 {specified_date.strftime('%Y-%m-%d')} 不是交易日，最近的交易日是 {t_date.strftime('%Y-%m-%d')}，将作为T日。")
                    else:
                        # 理论上不太可能，但如果回溯范围内没有更早的交易日
                        t_date = all_trading_dates[-1] # 使用最新的交易日
                        print(f"在回溯范围内未找到早于指定日期的交易日，使用最新的交易日 {t_date.strftime('%Y-%m-%d')} 作为T日。")
            except ValueError as e:
                print(f"配置文件中的 EndDate 格式错误 ({specified_date_str})，将忽略该设置: {e}")
                specified_date_str = None # 重置，使用默认逻辑
        # 如果没有指定日期或指定日期无效，则使用最新的交易日
        if t_date is None:
            t_date = all_trading_dates[-1]
            print(f"未指定有效结束日期，使用最新交易日 {t_date.strftime('%Y-%m-%d')} 作为T日。")

        return t_date

    except Exception as e:
        print(f"获取交易日历或确定T日失败: {e}")
        return None # 返回 None 表示失败


def save_results_to_excel(results: List[Dict[str, Any]], candidates: List[Dict[str, Any]], filename: str = 'result.xlsx'):
    """
    将策略结果保存到 Excel。
    'results' sheet 保存稳定回调的股票。
    'candidates' sheet 保存所有符合条件的首板股票。
    """
    # 定义期望的列顺序和最终列名
    column_order_before_rename = [
        '股票代码', '股票名称', '行业', '首板日期', '首板价格', '回调周期',
        '板后走势', '板后最高价', '板后最低价',
        '最高价日期', '最低价日期', '板后回调(%)'
    ]
    # 重命名映射 (如果策略返回的键名与最终Excel列名不同，需要调整)
    rename_dict = {
        # '板后回调': '板后回调(%)' # 假设策略直接返回 '板后回调(%)'
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
                df[col] = None # 使用 None 或 np.nan

        # 按期望的顺序选择和排列列，然后重命名
        df = df[column_order_before_rename]
        if rename_dict:
            df = df.rename(columns=rename_dict)
        return df

    # 准备两个DataFrame
    stable_callback_df = prepare_dataframe(results) # 'results' 对应 '稳定回调'
    all_first_limit_df = prepare_dataframe(candidates) # 'candidates' 对应 '所有首板'

    # 保存到Excel，包含两个sheet
    try:
        with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
            stable_callback_df.to_excel(writer, sheet_name='results', index=False)
            all_first_limit_df.to_excel(writer, sheet_name='candidates', index=False)
        print(f"结果已保存至 {filename}，包含 'results' 和 'candidates' 两个Sheet。")
    except Exception as e:
        print(f"保存Excel文件失败: {e}")


# ----------------------------
# 主执行流程
# ----------------------------

def main():
    """
    主执行流程。
    """
    print("开始执行量化交易策略...")

    # 1. 读取配置 (主要是 EndDate 用于确定 T 日)
    config = get_config_limits()
    specified_end_date_str = config.get('end_date')

    # 2. 连接数据库
    client = get_clickhouse_client()

    # 3. 确定 T 日
    t_date = get_latest_trading_date(client, specified_end_date_str)
    if not t_date:
         print("无法确定T日，退出。")
         return # 退出程序
    print(f"确定的T日为: {t_date}")

    # --- 策略解耦核心 ---
    # 4. 选择并实例化策略
    # 方式一：硬编码 (简单直接，适用于固定策略)
    # strategy: StockSelectionStrategy = FirstLimitCallbackStrategy()

    # 方式二：通过配置文件或参数动态加载 (更灵活)
    # 例如，可以在 config.txt 中增加一行 StrategyName:FirstLimitCallbackStrategy
    # 然后在这里读取并使用 globals()[strategy_name] 或 importlib 加载
    # 这里暂时使用硬编码作为示例
    strategy: StockSelectionStrategy = FirstLimitCallbackStrategy()

    # 5. 执行策略
    print(f"正在使用策略: {strategy.get_name()}")
    print(f"策略参数: {strategy.get_parameters()}")
    
    try:
        # 调用策略的 select_stocks 方法，传入 T 日
        selected_stocks_data = strategy.select_stocks(t_date)
        print(f"策略执行完成。")
        # 假设策略返回的就是最终需要的数据列表
        # 如果策略内部也区分了 '稳定回调' 和 '所有候选'，则需要相应调整
        # 为了兼容 flu1.txt 的输出，我们暂时假设策略只返回 '稳定回调' 的股票
        # 并且我们没有 '所有候选' 的数据。如果需要，策略本身需要提供。
        # 这里我们简化处理，只保存 'results' (稳定回调)。
        # 如果策略需要返回两部分数据，可以修改接口 select_stocks 返回 Dict[str, List[Dict]]
        # 例如: {'results': [...], 'candidates': [...]}

        # --- 临时处理：为了完全匹配 flu1.txt 的输出 ---
        # flu1.txt 的 select_stocks (即 execute_strategy) 会处理所有数据并保存两个 sheet
        # 我们需要修改策略接口或策略本身来支持这一点。
        # 一种方法是让策略的 select_stocks 返回一个包含两个列表的字典
        # 或者，让策略提供两个方法：select_stocks 和 get_all_candidates
        # 为了最小化改动，我们假设策略的 select_stocks 返回 '稳定回调'，
        # 并且策略类内部可以提供一个方法获取 '所有候选' (但这需要修改策略类)。

        # --- 修改策略接口建议 ---
        # 在 strategy_interface.py 中增加:
        # @abstractmethod
        # def get_all_candidates(self, t_date: date) -> List[Dict[str, Any]]:
        #     """获取所有符合条件的候选股票（不仅仅是稳定回调）"""
        #     pass
        #
        # 然后在 FirstLimitCallbackStrategy 中实现它，并在内部存储 all_candidates 数据。

        # --- 当前实现：假设策略只返回 'results' ---
        # 如果需要 'candidates'，需要修改 FirstLimitCallbackStrategy
        # 使其在 select_stocks 内部也计算并存储 all_first_limit_up_results
        # 并提供一个方法来获取它，或者修改 select_stocks 返回结构。

        # 临时方案：只保存 'results'
        # save_results_to_excel(selected_stocks_data, [], 'result.xlsx') # 保存空的 candidates

        # --- 更好的方案：修改策略返回结构 ---
        # 修改 FirstLimitCallbackStrategy.select_stocks 返回:
        # return {
        #     'results': stable_callback_results,
        #     'candidates': all_first_limit_up_results
        # }
        # 然后这里调用:
        if isinstance(selected_stocks_data, dict) and 'results' in selected_stocks_data and 'candidates' in selected_stocks_data:
             save_results_to_excel(selected_stocks_data['results'], selected_stocks_data['candidates'])
        else:
             # 如果策略没按新结构返回，就只保存 results，candidates 为空
             save_results_to_excel(selected_stocks_data, [])
             print("警告：策略未返回 'candidates' 数据，'candidates' sheet 将为空。")


    except Exception as e:
        print(f"执行策略 '{strategy.get_name()}' 时出错: {e}")
        import traceback
        traceback.print_exc()
        return # 策略执行失败，退出

    # 6. (未来扩展) 生成交易指令、管理持仓、资金流等
    # generate_orders(selected_stocks, t_date + timedelta(days=1)) # T+1 建仓
    # manage_positions(...) # 管理持仓 n 天
    # ...

    print("策略执行流程完成。")


if __name__ == '__main__':
    main()