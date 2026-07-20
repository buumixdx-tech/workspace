"""
统一错误处理中间件

捕获所有未处理的异常，返回标准化的错误响应格式
"""

import traceback
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional

# 配置日志
logger = logging.getLogger(__name__)


class BusinessError(Exception):
    """
    业务异常基类
    
    用于区分业务逻辑错误和系统错误
    """
    def __init__(self, message: str, code: Optional[str] = None, status_code: int = 400):
        self.message = message
        self.code = code or "BUSINESS_ERROR"
        self.status_code = status_code
        super().__init__(message)


class ValidationError(BusinessError):
    """数据验证错误"""
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message, code or "VALIDATION_ERROR", 422)


class NotFoundError(BusinessError):
    """资源未找到错误"""
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message, code or "NOT_FOUND", 404)


class ConflictError(BusinessError):
    """资源冲突错误"""
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message, code or "CONFLICT", 409)


class PermissionError(BusinessError):
    """权限不足错误"""
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message, code or "PERMISSION_DENIED", 403)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    统一错误处理中间件
    
    捕获所有异常并返回标准化的错误响应
    
    错误响应格式：
    {
        "success": false,
        "error": {
            "code": "ERROR_CODE",
            "message": "用户友好的错误信息",
            "details": {}  // 可选的额外信息
        }
    }
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
            
        except BusinessError as exc:
            # 业务异常 - 返回用户友好的错误信息
            logger.warning(f"业务异常: {exc.code} - {exc.message}", exc_info=True)
            return self._create_error_response(
                code=exc.code,
                message=exc.message,
                status_code=exc.status_code
            )
            
        except Exception as exc:
            # 系统异常 - 记录详细日志但返回通用错误信息
            error_id = self._generate_error_id()
            logger.error(
                f"系统异常 [ID: {error_id}]: {str(exc)}\n"
                f"Traceback:\n{traceback.format_exc()}",
                exc_info=True
            )
            
            # 生产环境不暴露详细错误信息
            return self._create_error_response(
                code="INTERNAL_ERROR",
                message=f"系统内部错误，请联系管理员。错误ID: {error_id}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                details={"error_id": error_id} if self._is_debug_mode() else None
            )

    def _create_error_response(
        self, 
        code: str, 
        message: str, 
        status_code: int = 400,
        details: dict = None
    ) -> JSONResponse:
        """
        创建标准化的错误响应
        
        Args:
            code: 错误代码
            message: 错误信息
            status_code: HTTP状态码
            details: 额外的错误详情（可选）
            
        Returns:
            JSONResponse: 标准化的错误响应
        """
        content = {
            "success": False,
            "error": {
                "code": code,
                "message": message
            }
        }
        
        if details:
            content["error"]["details"] = details
            
        return JSONResponse(
            status_code=status_code,
            content=content
        )

    def _generate_error_id(self) -> str:
        """
        生成唯一的错误ID
        
        Returns:
            str: 格式为 ERR-{timestamp}-{random} 的错误ID
        """
        import uuid
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = str(uuid.uuid4())[:8]
        return f"ERR-{timestamp}-{random_part}"

    def _is_debug_mode(self) -> bool:
        """
        检查是否处于调试模式
        
        Returns:
            bool: 调试模式返回True，生产模式返回False
        """
        import os
        return os.environ.get("DEBUG", "false").lower() == "true"


# 便捷函数：用于在业务代码中抛出业务异常
def raise_business_error(message: str, code: str = "BUSINESS_ERROR", status_code: int = 400):
    """
    抛出业务异常
    
    Args:
        message: 错误信息
        code: 错误代码
        status_code: HTTP状态码
        
    Raises:
        BusinessError: 业务异常
    """
    raise BusinessError(message, code, status_code)


def raise_validation_error(message: str, code: str = "VALIDATION_ERROR"):
    """
    抛出验证错误
    
    Args:
        message: 错误信息
        code: 错误代码
        
    Raises:
        ValidationError: 验证错误
    """
    raise ValidationError(message, code)


def raise_not_found_error(resource: str, resource_id: str = None):
    """
    抛出资源未找到错误
    
    Args:
        resource: 资源类型名称
        resource_id: 资源ID（可选）
        
    Raises:
        NotFoundError: 资源未找到错误
    """
    message = f"未找到{resource}"
    if resource_id:
        message = f"未找到{resource} (ID: {resource_id})"
    raise NotFoundError(message, "NOT_FOUND")


def raise_conflict_error(message: str, code: str = "CONFLICT"):
    """
    抛出资源冲突错误
    
    Args:
        message: 错误信息
        code: 错误代码
        
    Raises:
        ConflictError: 资源冲突错误
    """
    raise ConflictError(message, code)


def raise_permission_error(message: str = "权限不足"):
    """
    抛出权限错误
    
    Args:
        message: 错误信息
        
    Raises:
        PermissionError: 权限错误
    """
    raise PermissionError(message, "PERMISSION_DENIED")