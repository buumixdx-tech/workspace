from pydantic import BaseModel
from typing import Any, Optional

class ActionResult(BaseModel):
    """标准执行结果返回模型"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None
