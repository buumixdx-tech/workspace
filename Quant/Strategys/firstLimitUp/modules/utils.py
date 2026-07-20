# modules/utils.py

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta, date
from clickhouse_driver import Client
import re
from typing import List, Dict, Any, Optional, Tuple, Union
import yaml
from .db import ClickHouseDB


# ----------------------------
# 工具函数：ClickHouse连接配置 (已根据要求修改用户名和密码)
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
# 工具函数：读取配置文件中的kv值
# ----------------------------
def get_config(config_path: str = 'config.txt') -> dict:
    """
    从指定的配置文件读取键值对配置项。
    格式: key:value
    Args:
        config_path (str): 配置文件的路径。默认为 'config.txt'。
    Returns:
        dict: 包含所有配置项的字典。
    """
    config = {}
    if os.path.exists(config_path):
        # print(f"正在读取配置文件 {config_path}...") # 可根据需要开启/关闭详细日志
        try:
            # 显式指定 encoding='utf-8' 以避免编码问题
            with open(config_path, 'r', encoding='utf-8') as f:
                # line_number = 0 # 可根据需要开启/关闭详细日志
                for line in f:
                    # line_number += 1 # 可根据需要开启/关闭详细日志
                    # original_line = line # 可根据需要开启/关闭详细日志
                    line = line.strip() # 去除首尾空白字符
                    # print(f"  读取第 {line_number} 行: '{original_line.strip()}'") # 可根据需要开启/关闭详细日志
                    # 跳过空行
                    if not line:
                        # print(f"    -> 跳过空行") # 可根据需要开启/关闭详细日志
                        continue
                    # 查找第一个冒号 ':' 的位置
                    colon_index = line.find(':')
                    # 如果没有冒号或冒号在行首，则跳过该行
                    if colon_index <= 0:
                         # print(f"    -> 跳过：格式不正确或缺少Key") # 可根据需要开启/关闭详细日志
                         continue
                    # 提取 key 和 value
                    key = line[:colon_index].strip()   # 冒号前的部分作为 key，并去除首尾空格
                    value_raw = line[colon_index + 1:].strip() # 冒号后的部分作为 value，并去除首尾空格
                    # print(f"    -> 解析 Key: '{key}', Value: '{value_raw}' (原始)") # 可根据需要开启/关闭详细日志
                    # --- 处理百分比值 ---
                    # 初始化最终存储的 value 为原始字符串
                    processed_value = value_raw
                    # 检查 value_raw 是否以 '%' 结尾
                    if value_raw.endswith('%'):
                        try:
                            # 移除末尾的 '%' 并转换为浮点数
                            percent_number = float(value_raw[:-1])
                            # 转换为小数
                            processed_value = percent_number / 100.0
                            # print(f"    -> 检测到百分比，转换为小数: {processed_value}") # 可根据需要开启/关闭详细日志
                        except ValueError:
                            # 如果转换失败（例如 'abc%'），则保留原始字符串
                            print(f"    -> 警告：无法将 '{value_raw}' 转换为百分比数字，将作为普通字符串处理。")
                            # processed_value 保持为 value_raw
                    # --- 结束百分比处理 ---
                    # 将键值对存入字典
                    config[key] = processed_value
        except Exception as e:
            print(f"读取配置文件 {config_path} 时发生错误: {e}")
            # import traceback
            # traceback.print_exc() # 如需详细堆栈可取消注释
    # --- 打印读取到的配置值 ---
    print(f"从 {config_path} 读取到的配置:") # 可根据需要开启/关闭详细日志
    # for k, v in config.items(): # 可根据需要开启/关闭详细日志
    #     print(f"  - {k}: {v}") # 可根据需要开启/关闭详细日志
    # --- 结束 ---
    return config


# ----------------------------
# 工具函数：从完整代码提取6位数字代码 (保留此函数用于匹配 stock_info_dict)
# ----------------------------
def extract_6digit_code(full_code: str) -> Optional[str]:
    """
    从 'sh.600000' 或 'sz.000001' 提取 '600000'
    此函数仅用于从数据库代码匹配 AllA.xlsx 信息，不用于最终输出
    """
    match = re.search(r'\.(\d{6})$', full_code)
    return match.group(1) if match else None


# ----------------------------
# 工具函数：加载股票信息
# ----------------------------
def load_stock_info() -> Dict[str, Dict[str, str]]:
    """
    从 configs/AllA.xlsx 加载股票代码、名称和行业信息
    AllA.xlsx 中的代码是纯6位数字
    
    返回:
        Dict[str, Dict[str, str]]: 股票信息字典，格式为 {股票代码: {'股票名称': str, '行业': str}}
    
    异常:
        FileNotFoundError: 当文件不存在时抛出
    """
    # 构建文件路径（兼容不同操作系统路径分隔符）
    file_path = os.path.join('configs', 'AllA.xlsx')
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"找不到 {file_path} 文件，请确保：\n"
            "1. configs目录与脚本在同一目录\n"
            "2. AllA.xlsx文件在configs目录中"
        )
    
    try:
        # 读取Excel文件
        df_info = pd.read_excel(file_path)
        
        # 标准化股票代码为6位数字 (处理 = "000032" 这种格式)
        df_info['股票代码'] = (
            df_info['股票代码']
            .astype(str)
            .str.replace(r'[^\d]', '', regex=True)
            .str.zfill(6)
        )
        
        # 构建股票信息字典
        stock_info_dict = {}
        for _, row in df_info.iterrows():
            code = row['股票代码']  # 6位数字
            name = str(row['股票简称']).strip().replace('Ａ', 'A')  # 处理全角A
            industry = str(row['所属行业']).strip()
            
            stock_info_dict[code] = {
                '股票名称': name,
                '行业': industry
            }
        
        return stock_info_dict
    
    except Exception as e:
        raise RuntimeError(f"读取 {file_path} 文件时出错: {str(e)}") from e

