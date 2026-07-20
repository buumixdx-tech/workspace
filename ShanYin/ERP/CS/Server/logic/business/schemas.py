from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict
from logic.constants import BusinessStatus

class CreateBusinessSchema(BaseModel):
    customer_id: int = Field(..., description="关联客户ID")

class UpdateBusinessStatusSchema(BaseModel):
    business_id: int = Field(..., description="业务ID")
    status: str = Field(..., description="目标状态")
    details: Optional[dict] = Field(None, description="完整详情覆盖(可选)")

class AdvanceBusinessStageSchema(BaseModel):
    business_id: int = Field(..., description="业务ID")
    next_status: str = Field(..., description="目标阶段: 前期接洽/业务评估/客户反馈/合作落地/业务开展/业务暂缓/业务终止")
    comment: Optional[str] = Field("", description="阶段推进备注")
    pricing: Optional[dict] = Field(None, description="定价配置(落地阶段)")
    payment_terms: Optional[dict] = Field(None, description="结算条款(落地→开展时必填) {prepayment_ratio, balance_period, ...}")
    contract_num: Optional[str] = Field(None, description="合同编号(可选，自动生成)")

    @field_validator('next_status')
    @classmethod
    def validate_status(cls, v):
        valid_statuses = [
            BusinessStatus.DRAFT, BusinessStatus.EVALUATION,
            BusinessStatus.FEEDBACK, BusinessStatus.LANDING,
            BusinessStatus.ACTIVE, BusinessStatus.PAUSED,
            BusinessStatus.TERMINATED
        ]
        if v not in valid_statuses:
            raise ValueError(f"非法业务阶段状态: {v}")
        return v

    @model_validator(mode='after')
    def validate_landing_requirements(self) -> 'AdvanceBusinessStageSchema':
        if self.next_status == BusinessStatus.ACTIVE:
            if not self.payment_terms:
                raise ValueError("业务正式开展前必须配置结算条款 (payment_terms)")

            p = self.payment_terms
            ratio = p.get('prepayment_ratio', 0)
            if not (0 <= ratio <= 1):
                raise ValueError("预付款比例必须在 0 到 1 之间")
        return self
