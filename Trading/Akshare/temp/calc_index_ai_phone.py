import pandas as pd
import time
from market.ck_client import ClickHouseClient

def calculate_ai_phone_index():
    start_time = time.time()
    ck = ClickHouseClient()
    
    # 1. 加载 AI手机 的成分股和权重 (总市值)
    # 根据 Table.xls 的顺序，AI手机 对应 008.csv
    csv_path = "data/pywinauto/008.csv"
    try:
        df_csv = pd.read_csv(csv_path, encoding='utf-8-sig')
    except:
        df_csv = pd.read_csv(csv_path, encoding='gb18030')
    
    # 清洗代码并映射总市值
    # 同花顺的 代码 是 SZ301377 -> sz.301377
    def format_code(c):
        c = str(c).strip()
        if len(c) >= 8:
            return f"{c[:2].lower()}.{c[2:]}"
        return None

    df_csv['std_code'] = df_csv['代码'].apply(format_code)
    df_csv = df_csv.dropna(subset=['std_code'])
    
    # 提取总市值作为权重
    # 注意：这里的总市值可能是亿元或者元，我们需要统一比例即可
    weights = df_csv.set_index('std_code')['总市值'].to_dict()
    target_codes = list(weights.keys())
    
    # 2. 从 ClickHouse 提取最新快照
    # 假设我们取最新的一个 snapshot_time 的数据
    sql = f"""
    SELECT 
        code, 
        price, 
        last_close,
        snapshot_time
    FROM stock_snapshot_intraday
    WHERE code IN {tuple(target_codes)}
    AND snapshot_time = (SELECT max(snapshot_time) FROM stock_snapshot_intraday)
    """
    df_snap = ck.query_df(sql)
    
    if df_snap.empty:
        print("❌ 未能在 ClickHouse 中找到成分股的 snapshot 数据")
        ck.close()
        return

    snapshot_time = df_snap['snapshot_time'].iloc[0]
    
    # 3. 指数计算
    # 基数 1000
    # Formula: Index = 1000 * (Σ (Price_Ratio * Weight)) / Σ Weight
    
    total_weight = 0
    weighted_ratio_sum = 0
    
    for _, row in df_snap.iterrows():
        code = row['code']
        price = row['price']
        last_close = row['last_close']
        
        if last_close == 0: continue
        
        weight = weights.get(code, 0)
        ratio = price / last_close
        
        weighted_ratio_sum += (ratio * weight)
        total_weight += weight
        
    if total_weight == 0:
        index_value = 1000
    else:
        index_value = (weighted_ratio_sum / total_weight) * 1000
        
    end_time = time.time()
    calc_duration = (end_time - start_time) * 1000 # 毫秒

    print(f"--- AI手机 指数计算结果 ---")
    print(f"快照时间: {snapshot_time}")
    print(f"成分股数量: {len(df_snap)}")
    print(f"当前指数点位: {index_value:.2f}")
    print(f"计算耗时: {calc_duration:.2f} ms")
    
    ck.close()

if __name__ == "__main__":
    calculate_ai_phone_index()