# ----------------------------
# 工具函数：获取T日之前n个交易日
# ----------------------------
def get_n_dates_before_T(db: ClickHouseDB, n: int, t_date: str) -> List[str]:
    """
    获取 T 日之前的 n 个交易日日期列表，包括T日
    如果 T 日不是交易日，则用晚于 T 日的最近一个交易日作为新的 T 日
    
    Args:
        db: ClickHouseDB 实例
        n: 需要获取的交易日数量
        t_date: T 日 (YYYYMMDD 格式)
        
    Returns:
        List[str]: n 个交易日的列表 (YYYYMMDD 格式)，按日期升序排列
                  任何错误情况都返回空列表
    """
    if n <= 0:
        return []
    
    try:
        t_date_obj = datetime.strptime(t_date, '%Y%m%d').date()
        t_date_str = t_date_obj.strftime('%Y-%m-%d')
    except ValueError:
        return []

    try:
        # 使用字符串格式的日期，避免类型转换问题
        query = """
        WITH 
        adjusted_t_date AS (
            SELECT min(toString(date)) AS new_t_date_str
            FROM stock_data.index_k
            WHERE code = 'sh.000001' AND date >= %(t_date)s
        )
        SELECT 
            concat(
                substring(toString(date), 1, 4),
                substring(toString(date), 6, 2),
                substring(toString(date), 9, 2)
            ) AS date_str
        FROM stock_data.index_k
        WHERE 
            code = 'sh.000001' 
            AND toString(date) <= (SELECT new_t_date_str FROM adjusted_t_date)
            AND (SELECT new_t_date_str FROM adjusted_t_date) IS NOT NULL
            AND (SELECT new_t_date_str FROM adjusted_t_date) != ''
        ORDER BY date DESC
        LIMIT %(n)s
        """
        
        params = {
            't_date': t_date_str,
            'n': int(n)
        }
        
        result = db.fetch_all(query, params)
        
        if not result:
            return []
        
        # 提取日期字符串
        dates = [str(row[0]) for row in result]
        return sorted(dates)
        
    except Exception as e:
        print(f"数据库查询失败: {e}")
        import traceback
        traceback.print_exc()
        return []
    
# ----------------------------
# 工具函数：获取T日之后n个交易日
# ----------------------------
def get_n_dates_after_T(db: ClickHouseDB, n: int, t_date: str) -> List[str]:
    """
    获取 T 日之后的 n 个交易日日期列表（不包括 T 日）
    如果 T 日不是交易日，则用早于 T 日的最近一个交易日作为新的 T 日
    
    Args:
        db: ClickHouseDB 实例
        n: 需要获取的交易日数量
        t_date: T 日 (YYYYMMDD 格式)
        
    Returns:
        List[str]: n 个交易日的列表 (YYYYMMDD 格式)，按日期升序排列
                  任何错误情况都返回空列表
    """
    if n <= 0:
        return []
    
    try:
        # 日期格式校验
        t_date_obj = datetime.strptime(t_date, '%Y%m%d').date()
        t_date_str = t_date_obj.strftime('%Y-%m-%d')
    except ValueError:
        return []

    try:
        # 使用字符串格式的日期，避免类型转换问题
        query = """
        WITH 
        adjusted_t_date AS (
            SELECT max(toString(date)) AS new_t_date_str
            FROM stock_data.index_k
            WHERE code = 'sh.000001' AND date <= %(t_date)s
        )
        SELECT 
            concat(
                substring(toString(date), 1, 4),
                substring(toString(date), 6, 2),
                substring(toString(date), 9, 2)
            ) AS date_str
        FROM stock_data.index_k
        WHERE 
            code = 'sh.000001' 
            AND toString(date) > (SELECT new_t_date_str FROM adjusted_t_date)
            AND (SELECT new_t_date_str FROM adjusted_t_date) IS NOT NULL
            AND (SELECT new_t_date_str FROM adjusted_t_date) != ''
        ORDER BY date ASC
        LIMIT %(n)s
        """
        
        params = {
            't_date': t_date_str,
            'n': int(n)
        }
        
        result = db.fetch_all(query, params)
        
        if not result:
            return []
        
        # 提取日期字符串
        dates = [str(row[0]) for row in result]
        return dates  # 已经是升序排列
        
    except Exception as e:
        print(f"数据库查询失败: {e}")
        import traceback
        traceback.print_exc()
        return []
    
