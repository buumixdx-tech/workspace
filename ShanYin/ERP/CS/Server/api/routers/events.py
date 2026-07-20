import json
import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from api.deps import get_db, verify_token, api_success
from models import SystemEvent
from logic.api_queries import list_recent_events, mark_events_pushed

router = APIRouter(prefix="/api/v1/events", tags=["事件"], dependencies=[Depends(verify_token)])


@router.get("/stream", summary="SSE 实时事件流")
async def event_stream(session: Session = Depends(get_db)):
    """
    订阅系统事件的 Server-Sent Events 流。
    使用请求级 session + 事件标记推送状态，客户端断开时优雅退出。
    """
    async def generate():
        last_id = 0
        try:
            while True:
                events = session.query(SystemEvent).filter(
                    SystemEvent.id > last_id,
                    SystemEvent.pushed_to_ai == False
                ).order_by(SystemEvent.id).limit(20).all()

                event_ids_to_mark = []
                for event in events:
                    data = {
                        "id": event.id,
                        "event_type": event.event_type,
                        "aggregate_type": event.aggregate_type,
                        "aggregate_id": event.aggregate_id,
                        "payload": event.payload,
                        "created_at": event.created_at.isoformat() if event.created_at else None,
                    }
                    yield {
                        "id": str(event.id),
                        "event": event.event_type,
                        "data": json.dumps(data, ensure_ascii=False),
                    }
                    event_ids_to_mark.append(event.id)
                    last_id = event.id

                if event_ids_to_mark:
                    mark_events_pushed(session, event_ids_to_mark)
                    session.commit()

                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(generate())


@router.get("/recent", summary="最近事件列表")
def get_recent_events(page: int = 1, size: int = 20, event_type: str = None,
                      aggregate_type: str = None, session: Session = Depends(get_db)):
    """分页获取最近事件，支持按事件类型和聚合对象类型筛选。"""
    return api_success(list_recent_events(session, page=page, size=size,
                                          event_type=event_type, aggregate_type=aggregate_type))
