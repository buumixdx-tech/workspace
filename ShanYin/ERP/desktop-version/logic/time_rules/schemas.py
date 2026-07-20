from pydantic import BaseModel, Field
from typing import Optional

class TimeRuleSchema(BaseModel):
    id: Optional[int] = Field(None, description="规则ID")
    related_id: int = Field(..., description="关联对象ID")
    related_type: str = Field(..., description="关联类型")
    party: str = Field(..., description="责任方")
    trigger_event: str = Field(..., description="触发事件")
    target_event: str = Field(..., description="目标事件")
    offset: int = Field(..., ge=0, description="偏移量")
    unit: str = Field(..., description="单位")
    direction: str = Field(..., description="方向")
    inherit: int = Field(..., description="继承级别")
    status: str = Field(..., description="状态")