# ----------------------------
# 工具函数：获取 T 日
# ----------------------------
def get_t_date(db: ClickHouseDB, specified_end_date_str: str = None) -> str:
    """
    根据指定日期或最新日期获取T日。
    返回日期格式为YYYY-MM-DD。
    """
    print("正在获取交易日历并确定T日...")
    try:
        # 确定查询的结束日期
        if specified_end_date_str:
            try:
                end_date_obj = datetime.strptime(specified_end_date_str, '%Y%m%d').date()
                end_date_str = end_date_obj.strftime('%Y-%m-%d')
                print(f"配置文件指定了结束日期: {end_date_str}")
            except ValueError as e:
                print(f"配置文件中的 EndDate 格式错误 ({specified_end_date_str}): {e}")
                end_date_str = datetime.now().date().strftime('%Y-%m-%d')
        else:
            end_date_str = datetime.now().date().strftime('%Y-%m-%d')
        
        # 使用更兼容的 SQL 查询逻辑
        if specified_end_date_str:
            # 指定了结束日期的情况
            query = """
            SELECT 
                concat(
                    toString(toYear(final_date)),
                    '-',
                    substring('0' || toString(toMonth(final_date)), -2),
                    '-',
                    substring('0' || toString(toDayOfMonth(final_date)), -2)
                ) AS t_date_str
            FROM (
                SELECT 
                    if(
                        (SELECT count() FROM stock_data.index_k 
                         WHERE code = 'sh.000001' AND date = toDate(%(end_date)s)) > 0,
                        toDate(%(end_date)s),
                        (SELECT max(date) FROM stock_data.index_k 
                         WHERE code = 'sh.000001' AND date < toDate(%(end_date)s))
                    ) AS final_date
            )
            WHERE final_date IS NOT NULL
            """
        else:
            # 未指定结束日期，使用最新交易日
            query = """
            SELECT 
                concat(
                    toString(toYear(max_date)),
                    '-',
                    substring('0' || toString(toMonth(max_date)), -2),
                    '-',
                    substring('0' || toString(toDayOfMonth(max_date)), -2)
                ) AS t_date_str
            FROM (
                SELECT max(date) AS max_date
                FROM stock_data.index_k
                WHERE code = 'sh.000001' AND date <= toDate(%(end_date)s)
            )
            WHERE max_date IS NOT NULL
            """
        
        params = {'end_date': end_date_str}
        
        result = db.fetch_all(query, params)
        
        if not result or not result[0][0]:
            raise Exception("无法确定T日，交易日历中未找到有效数据")
        
        t_date_str = str(result[0][0])
        print(f"确定的T日为: {t_date_str}")
        return t_date_str
        
    except Exception as e:
        print(f"获取交易日历或确定T日失败: {e}")
        raise
  
# ----------------------------
# 工具函数：四种格式之间自由转换时间格式
# ----------------------------
def convert_date_format(
    input_date: Union[str, date, np.datetime64], 
    output_type: int
) -> Union[str, date, np.datetime64]:
    """
    日期格式转换工具函数
    
    参数:
        input_date: 输入的日期，可能是以下格式之一：
                   1. 'YYYYMMDD'字符串 (如 '20231120')
                   2. 'YYYY-MM-DD'字符串 (如 '2023-11-20')
                   3. datetime.date 对象
                   4. numpy.datetime64 对象
        output_type: 输出类型，取值为1-4：
                   1 -> 'YYYYMMDD'字符串
                   2 -> 'YYYY-MM-DD'字符串
                   3 -> datetime.date 对象
                   4 -> numpy.datetime64 对象
    
    返回:
        转换后的日期对象
    
    异常:
        ValueError: 如果输入日期格式无法识别或输出类型无效
    """
    # 第一步：统一转换为YYYY-MM-DD字符串
    yyyy_mm_dd = None
    
    if isinstance(input_date, str):
        # 处理字符串输入
        if re.match(r'^\d{8}$', input_date):  # YYYYMMDD格式
            yyyy_mm_dd = f"{input_date[:4]}-{input_date[4:6]}-{input_date[6:8]}"
        elif re.match(r'^\d{4}-\d{2}-\d{2}$', input_date):  # YYYY-MM-DD格式
            yyyy_mm_dd = input_date
        else:
            raise ValueError(f"无法识别的日期字符串格式: {input_date}")
    elif isinstance(input_date, date):  # datetime.date对象
        yyyy_mm_dd = input_date.strftime("%Y-%m-%d")
    elif isinstance(input_date, np.datetime64):  # numpy.datetime64对象
        yyyy_mm_dd = str(input_date.astype('datetime64[D]')).replace('-', '-')
    else:
        raise ValueError(f"不支持的输入类型: {type(input_date)}")
    
    # 验证转换后的YYYY-MM-DD格式是否有效
    try:
        datetime.strptime(yyyy_mm_dd, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"无效的日期: {yyyy_mm_dd}")
    
    # 第二步：根据输出类型转换格式
    if output_type == 1:  # YYYYMMDD字符串
        return yyyy_mm_dd.replace("-", "")
    elif output_type == 2:  # YYYY-MM-DD字符串
        return yyyy_mm_dd
    elif output_type == 3:  # datetime.date对象
        return datetime.strptime(yyyy_mm_dd, "%Y-%m-%d").date()
    elif output_type == 4:  # numpy.datetime64对象
        return np.datetime64(yyyy_mm_dd)
    else:
        raise ValueError(f"无效的输出类型: {output_type} (必须是1-4)")
  
