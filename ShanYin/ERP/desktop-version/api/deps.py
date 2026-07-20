from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from models import get_session


def get_db():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def verify_api_key(x_api_key: str = Header(None)):
    pass  # API key verification disabled


def row_to_dict(obj):
    """将 SQLAlchemy model 实例转为 dict，处理 datetime 和 JSON 字段。"""
    d = {}
    for c in inspect(obj).mapper.column_attrs:
        val = getattr(obj, c.key)
        if isinstance(val, datetime):
            val = val.isoformat()
        d[c.key] = val
    return d


def paginate(session: Session, query, page: int = 1, size: int = 50):
    """通用分页，返回 {items, total, page, size}。"""
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return {"items": [row_to_dict(i) for i in items], "total": total, "page": page, "size": size}


def parse_ids(ids: Optional[str]) -> Optional[List[int]]:
    """解析逗号分隔的 ID 字符串，如 "1,2,3" → [1, 2, 3]"""
    if not ids:
        return None
    parts = [x.strip() for x in ids.split(",") if x.strip()]
    invalid = [p for p in parts if not p.isdigit()]
    if invalid:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"无效的 ID 格式: {', '.join(invalid)}")
    id_list = [int(p) for p in parts]
    return id_list if id_list else None


def get_or_404(session: Session, model: Any, record_id: int, resource_name: str = None) -> Any:
    """查询单条记录，不存在则抛出 NotFoundError。"""
    obj = session.query(model).get(record_id)
    if obj is None:
        from api.middleware.error_handler import raise_not_found_error
        name = resource_name or model.__name__
        raise_not_found_error(name, str(record_id))
    return obj


def api_success(data: Any = None, meta: Dict[str, Any] = None) -> Dict[str, Any]:
    """构造标准成功响应。"""
    resp: Dict[str, Any] = {"success": True, "data": data, "error": None}
    if meta:
        resp["meta"] = meta
    return resp


def api_error(code: str, message: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
    """构造标准错误响应（用于路由层直接返回）。格式与 ErrorHandlerMiddleware 一致。"""
    err: Dict[str, Any] = {"code": code, "message": message}
    if details:
        err["details"] = details
    return {"success": False, "error": err}
