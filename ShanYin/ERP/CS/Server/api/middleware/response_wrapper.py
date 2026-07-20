"""
响应包装中间件

统一API响应格式，确保所有响应都遵循标准格式：
{
    "success": true/false,
    "data": {...},  // 成功时返回数据
    "error": {...}, // 失败时返回错误信息
    "meta": {...}  // 可选的元数据（分页等）
}
"""

import json
from fastapi import Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
from typing import Any, Dict, Optional


class ResponseWrapperMiddleware(BaseHTTPMiddleware):
    """
    响应包装中间件
    
    自动将所有JSON响应包装为标准格式
    """

    # 不需要包装的路径（如健康检查、Swagger文档等）
    EXCLUDED_PATHS = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
    ]

    async def dispatch(self, request: Request, call_next):
        # 检查是否需要跳过包装
        if self._should_skip(request):
            return await call_next(request)

        # 对于流式响应，我们需要特殊处理
        response = await call_next(request)

        # 只处理JSON响应，跳过流式响应和其他类型
        if not self._is_json_response(response):
            return response

        # 包装响应
        return await self._wrap_response(response)

    def _should_skip(self, request: Request) -> bool:
        """
        检查是否应该跳过响应包装
        
        Args:
            request: FastAPI请求对象
            
        Returns:
            bool: 是否跳过包装
        """
        path = request.url.path
        return any(path.startswith(excluded) for excluded in self.EXCLUDED_PATHS)

    def _is_json_response(self, response: Response) -> bool:
        """
        检查响应是否为JSON类型
        
        Args:
            response: FastAPI响应对象
            
        Returns:
            bool: 是否为JSON响应
        """
        # 跳过流式响应
        if isinstance(response, StreamingResponse):
            return False
        
        content_type = response.headers.get("content-type", "")
        return "application/json" in content_type

    async def _wrap_response(self, response: Response) -> JSONResponse:
        """
        包装响应为标准格式
        
        Args:
            response: 原始响应对象
            
        Returns:
            JSONResponse: 包装后的响应
        """
        # 读取原始响应体
        body = b""
        
        # 处理不同类型的响应
        try:
            if isinstance(response, JSONResponse) and hasattr(response, 'body'):
                # JSONResponse 有 body 属性 (可能是字符串或字节)
                raw_body = response.body
                if isinstance(raw_body, str):
                    body = raw_body.encode("utf-8")
                elif isinstance(raw_body, bytes):
                    body = raw_body
                else:
                    body = str(raw_body).encode("utf-8")
            elif hasattr(response, 'body_iterator'):
                # 流式响应 - 需要异步读取
                async for chunk in response.body_iterator:
                    if isinstance(chunk, str):
                        body += chunk.encode("utf-8")
                    else:
                        body += chunk
            elif hasattr(response, 'content'):
                # 一些响应对象使用 content 属性
                raw_body = response.content
                if isinstance(raw_body, str):
                    body = raw_body.encode("utf-8")
                elif isinstance(raw_body, bytes):
                    body = raw_body
                else:
                    body = str(raw_body).encode("utf-8")
            else:
                # 无法读取响应体，直接返回原响应
                return response
        except Exception:
            # 读取响应体时出错，直接返回原响应
            return response

        # 解析原始JSON
        try:
            body_str = body.decode("utf-8") if isinstance(body, bytes) else body
            original_data = json.loads(body_str) if body_str else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            # 如果不是有效的JSON，直接返回原响应
            return response

        # 检查是否已经是标准格式
        if self._is_standard_format(original_data):
            return JSONResponse(
                status_code=response.status_code,
                content=original_data,
                headers=dict(response.headers)
            )

        # 包装为标准格式
        status_code = response.status_code
        if 200 <= status_code < 300:
            wrapped_response = {
                "success": True,
                "data": original_data,
                "error": None,
            }
        else:
            # 保留原始错误信息（来自 ErrorHandlerMiddleware），不做覆盖
            wrapped_response = {
                "success": False,
                "data": None,
                "error": original_data.get("error") or {
                    "code": f"HTTP_{status_code}",
                    "message": self._get_http_error_message(status_code)
                }
            }

        return JSONResponse(
            status_code=status_code,
            content=wrapped_response,
            headers={k: v for k, v in response.headers.items() if k.lower() not in ['content-length', 'content-type']}
        )

    def _is_standard_format(self, data: Dict[str, Any]) -> bool:
        """
        检查数据是否已经是标准格式
        
        Args:
            data: 响应数据
            
        Returns:
            bool: 是否为标准格式
        """
        if not isinstance(data, dict):
            return False
        return "success" in data and ("data" in data or "error" in data)

    def _get_http_error_message(self, status_code: int) -> str:
        """
        获取HTTP状态码对应的错误信息
        
        Args:
            status_code: HTTP状态码
            
        Returns:
            str: 错误信息
        """
        messages = {
            400: "请求参数错误",
            401: "未授权访问",
            403: "禁止访问",
            404: "资源未找到",
            405: "请求方法不允许",
            408: "请求超时",
            409: "资源冲突",
            422: "请求格式错误",
            429: "请求过于频繁",
            500: "服务器内部错误",
            502: "网关错误",
            503: "服务不可用",
            504: "网关超时",
        }
        return messages.get(status_code, f"HTTP错误: {status_code}")


# 便捷函数：用于创建标准格式的成功响应
def create_success_response(data: Any, meta: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    创建标准格式的成功响应
    
    Args:
        data: 响应数据
        meta: 元数据（如分页信息）
        
    Returns:
        Dict[str, Any]: 标准格式的成功响应
    """
    response = {
        "success": True,
        "data": data,
        "error": None
    }
    if meta:
        response["meta"] = meta
    return response


def create_error_response(code: str, message: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    创建标准格式的错误响应
    
    Args:
        code: 错误代码
        message: 错误信息
        details: 额外的错误详情
        
    Returns:
        Dict[str, Any]: 标准格式的错误响应
    """
    response = {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message
        }
    }
    if details:
        response["error"]["details"] = details
    return response