# ----------------------------
# 要淘汰的工具函数：获取 T 日 和 T-n+1 日
# ----------------------------
def get_n_before_T_date(client: Client, n: int, specified_end_date_str: str = None) -> Tuple[str, str]:
    """
    根据指定日期或最新日期获取 T 日，并返回 T 日 和 T-n+1 日 的字符串。
    Args:
        client (Client): 已连接的ClickHouse客户端。
        n (int): 回溯的交易日天数 (n 必须大于 1)。
        specified_end_date_str (str, optional): 配置文件中指定的结束日期 (YYYYMMDD)。
    Returns:
        tuple[str, str]: (T日字符串 YYYY-MM-DD, T-n+1日字符串 YYYY-MM-DD)。
                         如果失败，则抛出异常。
    """
    if n <= 1:
        raise ValueError("参数 n 必须大于 1。")
    print(f"正在获取交易日历并确定T日及T-{n-1}日...")
    try:
        # 获取足够多的交易日用于确定T日 (最多回溯 n + 30 天)
        lookback_days = n + 30 # 确保有足够的历史数据
        if specified_end_date_str:
            try:
                end_date_for_query = datetime.strptime(specified_end_date_str, '%Y%m%d').date()
            except ValueError as e:
                print(f"配置文件中的 EndDate 格式错误 ({specified_end_date_str})，将忽略该设置: {e}")
                # specified_end_date_str = datetime.now().date() # 这里不需要赋值，因为下面会用到默认值
        else:
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
        # --- 确定T日逻辑 (与 get_t_date 相同) ---
        t_date = None
        if specified_end_date_str:
            try:
                specified_date = datetime.strptime(specified_end_date_str, '%Y%m%d').date()
                print(f"配置文件指定了结束日期: {specified_date.strftime('%Y-%m-%d')}")
                if specified_date in all_trading_dates:
                    t_date = specified_date
                    print(f"指定日期 {t_date.strftime('%Y-%m-%d')} 是交易日，将作为T日。")
                else:
                    for trade_date in all_trading_dates:
                        if trade_date < specified_date:
                            t_date = trade_date
                            break
                    if t_date:
                        print(f"指定日期 {specified_date.strftime('%Y-%m-%d')} 不是交易日，最近的交易日是 {t_date.strftime('%Y-%m-%d')}，将作为T日。")
                    else:
                        t_date = all_trading_dates[0]
                        print(f"在回溯范围内未找到早于指定日期的交易日，使用最新的交易日 {t_date.strftime('%Y-%m-%d')} 作为T日。")
            except ValueError as e:
                print(f"配置文件中的 EndDate 格式错误 ({specified_end_date_str})，将忽略该设置: {e}")
        if t_date is None:
            t_date = all_trading_dates[0]
            print(f"未指定有效结束日期，使用最新交易日 {t_date.strftime('%Y-%m-%d')} 作为T日。")
        # --- 结束T日确定 ---
        # --- 确定 T-n+1 日逻辑 ---
        # 从 all_trading_dates 中找到 t_date 及之前的所有交易日
        relevant_trading_dates = [d for d in all_trading_dates if d <= t_date]
        relevant_trading_dates.sort() # 升序排列
        if len(relevant_trading_dates) < n:
             raise Exception(f"在T日({t_date})之前只找到 {len(relevant_trading_dates)} 个交易日，不足{n}个。")
        # 取最后 n 个
        final_trading_dates = relevant_trading_dates[-n:]
        t_n_minus_1_date = final_trading_dates[0]   # T-n+1 日 (例如 n=6, 则是 T-5)
        # --- 结束 T-n+1 日确定 ---
        # 打印确认后的日期范围
        t_date_str = t_date.strftime('%Y-%m-%d') # T日
        t_n_minus_1_date_str = t_n_minus_1_date.strftime('%Y-%m-%d') # T-n+1日
        print(f"确定的最近{n}个交易日: {[d.strftime('%Y-%m-%d') for d in final_trading_dates]}")
        print(f"实际分析日期范围: {t_n_minus_1_date_str} 至 {t_date_str}")
        return t_date_str, t_n_minus_1_date_str
    except Exception as e:
        print(f"获取交易日历或确定T日/T-{n-1}日失败: {e}")
        raise # 重新抛出异常，让调用者处理

