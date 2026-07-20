"""
Windows Named Pipes 信号通讯模块
用于 RSS 系统各组件间的事件驱动通讯
"""
import threading
import time
from multiprocessing.connection import Listener, Client

# 管道名称定义
PIPE_TASK_READY = r'\\.\pipe\rss_task_ready'      # Fetcher -> Engine
PIPE_RESULT_READY = r'\\.\pipe\rss_result_ready'  # Engine -> Pusher


class SignalSender:
    """信号发送器（非阻塞）"""
    
    @staticmethod
    def send(pipe_name: str, message: str = "CHECK") -> bool:
        """
        向指定管道发送信号
        
        Args:
            pipe_name: 管道名称（如 PIPE_TASK_READY）
            message: 信号内容，默认为 "CHECK"
        
        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        try:
            conn = Client(pipe_name)
            conn.send(message)
            conn.close()
            return True
        except FileNotFoundError:
            # 管道不存在（Listener 未启动），静默失败
            print(f"[SignalSender] 管道 {pipe_name} 未就绪，跳过信号发送")
            return False
        except Exception as e:
            print(f"[SignalSender] 发送信号失败: {e}")
            return False


class SignalListener:
    """
    信号监听器（阻塞式，可设超时）
    
    使用方法:
        listener = SignalListener(PIPE_TASK_READY, timeout=60)
        while True:
            signal = listener.wait()  # 阻塞，60秒超时
            if signal:
                print(f"收到信号: {signal}")
            # 无论是否收到信号，都可以执行后续逻辑
    """
    
    def __init__(self, pipe_name: str, timeout: int = 60):
        """
        初始化监听器
        
        Args:
            pipe_name: 要监听的管道名称
            timeout: 等待超时时间（秒），超时后返回 None
        """
        self.pipe_name = pipe_name
        self.timeout = timeout
        self._listener = None
        self._lock = threading.Lock()
        self._queue = []  # 信号队列
        self._stop_event = threading.Event()
        self._worker_thread = None

    def _ensure_listener(self):
        """确保 Listener 已启动且工作线程在运行"""
        with self._lock:
            if self._listener is None:
                try:
                    self._listener = Listener(self.pipe_name)
                    print(f"[SignalListener] 管道 {self.pipe_name} 已启动监听")
                    
                    # 启动后台工作线程
                    self._stop_event.clear()
                    self._worker_thread = threading.Thread(target=self._listen_loop, daemon=True)
                    self._worker_thread.start()
                except OSError as e:
                    if "Only one usage" in str(e) or "address already in use" in str(e).lower():
                        print(f"[SignalListener] 管道已被占用，可能有另一个实例正在运行")
                    raise

    def _listen_loop(self):
        """后台监听循环"""
        while not self._stop_event.is_set():
            try:
                # accept 是阻塞的，但由于 context manager 或 close() 能够中断它
                conn = self._listener.accept()
                msg = conn.recv()
                conn.close()
                with self._lock:
                    self._queue.append(msg)
            except Exception:
                if self._stop_event.is_set():
                    break
                # 出错时稍微等下重试
                time.sleep(1)

    def wait(self) -> str | None:
        """
        等待信号（非阻塞式检查队列，如果没有则进入等待）
        
        Returns:
            收到信号时返回信号内容，超时返回 None
        """
        self._ensure_listener()
        
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            with self._lock:
                if self._queue:
                    return self._queue.pop(0)
            
            # 短暂休眠避免占用过多 CPU
            time.sleep(0.5)
            
        return None

    
    def close(self):
        """关闭监听器"""
        with self._lock:
            if self._listener:
                self._listener.close()
                self._listener = None
                print(f"[SignalListener] 管道 {self.pipe_name} 已关闭")


# 便捷函数
def notify_engine():
    """通知 Engine 有新任务"""
    return SignalSender.send(PIPE_TASK_READY)

def notify_pusher():
    """通知 Pusher 有新结果"""
    return SignalSender.send(PIPE_RESULT_READY)


if __name__ == "__main__":
    # 简单测试：运行此脚本作为 Listener
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "send":
        # 发送模式
        print("发送信号测试...")
        success = notify_engine()
        print(f"发送结果: {'成功' if success else '失败'}")
    else:
        # 监听模式
        print("启动信号监听测试（按 Ctrl+C 退出）...")
        listener = SignalListener(PIPE_TASK_READY, timeout=10)
        try:
            while True:
                print("等待信号...")
                signal = listener.wait()
                if signal:
                    print(f"✓ 收到信号: {signal}")
                else:
                    print("- 超时，继续等待...")
        except KeyboardInterrupt:
            listener.close()
            print("测试结束")
