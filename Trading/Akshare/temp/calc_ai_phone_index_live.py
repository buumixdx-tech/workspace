import pandas as pd
import akshare as ak
import time
from market.ck_client import ClickHouseClient

def calculate_ai_phone_index():
    start_all = time.time()
    ck = ClickHouseClient()
    
    # 1. 确定成分股列表
    sql_comp = "SELECT stock_code FROM finance_concept_components WHERE concept_name = 'AI手机'"
    codes_df = ck.query_df(sql_comp)
    if codes_df.empty:
        print("❌ 数据库中未找到 AI手机 板块成分股")
        return
    
    codes = codes_df['stock_code'].tolist()
    print(f"📊 已找到 {len(codes)} 只成分股")

    # 2. 获取总市值作为权重 (由于表里没存，现场抓取一次基础数据)
    # 取 A 股最新实时行情，从中提取总市值
    print("🚀 正在获取成分股市值权重...")
    try:
        df_spot = ak.stock_zh_a_spot_em()
        # 转换代码格式 sh600000 -> sh.600000
        df_spot['std_code'] = df_spot.apply(lambda x: f"{'sh' if x['代码'].startswith('6') else 'sz'}.{x['代码']}", axis=1)
        
        # 提取总市值 (总市值在 A股现货数据中名为 '总市值')
        weights = df_spot[df_spot['std_code'].isin(codes)].set_index('std_code')['总市值'].to_dict()
    except Exception as e:
        print(f"❌ 获取市值失败: {e}")
        return

    # 3. 从 ClickHouse 提取最新日内快照
    db_start = time.time()
    sql_snap = f"""
    SELECT 
        code, 
        price, 
        last_close,
        snapshot_time
    FROM stock_snapshot_intraday
    WHERE code IN ({",".join([f"'{c}'" for c in codes])})
    AND snapshot_time = (SELECT max(snapshot_time) FROM stock_snapshot_intraday)
    """
    df_snap = ck.query_df(sql_snap)
    db_time = (time.time() - db_start) * 1000

    if df_snap.empty:
        print("❌ ClickHouse 中没有相关股票的 snapshot 数据")
        return

    # 4. 指数编制 (总市值加权)
    # 基数 1000，计算公式: 1000 * Σ(当前价/昨收 * 市值) / Σ市值
    total_val = 0
    weighted_ratio = 0
    match_count = 0
    
    for _, row in df_snap.iterrows():
        c = row['code']
        p = row['price']
        lc = row['last_close']
        mv = weights.get(c, 0)
        
        if lc > 0 and mv > 0:
            weighted_ratio += (p / lc) * mv
            total_val += mv
            match_count += 1
            
    if total_val == 0:
        index_value = 1000.0
    else:
        index_value = (weighted_ratio / total_val) * 1000

    end_all = time.time()
    
    print(f"\n✅ AI手机 板块指数 (日内)")
    print(f"------------------------------------")
    print(f"计算基准: 1000.00 (以昨收位为准)")
    print(f"当前点位: {index_value:.2f}")
    print(f"涨 跌 幅: {((index_value/1000)-1)*100:.2f}%")
    print(f"快照时间: {df_snap['snapshot_time'].iloc[0]}")
    print(f"匹配权重: {match_count} / {len(codes)}")
    print(f"------------------------------------")
    print(f"DB 查询耗时: {db_time:.2f} ms")
    print(f"总流程耗时: {(end_all - start_all)*1000:.2f} ms")

    ck.close()

if __name__ == "__main__":
    calculate_ai_phone_index()