# ----------------------------
# 要淘汰的工具函数：获取 T 日 和 T+n-1 日
# ----------------------------
def get_n_after_T_date(client: Client, n: int, specified_start_date_str: str = None) -> Tuple[str, str]:
    """
    根据指定日期或最新日期获取 T 日，并返回 T 日 和 T+n-1 日 的字符串。
    Args:
        client (Client): 已连接的ClickHouse客户端。
        n (int): 展望的交易日天数 (n 必须大于 1)。
        specified_start_date_str (str, optional): 配置文件中指定的起始日期 (格式 YYYYMMDD)。
                                                   该日期将被视为 T 日候选，或用于寻找最近的 T 日。
    Returns:
        tuple[str, str]: (T日字符串 YYYY-MM-DD, T+n-1日字符串 YYYY-MM-DD)。
                         如果失败，则抛出异常。
    """
    # 1. 参数校验
    if n <= 1:
        raise ValueError("参数 n 必须大于 1。")
    if not client:
        raise ValueError("参数 client 不能为空。")

    print(f"正在获取交易日历并确定T日及T+{n-1}日...")

    try:
        # 2. 确定 T 日查询的参考点和范围
        # 使用指定日期或当前日期作为参考
        if specified_start_date_str:
            try:
                # 尝试解析指定的起始日期
                reference_date = datetime.strptime(specified_start_date_str, '%Y%m%d').date()
                print(f"配置文件指定了起始日期参考点: {reference_date.strftime('%Y-%m-%d')}")
            except ValueError as e:
                print(f"配置文件中的 StartDate 格式错误 ({specified_start_date_str})，将使用当前日期作为参考: {e}")
                reference_date = datetime.now().date()
        else:
            reference_date = datetime.now().date()
            print(f"未指定起始日期，将使用当前日期 {reference_date.strftime('%Y-%m-%d')} 作为参考点。")

        # 为了确保能找到 T 日及之后的 n 个交易日，需要向未来看一段日期
        # 假设每周 5 个交易日，n 个工作日大约需要 n/5 * 7 个自然日。为保险起见，多加 10 天。
        lookahead_days = n + 10
        start_date_for_query = reference_date # 从参考日期开始查
        end_date_for_query = reference_date + timedelta(days=lookahead_days) # 向未来看

        # 3. 查询交易日历 (未来的交易日)
        trading_calendar_query = """
        SELECT date
        FROM stock_data.index_k
        WHERE code = 'sh.000001' AND date >= %(start_date)s AND date <= %(end_date)s
        ORDER BY date ASC -- 升序排列，最早的在前
        """
        trading_dates_result = client.execute(
            trading_calendar_query,
            {
                'start_date': start_date_for_query.strftime('%Y-%m-%d'),
                'end_date': end_date_for_query.strftime('%Y-%m-%d')
            }
        )

        # 4. 处理查询结果
        if not trading_dates_result:
            raise Exception(f"在 {start_date_for_query} 至 {end_date_for_query} 范围内，交易日历中未找到任何交易日。")

        # 处理日期类型并排序 (升序)
        all_trading_dates = []
        for row in trading_dates_result:
            d = row[0]
            if isinstance(d, np.datetime64):
                dt = pd.to_datetime(d).to_pydatetime()
                all_trading_dates.append(dt.date() if hasattr(dt, 'date') else dt)
            else:
                # 假设已经是 date 或 datetime 对象
                all_trading_dates.append(d if not hasattr(d, 'date') else d.date())
        
        # 确保是升序 (虽然 SQL 已排序，但再确认一下)
        all_trading_dates.sort() # 升序: 最早的在前

        # 5. 确定 T 日 (T date)
        # 逻辑：找到大于等于 reference_date 的第一个交易日，或者如果 reference_date 是交易日，则使用它。
        t_date = None
        if specified_start_date_str:
            # 如果指定了日期，优先检查该日期是否为交易日
            if reference_date in all_trading_dates:
                t_date = reference_date
                print(f"指定的参考日期 {t_date.strftime('%Y-%m-%d')} 是交易日，将作为T日。")
            else:
                # 否则，寻找 reference_date 之后的第一个交易日
                for trade_date in all_trading_dates:
                    if trade_date > reference_date: # 注意：是大于，不是大于等于，因为 reference_date 已经检查过不是交易日
                        t_date = trade_date
                        break
                if t_date:
                    print(f"指定的参考日期 {reference_date.strftime('%Y-%m-%d')} 不是交易日，最近的下一个交易日是 {t_date.strftime('%Y-%m-%d')}，将作为T日。")
                else:
                    # 理论上不太可能，因为 lookahead_days 应该足够大
                    raise Exception(f"在参考日期 {reference_date} 之后未找到交易日。")
        else:
            # 如果未指定日期，使用 reference_date (即今天) 之后的第一个交易日，或如果今天是交易日则使用今天
            # 由于 reference_date 就是今天，逻辑与上面类似：先看今天是不是，不是就找下一个
            # 但 reference_date 已经是 all_trading_dates 中或之后的日期了
            # 更简单的逻辑：直接找 all_trading_dates 中 >= reference_date 的第一个
            for trade_date in all_trading_dates:
                 if trade_date >= reference_date:
                     t_date = trade_date
                     break
            if t_date:
                 print(f"使用参考日期 {reference_date.strftime('%Y-%m-%d')} 之后的第一个交易日 {t_date.strftime('%Y-%m-%d')} 作为T日。")
            else:
                 raise Exception(f"在参考日期 {reference_date} 之后未找到交易日。")

        if t_date is None:
             # 这个分支理论上不会到达，因为上面的逻辑已经覆盖了
             raise Exception("无法确定T日。")

        # 6. 确定 T+n-1 日 (T plus n minus 1 date)
        # 从 all_trading_dates 中找到 t_date 及之后的所有交易日
        relevant_trading_dates = [d for d in all_trading_dates if d >= t_date]
        # relevant_trading_dates 已经是升序排列
        if len(relevant_trading_dates) < n:
             raise Exception(f"从T日({t_date})开始，只找到 {len(relevant_trading_dates)} 个交易日，不足{n}个。")

        # 取前 n 个 (从 T 日开始的 n 个交易日)
        final_trading_dates = relevant_trading_dates[:n]
        t_plus_n_minus_1_date = final_trading_dates[-1] # T+N-1 日 (例如 n=5, 则是 T+4)

        # 7. 返回结果
        t_date_str = t_date.strftime('%Y-%m-%d') # T日
        t_plus_n_minus_1_date_str = t_plus_n_minus_1_date.strftime('%Y-%m-%d') # T+N-1日
        print(f"确定的未来{n}个交易日: {[d.strftime('%Y-%m-%d') for d in final_trading_dates]}")
        print(f"实际分析日期范围: {t_date_str} 至 {t_plus_n_minus_1_date_str}")
        return t_date_str, t_plus_n_minus_1_date_str

    except Exception as e:
        print(f"获取交易日历或确定T日/T+{n-1}日失败: {e}")
        raise # 重新抛出异常，让调用者处理

