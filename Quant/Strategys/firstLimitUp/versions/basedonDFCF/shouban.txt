import pandas as pd
import numpy as np
import os
from datetime import datetime

# ----------------------------
# 1. 工具函数：判断是否涨停
# ----------------------------
def is_limit_up(row, board_type):
    """
    判断当日是否涨停
    :param row: DataFrame 的一行，包含 preclose, close, high
    :param board_type: 'main' 为10%，'gem' 或 'star' 为20%
    :return: 是否涨停 (bool)
    """
    limit_ratio = 0.10 if board_type == 'main' else 0.20
    expected_limit = round(row['preclose'] * (1 + limit_ratio), 2)
    
    # 检查最高价是否达到涨停价（允许±0.01误差）
    is_at_limit = abs(row['high'] - expected_limit) < 0.011
    
    # 检查收盘价是否等于最高价（符合"日内最高价与收盘价一致"的条件）
    closes_at_limit = abs(row['close'] - row['high']) < 0.001
    
    return is_at_limit and closes_at_limit

# ----------------------------
# 2. 根据股票代码判断所属板块
# ----------------------------
def get_board_type(stock_code):
    """
    根据股票代码判断所属板块
    sz.00, sz.001, sz.002, sz.003 开头：主板（10%）
    sz.30 开头：创业板（20%）
    sh.60, sh.600, sh.601, sh.603 开头：主板（10%）
    sh.688 开头：科创板（20%）
    """
    if stock_code.startswith('sz.00') or stock_code.startswith('sz.001') or \
       stock_code.startswith('sz.002') or stock_code.startswith('sz.003') or \
       stock_code.startswith('sh.600') or stock_code.startswith('sh.601') or \
       stock_code.startswith('sh.603'):
        return 'main'
    elif stock_code.startswith('sz.30') or stock_code.startswith('sh.688'):
        return 'gem'
    else:
        return 'main'  # 默认主板

