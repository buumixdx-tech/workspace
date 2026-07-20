import akshare as ak
import time
import pandas as pd
from market.ck_client import ClickHouseClient

def calculate_index():
    loop_start = time.time()
    ck = ClickHouseClient()
    
    # 1. 成员读取 (从 CK 映射表读，极快)
    codes = ck.query_df("SELECT stock_code FROM finance_concept_components WHERE concept_name = 'AI手机'")['stock_code'].tolist()
    
    # 2. 权重获取 (为了避开网络不稳定，如果是生产环境建议存入 CK)
    # 既然 CSV 没了，我们通过 ak.stock_info_a_code_銘牌 (这里用一个更稳定的)
    # 或者直接用 spot 数据进行一次过滤
    try:
        # 只抓取一次基本面快照作为权重基数
        df_base = ak.stock_zh_a_spot_em()
        df_base['std_code'] = df_base.apply(lambda x: f"{'sh' if x['代码'].startswith('6') or x['代码'].startswith('9') else 'sz'}.{x['代码']}", axis=1)
        # 建立 股票代码 -> 总市值 的映射
        weights = df_base[df_base['std_code'].isin(codes)].set_index('std_code')['总市值'].to_dict()
    except:
        print("⚠️ 权重获取慢，尝试备选快速通道...")
        weights = {c: 1.0 for c in codes} # 降级为等权（仅作演示，实际应有权重）

    # 3. 核心计算环节 (从全市场 Snapshot 提取一次快照时间的数据)
    calc_internal_start = time.time()
    
    # 联表查询最新价格和昨收
    sql = f"""
    SELECT 
        code, price, last_close, snapshot_time
    FROM stock_snapshot_intraday
    WHERE code IN {tuple(codes)}
    AND snapshot_time = (SELECT max(snapshot_time) FROM stock_snapshot_intraday)
    """
    df_snap = ck.query_df(sql)
    
    if df_snap.empty:
        print("❌ 未在 CK 中找到成分股快照数据")
        return

    # 指数加权计算
    total_mkt_cap = 0
    weighted_sum = 0
    for _, row in df_snap.iterrows():
        c = row['code']
        mv = weights.get(c, 1.0) # 权重
        if row['last_close'] > 0:
            weighted_sum += (row['price'] / row['last_close']) * mv
            total_mkt_cap += mv
    
    index_val = (weighted_sum / total_mkt_cap) * 1000 if total_mkt_cap > 0 else 1000
    
    calc_internal_end = time.time()
    loop_end = time.time()

    print(f"\n📈 AI手机 指数实时计算报告")
    print(f"------------------------------------")
    print(f"指数点位: {index_val:.2f} (点)")
    print(f"快照时间: {df_snap['snapshot_time'].iloc[0]}")
    print(f"成分股数: {len(df_snap)}")
    print(f"------------------------------------")
    print(f"✅ 单次纯逻辑计算耗时: {(calc_internal_end - calc_internal_start)*1000:.2f} ms")
    print(f"✅ 全流程(含IO/DB)耗时: {(loop_end - loop_start)*1000:.2f} ms")
    
    ck.close()

if __name__ == "__main__":
    calculate_index()
