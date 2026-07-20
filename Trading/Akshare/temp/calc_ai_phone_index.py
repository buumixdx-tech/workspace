import pandas as pd
import time
import os
from market.ck_client import ClickHouseClient

def calculate_index():
    # 开始总计时
    start_time = time.time()
    
    ck = ClickHouseClient()
    
    # 1. 确定成分股和权重 (直接从同步好的 CK 映射表中拿，或者从 CSV 拿市值)
    # 这里从 CSV 读是因为我们需要“总市值”作为权重，CK 的映射表里目前只有代码
    csv_path = r"d:\WorkSpace\Trading\Akshare\data\pywinauto\008.csv"
    
    # 尝试读取 CSV 并提取市值
    try:
        df_csv = pd.read_csv(csv_path, encoding='gb18030')
    except:
        # 如果 gb18030 失败，尝试 utf-8
        df_csv = pd.read_csv(csv_path, encoding='utf-8-sig')

    # 处理表头混乱的情况，找到“代码”和“总市值”列
    # 同花顺导出的 CSV 列名可能包含 Unnamed，我们通过位置或关键词定位
    code_col = [c for c in df_csv.columns if '代码' in c][0]
    # 总市值通常在位置比较靠后的地方
    # 根据之前查看 001.csv 的经验，总市值大约在第 26 或 32 列左右
    # 我们直接基于内容搜索包含市值的列
    mkt_val_col = None
    for col in df_csv.columns:
        if '总市值' in col and 'Unnamed' not in col:
            mkt_val_col = col
            break
    
    if not mkt_val_col:
        # 如果列名匹配失败，尝试寻找数值特征显著的列(很大且不是代码)
        mkt_val_col = df_csv.columns[26] # 备选位置

    # 标准化代码
    def std_code(c):
        c = str(c).strip()
        if len(c) >= 8:
            return f"{c[:2].lower()}.{c[2:]}"
        return None

    df_csv['std_code'] = df_csv[code_col].apply(std_code)
    df_csv = df_csv.dropna(subset=['std_code'])
    
    # 建立代码到市值的映射
    weights = df_csv.set_index('std_code')[mkt_val_col].to_dict()
    target_codes = list(weights.keys())

    # 2. 从 ClickHouse 提取最新快照数据
    # 为了保证计算的一次性时间准确，我们记录查询开始时刻
    db_start = time.time()
    
    sql = f"""
    SELECT 
        code, 
        price, 
        last_close
    FROM stock_snapshot_intraday
    WHERE code IN {tuple(target_codes)}
    AND snapshot_time = (SELECT max(snapshot_time) FROM stock_snapshot_intraday)
    """
    df_snap = ck.query_df(sql)
    db_end = time.time()

    if df_snap.empty:
        print("❌ 无法从 ClickHouse 提取到成分股的实时快照")
        return

    # 3. 执行加权计算
    weighted_ratio_sum = 0
    total_market_cap = 0
    
    for _, row in df_snap.iterrows():
        code = row['code']
        p = row['price']
        lc = row['last_close']
        
        if lc <= 0 or p <= 0: continue
        
        cap = weights.get(code, 0)
        if cap <= 0: continue
        
        weighted_ratio_sum += (p / lc) * cap
        total_market_cap += cap
    
    if total_market_cap == 0:
        index_val = 1000.0
    else:
        index_val = (weighted_ratio_sum / total_market_cap) * 1000

    # 结束计时
    total_end = time.time()
    
    print(f"\n✅ AI手机 板块指数编制完成")
    print(f"------------------------------------")
    print(f"成 分 股: {len(df_snap)} 只 (已匹配)")
    print(f"当前点位: {index_val:.2f} (基准1000)")
    print(f"------------------------------------")
    print(f"数据库查询耗时: {(db_end - db_start)*1000:.2f} ms")
    print(f"总计算回路耗时: {(total_end - start_time)*1000:.2f} ms")
    
    ck.close()

if __name__ == "__main__":
    calculate_index()
