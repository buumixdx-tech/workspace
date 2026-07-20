import akshare as ak
import pandas as pd
from market.ck_client import ClickHouseClient
from datetime import datetime

def sync_total_shares():
    print("🚀 正在从东方财富获取全市场总股本数据...")
    ck = ClickHouseClient()
    
    try:
        # 获取最新实时看板
        df_spot = ak.stock_zh_a_spot_em()
        
        # 逻辑：总股本 = 总市值 / 最新价
        # 数据单位处理：东方财富的总市值单位通常是元
        data = []
        now = datetime.now()
        
        for _, row in df_spot.iterrows():
            code = str(row['代码'])
            price = float(row['最新价'])
            mkt_cap = float(row['总市值'])
            
            if price > 0:
                shares = mkt_cap / price
                market = "sh" if code.startswith('6') or code.startswith('9') else "sz"
                std_code = f"{market}.{code}"
                
                data.append({
                    'code': std_code,
                    'total_shares': shares,
                    'update_time': now
                })
        
        if data:
            df_shares = pd.DataFrame(data)
            # 批量更新 securities_info 表
            # 直接插入，ReplacingMergeTree 会根据 code 覆盖旧的值
            ck.insert_df("securities_info", df_shares)
            print(f"✅ 成功同步 {len(df_shares)} 只股票的总股本权重数据")
            
    except Exception as e:
        print(f"❌ 同步失败: {e}")
    finally:
        ck.close()

if __name__ == "__main__":
    sync_total_shares()
