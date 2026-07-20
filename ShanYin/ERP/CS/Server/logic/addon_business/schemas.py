from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime


class CreateAddonSchema(BaseModel):
    """创建附加业务的请求 Schema（原子化版本）"""
    business_id: int = Field(..., description="关联的业务ID")
    addon_type: str = Field(..., description="类型: PRICE_ADJUST / NEW_SKU")
    sku_id: Optional[int] = Field(None, description="SKU ID（PRICE_ADJUST / NEW_SKU 必填）")
    override_price: Optional[float] = Field(None, description="覆盖单价")
    override_deposit: Optional[float] = Field(None, description="覆盖押金")
    start_date: datetime = Field(..., description="有效期开始时间")
    end_date: Optional[datetime] = Field(None, description="有效期结束时间（NULL=永久有效）")
    remark: Optional[str] = Field(None, description="备注")

    @model_validator(mode='after')
    def validate(self) -> 'CreateAddonSchema':
        # addon_type 有效性
        if self.addon_type not in ["PRICE_ADJUST", "NEW_SKU"]:
            raise ValueError(f"无效的 addon_type：{self.addon_type}，目前仅支持 PRICE_ADJUST / NEW_SKU")

        # 日期校验
        if self.end_date is not None and self.start_date >= self.end_date:
            raise ValueError("开始日期必须早于结束日期")

        # SKU 必填校验
        if self.addon_type in ["PRICE_ADJUST", "NEW_SKU"]:
            if not self.sku_id:
                raise ValueError(f"{self.addon_type} 必须指定 sku_id")

        # PRICE_ADJUST 至少有一个覆盖值
        if self.addon_type == "PRICE_ADJUST":
            if self.override_price is None and self.override_deposit is None:
                raise ValueError("PRICE_ADJUST 必须提供 override_price 或 override_deposit")

        return self


class UpdateAddonSchema(BaseModel):
    """更新附加业务的请求 Schema（原子化版本）"""
    addon_id: int = Field(..., description="附加业务ID")
    start_date: Optional[datetime] = Field(None, description="有效期开始时间")
    end_date: Optional[datetime] = Field(None, description="有效期结束时间")
    override_price: Optional[float] = Field(None, description="覆盖单价")
    override_deposit: Optional[float] = Field(None, description="覆盖押金")
    status: Optional[str] = Field(None, description="状态: 生效 / 失效")
    remark: Optional[str] = Field(None, description="备注")


class AddonDetailSchema(BaseModel):
    """附加业务详情返回 Schema"""
    id: int
    business_id: int
    addon_type: str
    status: str
    sku_id: Optional[int]
    override_price: Optional[float]
    override_deposit: Optional[float]
    start_date: datetime
    end_date: Optional[datetime]
    remark: Optional[str]

    class Config:
        from_attributes = True
