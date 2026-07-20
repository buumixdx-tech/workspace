import sys
import os
import akshare as ak
import pandas as pd
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from market.providers.tencent import TencentSnapshotProvider

def format_code(code):
    """
    格式化股票代码，补全前后缀
    """
    code = str(code).strip().zfill(6)
    if code.startswith('6'):
        return f"SH.{code}"
    elif code.startswith('0') or code.startswith('3'):
        return f"SZ.{code}"
    elif code.startswith('8') or code.startswith('4') or code.startswith('92'):
        return f"BJ.{code}"
    else:
        return f"SZ.{code}"

def fetch_and_clean_data():
    """
    获取全市场实时行情数据，并进行清洗、格式化和状态判定。
    返回处理后的 DataFrame。
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始获取并处理基础数据...")
    
    # ---------------------------------------------------------
    # 1. 获取基础行情数据
    # ---------------------------------------------------------
    print("正在获取全市场股票列表 (ak.stock_info_a_code_name)...")
    try:
        df_info = ak.stock_info_a_code_name()
        raw_codes = df_info["code"].tolist()
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return pd.DataFrame()
        
    def code_to_tencent(code):
        code = str(code).strip().zfill(6)
        if code.startswith('6'):
            return f"sh{code}"
        elif code.startswith('0') or code.startswith('3'):
            return f"sz{code}"
        elif code.startswith('8') or code.startswith('4') or code.startswith('92'):
            return f"bj{code}"
        else:
            return f"sz{code}"

    provider_codes = [code_to_tencent(c) for c in raw_codes]
    
    # 获取腾讯快照数据
    print(f"正在通过 TencentProvider 获取全市场实时快照 ({len(provider_codes)}只)...")
    provider = TencentSnapshotProvider()
    batch_size = provider.batch_size
    
    results = []
    now_dt = datetime.now()
    
    def fetch_batch(batch):
        txt = provider.get_batch(batch)
        if txt:
            return provider.parse(txt, now_dt)
        return []

    batches = [provider_codes[i:i+batch_size] for i in range(0, len(provider_codes), batch_size)]
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_batch, b) for b in batches}
        for future in as_completed(futures):
            try:
                data = future.result()
                results.extend(data)
            except Exception:
                pass

    if not results:
        print("未获取到实时行情数据！")
        return pd.DataFrame()

    df_spot = pd.DataFrame(results)

    # 筛选并重命名列
    df = df_spot.rename(columns={
        "code": "股票代码",
        "name": "股票简称",
        "price": "今天收盘价",
        "last_close": "前一交易日收盘价",
        "total_market_cap": "总市值",
        "float_market_cap": "流通市值"
    })
    
    required_cols = ["股票代码", "股票简称", "今天收盘价", "前一交易日收盘价", "总市值", "流通市值"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"错误: 缺失列 {missing}, 现有列: {df.columns.tolist()}")
        return pd.DataFrame()

    df = df[required_cols].copy()

    # ---------------------------------------------------------
    # 2. 数据清洗与格式化
    # ---------------------------------------------------------
    
    # 2.1 格式化股票代码
    print("正在格式化股票代码...")
    # TencentProvider 产出的是 sh.600000 格式，转化为 SH.600000
    df["股票代码"] = df["股票代码"].str.upper()

    # 2.2 转换数值类型
    numeric_cols = ["今天收盘价", "前一交易日收盘价", "总市值", "流通市值"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # ---------------------------------------------------------
    # 3. 处理停牌状态 (ak.stock_tfp_em)
    # ---------------------------------------------------------
    print("正在获取停牌数据 (stock_tfp_em)...")
    try:
        today_str = datetime.now().strftime("%Y%m%d")
        df_tfp = ak.stock_tfp_em(date=today_str)
        
        suspension_map = {} 
        
        if not df_tfp.empty:
            for _, row in df_tfp.iterrows():
                raw_code = str(row['代码']).strip().zfill(6)
                suspension_map[raw_code] = {
                    "停牌时间": row.get('停牌时间', ''),
                    "预计复牌时间": row.get('预计复牌时间', pd.NaT)
                }
    except Exception as e:
        print(f"获取停牌数据失败: {e}")
        suspension_map = {}

    # 定义状态判定函数
    def determine_status(row):
        full_code = row['股票代码']
        raw_code = full_code.split('.')[-1]
        
        info = suspension_map.get(raw_code)
        
        if info:
            suspend_date_str = str(info['停牌时间'])[:10]
            try:
                suspend_date = datetime.strptime(suspend_date_str, "%Y-%m-%d")
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                
                if suspend_date > today:
                    return "预计停牌", suspend_date_str
                else:
                    return "停牌", suspend_date_str
            except:
                return "停牌", suspend_date_str
        else:
            return "正常", None

    # 应用状态判定
    status_results = df.apply(determine_status, axis=1)
    df["交易状态"] = [x[0] for x in status_results]
    df["停牌日期"] = [x[1] for x in status_results]

    # ---------------------------------------------------------
    # 4. 判定是否ST
    # ---------------------------------------------------------
    df["是否st"] = df["股票简称"].apply(lambda x: "是" if "ST" in str(x).upper() else "否")

    # ---------------------------------------------------------
    # 5. 退市股剔除
    # ---------------------------------------------------------
    # 规则: 交易状态为“正常”，但没有今日收盘价的（NaN 或 0），判定为退市股票，直接删除。
    print(f"剔除退市股前数量: {len(df)}")
    
    mask_to_drop = (
        (df["交易状态"] == "正常") & 
        ((df["今天收盘价"].isna()) | (df["今天收盘价"] == 0))
    )
    
    df_clean = df[~mask_to_drop].copy()
    print(f"剔除退市股后数量: {len(df_clean)}")
    
    return df_clean
