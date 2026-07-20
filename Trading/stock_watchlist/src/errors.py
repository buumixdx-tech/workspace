"""自定义 API 异常。

背景:routes.py 的 @_safe 装饰器之前把任何 Exception 都转成 500,
验证错误 / 资源不存在都返 500,客户端无法用 HTTP 码区分。

用法(迁移路线):
  旧: return jsonify({"ok": False, "error": "stock_code 必填"}), 400
  新: raise BadRequest("stock_code 必填")
"""
from __future__ import annotations


class ApiError(Exception):
    """基类 — 装饰器捕获时返对应 status + error JSON."""
    status: int = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class BadRequest(ApiError):
    """客户端请求错误 — 400."""
    status = 400


class NotFound(ApiError):
    """资源不存在 — 404."""
    status = 404


class Conflict(ApiError):
    """资源冲突(唯一键冲突等) — 409."""
    status = 409


class Unauthorized(ApiError):
    """未认证 — 401(预留,当前无认证)。"""
    status = 401


class Forbidden(ApiError):
    """权限不足 — 403(预留)。"""
    status = 403