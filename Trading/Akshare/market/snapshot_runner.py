import sys
import os
import time
import threading
import pandas as pd
from datetime import datetime
from typing import List

# 确保能导入同级模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market.ck_client import ClickHouseClient
from market.providers.base import BaseSnapshotProvider
from market.providers.tencent import TencentSnapshotProvider

import toml

# 配置
class SnapshotRunner:
    def __init__(self, provider: BaseSnapshotProvider):
        self.provider = provider
        
        # Load Config for interval and stop_time
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.toml")
        with open(config_path, "r", encoding="utf-8") as f:
            config = toml.load(f)
            self.interval = config.get("monitor", {}).get("snapshot_interval", 10)
            self.stop_time = config.get("monitor", {}).get("stop_time", "15:10")
            
        self.ck_client = ClickHouseClient() # 主线程连接，用于初始化
        self.stock_list: List[str] = []
        
    def initialize(self):
        """初始化检查：交易日、股票列表、由谁来清表"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 1. 交易日检查
        check_sql = f"SELECT is_trading_day FROM trade_calendar WHERE date = '{today_str}' AND exchange = 'SSE'"
        res = self.ck_client.query_df(check_sql)
        if res.empty or res['is_trading_day'].iloc[0] == 0:
            print(f"今日 ({today_str}) 非交易日，不执行任务。")
            return False
            
        # 2. 也是从 trade_calendar 获取上一个交易日 (避免查不到数据)
        prev_sql = f"SELECT prev_trading_date FROM trade_calendar WHERE date = '{today_str}' AND exchange = 'SSE'"
        prev_res = self.ck_client.query_df(prev_sql)
        if prev_res.empty:
            print(f"无法确定上一个交易日，初始化失败。")
            return False
        # 确保转换为字符串 YYYY-MM-DD
        prev_date_val = prev_res['prev_trading_date'].iloc[0]
        prev_date = pd.to_datetime(prev_date_val).strftime("%Y-%m-%d")
        
        # 3. 加载股票列表
        stocks_sql = f"SELECT distinct code FROM stock_kline_day WHERE date = '{prev_date}'"
        stocks_df = self.ck_client.query_df(stocks_sql)
        if stocks_df.empty:
            print(f"上一交易日 ({prev_date}) 无日线数据，无法构建票池。")
            return False
            
        self.stock_list = stocks_df['code'].tolist()
        print(f"已加载 {len(self.stock_list)} 只标的 (From: {prev_date})")
        
        # 4. 触发式清理 (只清理非当天的数据)
        try:
            today_date = datetime.now().date()
            time_query = "SELECT MAX(snapshot_time) as max_time FROM stock_snapshot_intraday"
            time_res = self.ck_client.query_df(time_query)
            
            should_truncate = False
            if time_res.empty or pd.isna(time_res['max_time'].iloc[0]):
                print("Table is empty, no cleanup needed.")
            else:
                last_update_date = pd.to_datetime(time_res['max_time'].iloc[0]).date()
                if last_update_date < today_date:
                    print(f"Detected old data from {last_update_date}, truncating...")
                    should_truncate = True
                else:
                    print(f"Detected today's data ({last_update_date}), skipping truncate to allow resume.")
            
            if should_truncate:
                self.ck_client.command("TRUNCATE TABLE stock_snapshot_intraday")
                self.ck_client.command("TRUNCATE TABLE concept_snapshot_intraday")
                print("Intraday tables truncated.")
        except Exception as e:
            print(f"Warning: Cleanup logic encountered error: {e}")
            
        return True

    def is_trading_hour(self) -> bool:
        """判断当前是否为交易时间段"""
        now = datetime.now().time()
        # 1. 集合竞价: 09:15 - 09:25
        # 2. 早盘: 09:30 - 11:30
        # 3. 午盘: 13:00 - 15:30
        # 注意: 这里的判断比较宽松，包含起止端点
        
        # 辅助转换函数：时分秒转秒数，方便比较
        def to_seconds(t): return t.hour * 3600 + t.minute * 60 + t.second
        
        curr = to_seconds(now)
        
        # 定义时间段 (时, 分, 秒)
        stop_h, stop_m = map(int, self.stop_time.split(':'))
        ranges = [
            (9, 15, 0), (9, 25, 0),
            (9, 30, 0), (11, 30, 0),
            (13, 0, 0), (stop_h, stop_m, 0)
        ]
        
        # 转换为秒
        r_secs = [r[0]*3600 + r[1]*60 + r[2] for r in ranges]
        
        if (r_secs[0] <= curr <= r_secs[1]) or \
           (r_secs[2] <= curr <= r_secs[3]) or \
           (r_secs[4] <= curr <= r_secs[5]):
            return True
            
        return False

    def _worker(self, thread_id: int):
        """工作线程逻辑"""
        # 增加时间段检查
        if not self.is_trading_hour():
            # print(f"Thread-{thread_id} skipped: Not in trading hours.")
            return

        snapshot_time = datetime.now()
        start_ts = snapshot_time.strftime("%H:%M:%S")
        
        # 将 CK 标准代码转为 Provider 格式
        provider_codes = [self.provider.format_code(c) for c in self.stock_list]
        
        results = []
        batch_size = self.provider.batch_size
        
        # 抓取循环
        for i in range(0, len(provider_codes), batch_size):
            batch = provider_codes[i : i + batch_size]
            raw_response = self.provider.get_batch(batch)
            if raw_response:
                parsed_list = self.provider.parse(raw_response, snapshot_time)
                results.extend(parsed_list)
        
        duration = (datetime.now() - snapshot_time).total_seconds()
        
        # 入库循环 (每个线程建立独立的 CK 连接)
        if results:
            try:
                # 显式新建连接，避免多线程共用 self.ck_client 可能的冲突
                # (虽然 clickhouse-connect 客户端通常是线程安全的，但稳妥起见)
                worker_ck = ClickHouseClient()
                df = pd.DataFrame(results)
                worker_ck.insert_df("stock_snapshot_intraday", df)
                worker_ck.close()
                print(f"[{start_ts}] Thread-{thread_id} Done. Count: {len(results)}, Cost: {duration:.2f}s")
            except Exception as e:
                print(f"[{start_ts}] Thread-{thread_id} DB Error: {e}")
        else:
            print(f"[{start_ts}] Thread-{thread_id} Empty Result!")

    def run(self):
        if not self.initialize():
            return

        # 计算截止时间
        stop_h, stop_m = map(int, self.stop_time.split(':'))
        now = datetime.now()
        end_time_dt = now.replace(hour=stop_h, minute=stop_m, second=0, microsecond=0)

        print(f"Runner Started. Target End Time: {self.stop_time}")
        
        cnt = 0
        active_threads = []
        
        try:
            while datetime.now() < end_time_dt:
                # 启动新的一轮抓取
                t = threading.Thread(target=self._worker, args=(cnt,))
                t.daemon = True
                t.start()
                active_threads.append(t)
                
                cnt += 1
                time.sleep(self.interval)
                
                # 清理已结束线程
                active_threads = [t for t in active_threads if t.is_alive()]
        except KeyboardInterrupt:
            print("\nStopping runner...")
            
        print("Waiting for pending tasks...")
        for t in active_threads:
            t.join(timeout=10)
        print("All Done.")

if __name__ == "__main__":
    # 在这里切换 Provider 即可切换数据源
    provider = TencentSnapshotProvider()
    runner = SnapshotRunner(provider)
    runner.run()
