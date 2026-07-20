from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TimeRuleSchema(BaseModel):
    id: Optional[int] = Field(None, description="规则ID")
    related_id: int = Field(..., description="关联对象ID")
    related_type: str = Field(..., description="关联类型")
    party: str = Field(..., description="责任方")
    trigger_event: str = Field(..., description="触发事件")
    tge_param1: Optional[str] = Field(None, description="触发事件参数1")
    tge_param2: Optional[str] = Field(None, description="触发事件参数2")
    target_event: str = Field(..., description="目标事件")
    tae_param1: Optional[str] = Field(None, description="目标事件参数1")
    tae_param2: Optional[str] = Field(None, description="目标事件参数2")
    offset: int = Field(..., ge=0, description="偏移量")
    unit: str = Field(..., description="单位")
    direction: str = Field(..., description="方向")
    inherit: int = Field(..., description="继承级别")
    status: str = Field(..., description="状态")
    trigger_time: Optional[datetime] = Field(None, description="触发时间")
    target_time: Optional[datetime] = Field(None, description="目标时间")
    flag_time: Optional[datetime] = Field(None, description="标杆时间")
    warning: Optional[str] = Field(None, description="告警等级")
    result: Optional[str] = Field(None, description="合规结果")