# ----------------------------
# 工具函数：获取交易日历
# ----------------------------
def fetch_trading_calendar(
    db: ClickHouseDB,
    start_date_str: str = None, 
    end_date_str: str = None
) -> List[str]: 
    """
    获取指定指数的交易日历。
    
    Args:
        db (ClickHouseDB): ClickHouse数据库连接对象。
        start_date_str (str, optional): 查询开始日期 (YYYYMMDD 格式)。
        end_date_str (str, optional): 查询结束日期 (YYYYMMDD 格式)。
        
    Returns:
        List[str]: 交易日列表 (按日期升序排列)，每个日期为 YYYYMMDD 格式的字符串。
    """
    query = "SELECT date FROM stock_data.index_k WHERE code = %(index_code)s"
    params = {'index_code': 'sh.000001'}
    
    # 处理开始日期参数
    if start_date_str:
        if not (isinstance(start_date_str, str) and len(start_date_str) == 8 and start_date_str.isdigit()):
            print(f"警告：start_date_str '{start_date_str}' 格式不正确，应为 YYYYMMDD。")
        query += " AND date >= %(start_date)s"
        try:
            dt_obj = datetime.strptime(start_date_str, '%Y%m%d')
            params['start_date'] = dt_obj.strftime('%Y-%m-%d')
        except ValueError:
            print(f"警告：start_date_str '{start_date_str}' 无法解析为日期。")
    
    # 处理结束日期参数
    if end_date_str:
        if not (isinstance(end_date_str, str) and len(end_date_str) == 8 and end_date_str.isdigit()):
            print(f"警告：end_date_str '{end_date_str}' 格式不正确，应为 YYYYMMDD。")
        query += " AND date <= %(end_date)s"
        try:
            dt_obj = datetime.strptime(end_date_str, '%Y%m%d')
            params['end_date'] = dt_obj.strftime('%Y-%m-%d')
        except ValueError:
            print(f"警告：end_date_str '{end_date_str}' 无法解析为日期。")
    
    query += " ORDER BY date"
    
    try:
        results = db.fetch_all(query, params)
        trading_dates_str_list = []
        
        for row in results:
            dt_obj = row[0]
            if isinstance(dt_obj, (date, datetime)):
                date_str = dt_obj.strftime('%Y%m%d')
            else:
                try:
                    date_str = pd.to_datetime(dt_obj).strftime('%Y%m%d')
                except Exception as convert_e:
                    print(f"警告：无法转换日期对象 {dt_obj}，跳过。错误: {convert_e}")
                    continue
            trading_dates_str_list.append(date_str)
            
        return trading_dates_str_list
        
    except Exception as e:
        print(f"获取交易日历失败: {e}")
        return []

