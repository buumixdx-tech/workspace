from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from models import get_session, User
from logic.auth import verify_access_token


def get_db():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def verify_token(authorization: str = Header(None)) -> dict:
    """
    验证 JWT Token 并返回 payload
    用于 FastAPI Depends() 依赖注入

    使用方式:
        @router.get("/xxx")
        def xxx(token_data: dict = Depends(verify_token)):
            user_id = token_data['sub']
            role = token_data['role']
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="未提供认证信息，请登录"
        )

    # 支持 "Bearer <token>" 或直接 "<token>"
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        token = parts[1]
    else:
        token = authorization

    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Token 无效或已过期"
        )

    return payload


def require_admin(token_data: dict = Depends(verify_token)) -> dict:
    """要求是管理员"""
    if token_data.get('role') != 'admin':
        raise HTTPException(
            status_code=403,
            detail="仅管理员可访问此接口"
        )
    return token_data


def get_current_user(
    token_data: dict = Depends(verify_token),
    session: Session = Depends(get_db)
) -> User:
    """获取当前登录用户对象"""
    user_id = int(token_data.get('sub'))
    user = session.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="用户不存在或已被禁用"
        )
    return user


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
