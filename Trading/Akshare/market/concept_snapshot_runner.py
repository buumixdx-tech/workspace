import time
import os
import toml
import pandas as pd
from datetime import datetime
from market.ck_client import ClickHouseClient

def get_config():
    """从上级目录加载配置文件 config.toml"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.toml")
    with open(config_path, "r", encoding="utf-8") as f:
        return toml.load(f)

def is_trading_day():
    """判断今日是否为交易日 (查询 trade_calendar 表)"""
    ck = ClickHouseClient()
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        check_sql = f"SELECT is_trading_day FROM trade_calendar WHERE date = '{today_str}' AND exchange = 'SSE'"
        res = ck.query_df(check_sql)
        return not res.empty and res['is_trading_day'].iloc[0] == 1
    except:
        return False
    finally:
        ck.close()

def is_trading_hour():
    """判断当前是否为交易时间段 (与 snapshot_runner 一致)"""
    config = get_config()
    stop_time = config.get("monitor", {}).get("stop_time", "15:10")
    stop_h, stop_m = map(int, stop_time.split(':'))
    
    now = datetime.now().time()
    def to_seconds(t): return t.hour * 3600 + t.minute * 60 + t.second
    curr = to_seconds(now)
    
    # 时段定义: 09:15-09:25 (竞价), 09:30-11:30 (早盘), 13:00-stop_time (午盘)
    ranges = [(9,15,0), (9,25,0), (9,30,0), (11,30,0), (13,0,0), (stop_h, stop_m, 0)]
    r_secs = [r[0]*3600 + r[1]*60 + r[2] for r in ranges]
    
    if (r_secs[0] <= curr <= r_secs[1]) or \
       (r_secs[2] <= curr <= r_secs[3]) or \
       (r_secs[4] <= curr <= r_secs[5]):
        return True
    return False

# 全局状态变量
_last_exec_time = 0
_last_processed_snap = None 

# 核心 SQL 模板: 严格涨跌停统计逻辑
# 规则说明：北交所 30%, 科创/创业 20%, ST 5%, 主板 10%
CONCEPT_CALC_SQL_TEMPLATE = """
    SELECT
        concept_name,
        date,
        snapshot_time,
        
        -- 计算价格指数
        ifNotFinite(round(1000 * total_mv / last_mv, 2), 1000) as price_index,
        -- 计算涨跌幅
        ifNotFinite(round((total_mv / last_mv - 1) * 100, 2), 0) as pct_chg,
        -- 计算市值变动
        ifNotFinite(round((total_mv - last_mv) / 100000000.0, 2), 0) as change,
        
        volume,
        amount,
        turnover_rate,
        
        rise_count,
        fall_count,
        flat_count,
        
        limit_up_count,
        limit_down_count,
        
        suspended_count,
        stock_count,
        
        -- 补齐 K 线字段
        price_index as open,
        price_index as high,
        price_index as low,
        1000.0 as last_close

    FROM (
        SELECT
            c.concept_name,
            toDate('{latest_snap}') as date,
            '{latest_snap}' as snapshot_time,
            
            -- 核心聚合指标
            sumIf(total_market_cap, is_suspended = 0) as total_mv,
            sumIf(total_market_cap * if(price > 0, last_close / price, 1), is_suspended = 0) as last_mv,
            
            round(sumIf(volume, is_suspended = 0) / 10000.0, 2) as volume,
            round(sumIf(amount, is_suspended = 0) / 100000000.0, 2) as amount,
            round(sumIf(turnover_rate * total_market_cap, is_suspended = 0) / sumIf(total_market_cap, is_suspended = 0), 2) as turnover_rate,
            
            countIf(s.pct_chg > 0 and is_suspended = 0) as rise_count,
            countIf(s.pct_chg < 0 and is_suspended = 0) as fall_count,
            countIf(s.pct_chg = 0 and is_suspended = 0) as flat_count,
            
            -- 严格涨停判定 (Inner Query) - 严格等于 (允许 0.001 误差)
            countIf(
                is_suspended = 0 AND 
                s.price > 0 AND
                abs(s.price - round(s.last_close * (1 + 
                    multiIf(
                        s.code LIKE 'bj.%', 0.30,
                        s.code LIKE 'sz.30%' OR s.code LIKE 'sh.688%', 0.20,
                        s.name LIKE '%ST%', 0.05,
                        0.10
                    )
                ), 2)) < 0.005
            ) as limit_up_count,
            
            -- 严格跌停判定 (Inner Query) - 严格等于 (允许 0.001 误差)
            countIf(
                is_suspended = 0 AND 
                s.price > 0 AND
                abs(s.price - round(s.last_close * (1 - 
                    multiIf(
                        s.code LIKE 'bj.%', 0.30,
                        s.code LIKE 'sz.30%' OR s.code LIKE 'sh.688%', 0.20,
                        s.name LIKE '%ST%', 0.05,
                        0.10
                    )
                ), 2)) < 0.005
            ) as limit_down_count,
            
            countIf(is_suspended = 1) as suspended_count,
            count() as stock_count
            
        FROM stock_snapshot_intraday s
        INNER JOIN view_concept_components_filtered c ON s.code = c.stock_code
        WHERE s.snapshot_time = '{latest_snap}'
        GROUP BY c.concept_name
    )
"""

def calculate_all_concepts():
    global _last_exec_time, _last_processed_snap
    
    # 1. 物理冷却锁 (5秒)
    now_ts = time.time()
    if now_ts - _last_exec_time < 5:
        return True
    _last_exec_time = now_ts
    
    # 2. 交易时间强制检查
    if not is_trading_hour():
        return False

    ck = ClickHouseClient()
    start_time = time.time()
    
    # 3. 数据版本一致性检查 (防止原地空转)
    # 只有当个股快照有更新时，板块计算才有意义
    try:
        latest_snap_df = ck.query_df("SELECT max(snapshot_time) as t FROM stock_snapshot_intraday")
        if latest_snap_df.empty or pd.isna(latest_snap_df['t'].iloc[0]):
            ck.close()
            return False
        
        latest_snap = latest_snap_df['t'].iloc[0]
        
        # 如果这个时刻的数据已经处理过，直接退出
        if str(latest_snap) == str(_last_processed_snap):
            ck.close()
            return True
        
        _last_processed_snap = latest_snap

        # 执行 SQL 计算
        sql = CONCEPT_CALC_SQL_TEMPLATE.format(latest_snap=latest_snap)
        df_result = ck.query_df(sql)
        
        if not df_result.empty:
            # 关键修复：确保时间字段是以 datetime 对象存储
            df_result['date'] = pd.to_datetime(df_result['date']).dt.date
            df_result['snapshot_time'] = pd.to_datetime(df_result['snapshot_time'])
            
            # 存入数据库
            ck.insert_df("concept_snapshot_intraday", df_result)
            
            duration = (time.time() - start_time) * 1000
            print(f"[{latest_snap}] ✅ 已更新 {len(df_result)} 个板块指数. 耗时: {duration:.2f} ms")
            return True
            
    except Exception as e:
        print(f"❌ 板块计算出错: {e}")
        return False
    finally:
        ck.close()

def run_scheduler():
    config = get_config()
    interval = config.get("monitor", {}).get("concept_update_interval", 60)
    print(f"🚀 板块指数编制引擎已启动 ({interval}秒/次)...")
    
    while True:
        # 1. 检查交易日
        if not is_trading_day():
            time.sleep(3600)
            continue
            
        # 2. 检查交易具体时段
        if is_trading_hour():
            calculate_all_concepts()
        
        time.sleep(interval)

if __name__ == "__main__":
    run_scheduler()