# ----------------------------
# 3. 主程序
# ----------------------------
def analyze_stocks():
    # 路径设置
    base_path = '.'
    shoubandata_file = os.path.join(base_path, 'shoubandata.xlsx')
    shoupan_file = os.path.join(base_path, 'shouban.xlsx')
    result_file = os.path.join(base_path, 'result.xlsx')

    # 读取 shoubandata.xlsx 获取股票信息
    df_info = pd.read_excel(shoubandata_file)
    
    # 标准化股票代码为字符串，补零到6位
    df_info['股票代码'] = df_info['股票代码'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(6)
    
    # 构建股票信息字典
    stock_info_dict = {}
    for _, row in df_info.iterrows():
        code = row['股票代码']
        # 清理股票简称和行业中的空格
        name = str(row['股票简称']).strip().replace('Ａ', 'A')
        industry = str(row['所属行业']).strip()
        stock_info_dict[code] = {
            '股票简称': name,
            '所属行业': industry
        }

    # 读取 shouban.xlsx 所有 sheet
    try:
        xl_file = pd.ExcelFile(shoupan_file)
    except FileNotFoundError:
        raise FileNotFoundError(f"未找到文件: {shoupan_file}")

    results = []

    for sheet_name in xl_file.sheet_names:
        # 标准化 sheet 名（股票代码）
        code_raw = str(sheet_name).strip()
        if not code_raw.isdigit() or len(code_raw) != 6:
            continue  # 跳过无效 sheet 名

        code_6d = code_raw  # 如 '000153'

        # 映射为 tushare 风格代码
        if code_6d.startswith('0') or code_6d.startswith('3'):
            ts_code = f"sz.{code_6d}"
        elif code_6d.startswith('6'):
            ts_code = f"sh.{code_6d}"
        else:
            continue

        # 获取股票信息
        if code_6d not in stock_info_dict:
            name = "未知"
            industry = "未知"
        else:
            name = stock_info_dict[code_6d]['股票简称']
            industry = stock_info_dict[code_6d]['所属行业']

        # 读取该股票的6天日K数据
        try:
            df = xl_file.parse(sheet_name)
            
            # 确保列名小写，并只保留我们需要的列
            df.columns = [col.lower() for col in df.columns]
            required_cols = ['date', 'open', 'high', 'low', 'close', 'preclose']
            
            # 检查是否存在所有必需的列
            if not all(col in df.columns for col in required_cols):
                print(f"缺少必要列，跳过 sheet: {sheet_name}")
                continue
                
            df = df[required_cols].copy()
        except Exception as e:
            print(f"无法读取 sheet: {sheet_name}, 错误: {str(e)}")
            continue

        if df.empty or len(df) < 1:
            continue

        # 转换日期为 datetime
        try:
            df['date'] = pd.to_datetime(df['date'])
        except:
            print(f"日期格式错误，跳过 sheet: {sheet_name}")
            continue

        # 判断板块
        board_type = get_board_type(ts_code)

        # 判断每日是否涨停
        df['is_limit'] = df.apply(lambda row: is_limit_up(row, board_type), axis=1)

        # 找出涨停日
        limit_up_days = df[df['is_limit']].copy()
        limit_up_count = len(limit_up_days)

        if limit_up_count == 0:
            # 无涨停
            results.append({
                '股票代码': code_6d,
                '股票名称': name,
                '行业': industry,
                '涨停板数': 0,
                '日期': '',
                '板后天数': 0,
                '板后走势': '无涨停',
                '板后最高价': np.nan,
                '板后最低价': np.nan,
                '最高价日期': '',
                '最低价日期': '',
                '板后回调': np.nan
            })
            continue

        # 获取最后一个涨停日
        last_limit_day = limit_up_days.iloc[-1]
        last_limit_date = last_limit_day['date']
        last_limit_close = last_limit_day['close']  # 涨停收盘价

        # 获取涨停后的交易日（严格在 last_limit_date 之后）
        post_limit_df = df[df['date'] > last_limit_date].copy()
        post_days = len(post_limit_df)

        # 板后价格区间：只看 open 和 close
        if post_days > 0:
            all_prices = pd.concat([post_limit_df['open'], post_limit_df['close']])
            post_high = all_prices.max()
            post_low = all_prices.min()

            # 找最高价和最低价对应的日期（优先找最早出现的）
            high_candidates = post_limit_df[(np.isclose(post_limit_df['open'], post_high, atol=0.001)) | 
                                          (np.isclose(post_limit_df['close'], post_high, atol=0.001))]
            low_candidates = post_limit_df[(np.isclose(post_limit_df['open'], post_low, atol=0.001)) | 
                                         (np.isclose(post_limit_df['close'], post_low, atol=0.001))]

            high_date = high_candidates['date'].iloc[0] if len(high_candidates) > 0 else None
            low_date = low_candidates['date'].iloc[0] if len(low_candidates) > 0 else None

            high_date_str = high_date.strftime('%Y-%m-%d') if high_date is not None else ''
            low_date_str = low_date.strftime('%Y-%m-%d') if low_date is not None else ''

            # 计算回调幅度
            # 涨停涨幅 = last_limit_close - preclose
            limit_gain = last_limit_close - last_limit_day['preclose']
            if limit_gain <= 0.001:  # 避免除以0或负数
                callback_ratio = np.nan
            else:
                # 最低价距离涨停价的回落 = last_limit_close - post_low
                drop_from_limit = last_limit_close - post_low
                callback_ratio = drop_from_limit / limit_gain  # 回调占涨停涨幅的比例
        else:
            post_high = np.nan
            post_low = np.nan
            high_date_str = ''
            low_date_str = ''
            callback_ratio = np.nan

        # 判断走势类型
        if post_days == 0:
            trend = '无后续交易日'
        elif pd.isna(post_high) or pd.isna(post_low):
            trend = '数据异常'
        elif post_high > last_limit_close:
            trend = '继续新高'
        elif pd.isna(callback_ratio) or callback_ratio < 0:
            trend = '异常'
        elif 0.10 <= callback_ratio <= 0.75:
            trend = '稳定回调'
        elif callback_ratio > 0.75:
            trend = '过度回调'
        else:
            trend = '微弱回调'

        # 保存结果
        results.append({
            '股票代码': code_6d,
            '股票名称': name,
            '行业': industry,
            '涨停板数': limit_up_count,
            '日期': last_limit_date.strftime('%Y-%m-%d'),
            '板后天数': post_days,
            '板后走势': trend,
            '板后最高价': round(post_high, 2) if not pd.isna(post_high) else np.nan,
            '板后最低价': round(post_low, 2) if not pd.isna(post_low) else np.nan,
            '最高价日期': high_date_str,
            '最低价日期': low_date_str,
            '板后回调': round(callback_ratio * 100, 2) if not pd.isna(callback_ratio) else np.nan
        })

    # ----------------------------
    # 4. 输出结果到 Excel
    # ----------------------------
    if not results:
        print("没有分析结果，无法生成输出文件")
        return

    result_df = pd.DataFrame(results)

    # 重命名列以匹配要求
    result_df = result_df.rename(columns={
        '股票代码': '股票代码',
        '股票名称': '股票名称',
        '行业': '行业',
        '涨停板数': '涨停板数',
        '日期': '最后涨停日',
        '板后天数': '板后天数',
        '板后走势': '板后走势',
        '板后最高价': '板后最高价',
        '板后最低价': '板后最低价',
        '最高价日期': '最高价日期',
        '最低价日期': '最低价日期',
        '板后回调': '板后回调(%)'
    })

    # 调整列顺序
    result_df = result_df[[
        '股票代码', '股票名称', '行业', '涨停板数', '最后涨停日',
        '板后天数', '板后走势', '板后最高价', '板后最低价',
        '最高价日期', '最低价日期', '板后回调(%)'
    ]]

    # 写入 Excel
    result_df.to_excel(result_file, index=False, sheet_name='结果')

    print(f"分析完成，共处理 {len(results)} 只股票，结果已保存至 {result_file}")

# ----------------------------
# 5. 执行
# ----------------------------
if __name__ == '__main__':
    analyze_stocks()