# ----------------------------
# 工具函数：按照日期查询多支股票行情
# ----------------------------
def fetch_stock_data_for_date(
    db: ClickHouseDB, 
    target_date: Union[date, str], 
    stock_codes: List[str]
) -> List[Dict[str, Any]]:
    """
    从ClickHouse数据库获取指定日期的一组股票的日K线数据。

    Args:
        db (ClickHouseDB): ClickHouse数据库连接对象。
        target_date (Union[date, str]): 目标交易日日期。
                                           如果是字符串，应为 'YYYY-MM-DD' 或 'YYYYMMDD' 格式。
        stock_codes (List[str]): 股票代码列表。

    Returns:
        List[Dict[str, Any]]: 查询结果列表。每个元素是一个字典，
                               包含 'code', 'date', 'open', 'high', 'low', 'close',
                               'preclose', 'volume', 'amount', 'turn', 'tradestatus', 'isST', 'adjustflag' 等字段。
                               如果某只股票在该日期没有数据，则不包含在返回列表中。
                               如果查询失败，可能抛出异常。
    """
    if not stock_codes:
        return []
        
    # 1. 格式化日期
    if isinstance(target_date, date):
        date_str = target_date.strftime('%Y-%m-%d')
    elif isinstance(target_date, str):
        # 尝试解析不同格式的日期字符串
        try:
            # 假设是 'YYYY-MM-DD'
            date_obj = datetime.strptime(target_date, '%Y-%m-%d').date()
        except ValueError:
            try:
                # 假设是 'YYYYMMDD'
                date_obj = datetime.strptime(target_date, '%Y%m%d').date()
            except ValueError:
                raise ValueError(f"无法解析日期字符串 '{target_date}'，请使用 'YYYY-MM-DD' 或 'YYYYMMDD' 格式。")
        date_str = date_obj.strftime('%Y-%m-%d')
    else:
        raise TypeError("target_date 必须是 datetime.date 对象或字符串。")

    # 2. 准备 SQL 查询
    # 确保 stock_codes 中的代码是字符串并去除空格
    cleaned_codes = [str(code).strip() for code in stock_codes if code]
    
    if not cleaned_codes:
        return []

    # 3. 使用参数化查询（更安全的方式）
    # 构建占位符
    placeholders = ', '.join([f'%({i})s' for i in range(len(cleaned_codes))])
    
    query = f"""
        SELECT 
            code, 
            date, 
            open, 
            high, 
            low, 
            close, 
            preclose, 
            volume, 
            amount, 
            turn, 
            tradestatus, 
            isST, 
            adjustflag
        FROM 
            stock_data.daily_k
        WHERE 
            date = %(target_date)s 
            AND code IN ({placeholders})
    """
    
    # 准备参数
    params = {'target_date': date_str}
    for i, code in enumerate(cleaned_codes):
        params[str(i)] = code

    # 4. 执行查询
    try:
        rows = db.fetch_all(query, params)
        
        # 5. 处理结果
        column_names = [
            'code', 'date', 'open', 'high', 'low', 'close', 
            'preclose', 'volume', 'amount', 'turn', 'tradestatus', 'isST', 'adjustflag'
        ]
        
        result = []
        for row in rows:
            # 将每一行元组转换为字典
            row_dict = dict(zip(column_names, row))
            result.append(row_dict)
            
        return result

    except Exception as e:
        print(f"[ERROR] 查询 {date_str} 的股票数据失败: {e}")
        raise

# ----------------------------
# 工具函数：将长格式 DataFrame 转换为宽格式
# ----------------------------
def pivot_to_wide_format(df_long: pd.DataFrame) -> pd.DataFrame:
    """
    将包含 '交易日' 和 '股票代码' 列的长格式 DataFrame
    转换为宽格式：每行一个交易日，列为 交易日, 股票代码1, 股票代码2, ...
    """
    if df_long.empty:
        # Return an empty DataFrame with the expected structure
        return pd.DataFrame(columns=['交易日'])

    # 1. 重置索引，为每个交易日内的股票创建序号
    df_reset = df_long.reset_index(drop=True)
    df_reset['row_id'] = df_reset.index

    # 2. 为每个交易日内的股票分配序号 (股票1, 股票2, ...)
    df_reset['stock_order'] = df_reset.groupby('交易日')['row_id'].rank(method='first').astype(int)
    
    # 3. 创建新的列名 '股票代码X'
    df_reset['stock_col'] = '股票代码' + df_reset['stock_order'].astype(str)

    # 4. 透视 (Pivot) 数据
    df_wide = df_reset.pivot(index='交易日', columns='stock_col', values='股票代码')
    
    # 5. 重置索引，使 '交易日' 成为普通列
    df_wide.reset_index(inplace=True)
    
    # 6. 确保列的顺序：'交易日' 在前，然后是 '股票代码1', '股票代码2', ...
    # 获取所有 '股票代码X' 列并排序
    stock_cols = [col for col in df_wide.columns if col.startswith('股票代码')]
    stock_cols.sort(key=lambda x: int(x.replace('股票代码', ''))) # 按数字排序
    # 重新排列列
    new_column_order = ['交易日'] + stock_cols
    df_wide = df_wide[new_column_order]

    # 7. 可选：清理列名 (如果 pivot 后有 '股票代码' 作为名称)
    # df_wide.columns.name = None # 如果需要，可以取消注释

    # print(f"数据已从长格式 ({len(df_long)} 行) 转换为宽格式 ({len(df_wide)} 行)。")
    return df_wide

