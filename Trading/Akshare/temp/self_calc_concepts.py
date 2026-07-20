import time
import pandas as pd
from market.ck_client import ClickHouseClient

def aggregate_concept_data():
    start_time = time.time()
    ck = ClickHouseClient()
    
    # 1. 核心聚合 SQL：
    # 逻辑：联表 finance_concept_components 获取板块成员。
    # 这里的 pct_chg 是个股涨跌幅，我们通过 avg(pct_chg) 实现等权板块涨跌。
    # 如果要加权，则需要关联市值表。
    sql = """
    SELECT
        c.concept_name,
        round(avg(s.pct_chg), 2) as pct_chg,
        round(sum(s.amount) / 100000000, 2) as amount_on, -- 亿元
        countIf(s.pct_chg > 0) as rise_count,
        countIf(s.pct_chg < 0) as fall_count,
        count() as stock_count,
        max(s.snapshot_time) as snap_time
    FROM stock_snapshot_intraday s
    INNER JOIN finance_concept_components c ON s.code = c.stock_code
    WHERE s.snapshot_time = (SELECT max(snapshot_time) FROM stock_snapshot_intraday)
    GROUP BY c.concept_name
    ORDER BY pct_chg DESC
    """
    
    calc_start = time.time()
    df_result = ck.query_df(sql)
    calc_end = time.time()
    
    print(f"\n📊 全市场板块聚合报告 (基于个股 Snapshot 自研计算)")
    print(f"--------------------------------------------------")
    print(f"当前时间轴: {df_result['snap_time'].max()}")
    print(f"板块总数: {len(df_result)}")
    print(f"\n🚀 实时涨幅榜前10 (等权计算):")
    print(df_result[['concept_name', 'pct_chg', 'amount_on', 'rise_count', 'fall_count']].head(10).to_string(index=False))
    
    print(f"\n--------------------------------------------------")
    print(f"🏎️  ClickHouse 聚合计算耗时: {(calc_end - calc_start)*1000:.2f} ms")
    print(f"⏱️  端到端总回路耗时: {(time.time() - start_time)*1000:.2f} ms")
    
    ck.close()

if __name__ == "__main__":
    aggregate_concept_data()
