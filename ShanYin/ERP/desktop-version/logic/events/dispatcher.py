from sqlalchemy.orm import Session
from datetime import datetime
import json

def emit_event(session: Session, event_type: str, aggregate_type: str, aggregate_id: int, payload: dict = None):
    """
    发布领域事件并持久化到数据库
    同时触发所有已注册的监听器
    """
    # 延迟导入以避免循环依赖 (models.py -> dispatcher.py -> models.py)
    from models import SystemEvent
    
    event = SystemEvent(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload or {},
        created_at=datetime.now()
    )
    session.add(event)
    session.flush()  # 确保 event.id 已生成
    
    # 分发给所有注册的监听器
    from logic.events.listeners import dispatch
    dispatch(session, event)
    
    # 不在这里 commit，交给 Action 的事务控制
    return event