# ----------------------------
# 要淘汰的工具函数：保存交易日历到 CSV 文件
# ----------------------------
def save_trading_calendar_to_csv(
    client: Client, 
    output_path: str = "data/trading_calendar.csv",
    start_date_str: str = None,
    end_date_str: str = None
):
    """
    获取交易日历并保存到 CSV 文件。

    Args:
        client (Client): 已连接的 ClickHouse 客户端。
        output_path (str): 输出 CSV 文件的路径。默认为 "data/trading_calendar.csv"。
        start_date_str (str, optional): 查询开始日期 (YYYYMMDD 格式)。
        end_date_str (str, optional): 查询结束日期 (YYYYMMDD 格式)。
    """

    try:
        print(f"正在获取交易日历数据...")
        # 1. 调用 fetch_trading_calendar 获取数据
        trading_dates_list = fetch_trading_calendar(
            client, 
            start_date_str=start_date_str, 
            end_date_str=end_date_str
        )

        if not trading_dates_list:
            print("警告：获取到的交易日历为空，将创建空的 CSV 文件。")
            # 创建一个空的 DataFrame，但仍包含列名
            df_calendar = pd.DataFrame(columns=['date'])
        else:
            # 2. 将 YYYYMMDD 字符串列表转换为 DataFrame
            # fetch_trading_calendar 返回的是 YYYYMMDD 格式的字符串列表
            df_calendar = pd.DataFrame({'date': trading_dates_list})
            print(f"获取到 {len(df_calendar)} 个交易日的数据。")

        # 3. 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"已创建目录: {output_dir}")

        # 4. 保存到 CSV 文件
        df_calendar.to_csv(output_path, index=False)
        print(f"交易日历已成功保存至: {output_path}")

    except Exception as e:
        print(f"保存交易日历到 CSV 文件时出错: {e}")
        raise # 重新抛出异常，让调用者知道发生了错误

# ----------------------------
# 要淘汰的工具函数：加载交易日历 (CSV)
# ----------------------------
def load_trading_calendar() -> List[str]:
    """
    加载交易日历
    
    Returns:
        交易日列表 (YYYYMMDD 字符串)
    """
    calendar_path = "data/trading_calendar.csv"
    if os.path.exists(calendar_path):
        df = pd.read_csv(calendar_path)
        
        # --- 关键修改：强制转换为字符串 ---
        # 确保 'date' 列是字符串类型。
        # fillna('') 处理可能的 NaN 值。
        # astype(str) 将所有元素（包括 int64）转换为字符串。
        df['date'] = df['date'].fillna('').astype(str)
        
        # 可选：过滤掉可能的空字符串（如果原始CSV中有空行）
        df = df[df['date'] != '']
        
        # 返回字符串列表
        return df['date'].tolist()
    else:
        # 如果没有交易日历文件，返回示例数据 (确保是字符串)
        print(f"警告: 未找到交易日历文件 {calendar_path}，使用示例日期。")
        return ["20240102", "20240103", "20240104", "20240105", "20240106"]


# ----------------------------
# 原有工具函数：加载市场数据 (CSV)
# ----------------------------
def load_market_data(date: str) -> Dict[str, Dict[str, Any]]:
    """
    加载指定日期的市场数据
    
    Args:
        date: 日期字符串 (YYYY-MM-DD)
        
    Returns:
        股票市场数据字典
    """
    file_path = f"data/market_data/market_data_{date.replace('-', '')}.csv"
    if not os.path.exists(file_path):
        return {}
    
    df = pd.read_csv(file_path)
    market_data = {}
    
    for _, row in df.iterrows():
        stock = row['stock']
        market_data[stock] = {
            'open': row['open'],
            'close': row['close'],
            'high': row['high'],
            'low': row['low'],
            'volume': row['volume'],
            'suspended': row.get('suspended', False)
        }
    
    return market_data


# ----------------------------
# 原有工具函数：加载选股清单 (CSV)
# ----------------------------
def load_selected_stocks(date: str) -> List[str]:
    """
    加载指定日期的选股清单
    
    Args:
        date: 日期字符串 (YYYY-MM-DD)
        
    Returns:
        股票代码列表
    """
    file_path = f"data/stock_lists/stock_list_{date.replace('-', '')}.csv"
    if not os.path.exists(file_path):
        return []
    
    df = pd.read_csv(file_path)
    return df['stock'].tolist()


# ----------------------------
# 原有工具函数：获取未来N个交易日
# ----------------------------
def get_next_n_trading_days(start_date: str, n: int, trading_calendar: List[str]) -> str:
    """
    获取从start_date开始的第n个交易日
    
    Args:
        start_date: 起始日期
        n: 天数
        trading_calendar: 交易日历
        
    Returns:
        第n个交易日
    """
    try:
        start_idx = trading_calendar.index(start_date)
        return trading_calendar[start_idx + n]
    except (ValueError, IndexError):
        return None


# ----------------------------
# 工具函数：加载策略配置文件 (YAML)
# ----------------------------
def load_config(config_path: str) -> Dict[str, Any]:
    """
    加载策略配置文件 (YAML)
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典
    """
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    return config


def get_strategy_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取策略配置
    
    Args:
        config: 完整配置字典
        
    Returns:
        策略配置字典
    """
    return config.get('strategy', {})
