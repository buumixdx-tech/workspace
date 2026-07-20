"""
事件响应器注册与调度模块
实现轻量级的事件订阅-发布模式（观察者模式）
"""
from typing import Callable, Dict, List
from sqlalchemy.orm import Session

# 全局监听器注册表
# 格式: { "EVENT_TYPE": [listener_func1, listener_func2, ...] }
_listeners: Dict[str, List[Callable]] = {}


def register_listener(event_type: str, listener: Callable):
    """
    注册事件监听器
    
    Args:
        event_type: 事件类型，如 "VC_STATUS_TRANSITION"
        listener: 监听器函数，签名为 (session, event) -> None
    """
    if event_type not in _listeners:
        _listeners[event_type] = []
    _listeners[event_type].append(listener)


def unregister_listener(event_type: str, listener: Callable):
    """移除事件监听器"""
    if event_type in _listeners:
        _listeners[event_type] = [l for l in _listeners[event_type] if l != listener]


def dispatch(session: Session, event):
    """
    分发事件给所有注册的监听器
    
    Args:
        session: 数据库会话
        event: SystemEvent 实例
    """
    event_type = event.event_type
    listeners = _listeners.get(event_type, [])
    
    for listener in listeners:
        try:
            listener(session, event)
        except Exception as e:
            # 记录错误但不中断其他监听器
            print(f"[EventDispatcher] Listener error for {event_type}: {e}")


def get_registered_listeners() -> Dict[str, int]:
    """返回已注册的监听器统计"""
    return {k: len(v) for k, v in _listeners.items()}
