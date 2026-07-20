import threading
import time
import sys
import os
from datetime import datetime
import toml

# Local imports
from market.snapshot_runner import SnapshotRunner
from market.providers.tencent import TencentSnapshotProvider
from market.concept_snapshot_runner import calculate_all_concepts
from market_analysis.bus_engine import RealtimeAnalysisEngine
from notification.telegram_bot import TelegramBot
from notification.state_manager import StateManager
from notification.gen_dict import generate_concept_dict

# Configuration Loader
def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.toml")
    with open(config_path, "r", encoding="utf-8") as f:
        return toml.load(f)

class MonitorService:
    def __init__(self):
        # 1. Load Config
        full_config = load_config()
        self.config = full_config.get("monitor", {})
        
        # 2. Get Intervals
        self.analysis_interval = self.config.get("analysis_interval", 60)
        self.concept_interval = self.config.get("concept_update_interval", 60)
        self.stop_time = self.config.get("stop_time", "15:10")

        # 3. Initialize Sub-services
        self.market_provider = TencentSnapshotProvider()
        self.snapshot_runner = SnapshotRunner(self.market_provider)
        
        self.analysis_engine = RealtimeAnalysisEngine()
        self.bot = TelegramBot()
        self.state_manager = StateManager()
        
        self.running = False
        self.threads = []

    def _concept_update_loop(self):
        """
        后台循环：每分钟重新聚合一次全市场的板块指数
        """
        print("Concept Snapshot Engine Started...")
        while self.running:
            try:
                calculate_all_concepts()
            except Exception as e:
                print(f"Concept Update Error: {e}")
            time.sleep(self.concept_interval)

    def _analysis_loop(self):
        """
        后台循环：执行策略匹配与报警发送
        """
        print("Strategy Analysis Engine Started...")
        while self.running:
            try:
                # 执行核心推荐逻辑 (冲板 + AI知识匹配)
                result = self.analysis_engine.generate_recommendation()
                
                if result:
                    # 状态管理：只推送新增（Diff Logic）
                    diff_result = self.state_manager.extract_new_items(result)
                    
                    if diff_result:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔥 发现新增异动机会，推送中...")
                        # 切换为压缩数据推送
                        self.bot.send_compressed_market_data(diff_result)
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] 行情无新增异动 (Silent)")
                
            except Exception as e:
                print(f"Analysis Loop Error: {e}")
                
            time.sleep(self.analysis_interval)

    def start(self):
        # --- 增加防止多开的锁机制 ---
        lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".monitor.lock")
        if os.path.exists(lock_file):
            with open(lock_file, "r") as f:
                old_pid = f.read().strip()
            # 检查该 PID 是否真的还在运行 (简单判断)
            if old_pid:
                print(f"⚠️ 警告: 监控服务似乎已经在运行 (PID: {old_pid})。")
                print(f"如果是异常关闭，请手动删除文件: {lock_file}")
                return

        # 写入当前 PID
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))

        self.running = True
        print(f"🚀 实时行情监控全链路服务启动... (PID: {os.getpid()})")
        
        # [新增] 启动前先同步当天的板块字典
        print("Checking concept dictionary...")
        try:
            generate_concept_dict()
        except Exception as e:
            print(f"Warning: Dictionary sync failed: {e}")
        
        try:
            # 1. 启动个股快照抓取 (10秒/次)
            t_snap = threading.Thread(target=self.snapshot_runner.run)
            t_snap.daemon = True
            t_snap.start()
            self.threads.append(t_snap)
            
            # 2. 启动板块指数聚合计算 (1分钟/次)
            t_concept = threading.Thread(target=self._concept_update_loop)
            t_concept.daemon = True
            t_concept.start()
            self.threads.append(t_concept)
            
            # 3. 启动策略分析引擎 (1分钟/次)
            t_analysis = threading.Thread(target=self._analysis_loop)
            t_analysis.daemon = True
            t_analysis.start()
            self.threads.append(t_analysis)
            
            print(f"All services launched. Target Stop Time: {self.stop_time}. Press Ctrl+C to stop.")
            
            stop_h, stop_m = map(int, self.stop_time.split(':'))
            
            while self.running:
                now = datetime.now()
                # 如果当前时间已过 15:10 (且在 12点以后，避免凌晨误判)
                if now.hour > stop_h or (now.hour == stop_h and now.minute >= stop_m):
                    if now.hour >= 12:
                        print(f"\n[{now.strftime('%H:%M:%S')}] 达到设定停止时间 ({self.stop_time})，正在自动关闭服务...")
                        break
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping services...")
        finally:
            self.running = False
            # 清理锁文件
            if os.path.exists(lock_file):
                os.remove(lock_file)
            print("Monitor process cleaned up.")

if __name__ == "__main__":
    service = MonitorService()
    service.start()
