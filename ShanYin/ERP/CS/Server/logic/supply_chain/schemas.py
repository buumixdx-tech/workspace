from pydantic import BaseModel, Field
from typing import List, Optional


class SupplyChainItemSchema(BaseModel):
    """供应链定价明细项"""
    sku_id: int = Field(..., description="SKU ID")
    price: float = Field(..., description="协议单价")
    is_floating: bool = Field(default=False, description="是否浮动价格")


class CreateSupplyChainSchema(BaseModel):
    supplier_id: int = Field(..., description="供应商ID")
    supplier_name: str = Field(..., description="供应商名称")
    type: str = Field(..., description="类型: 设备/物料")
    items: List[SupplyChainItemSchema] = Field(default_factory=list, description="定价明细")
    payment_terms: dict = Field(..., description="结算条款")
    contract_num: Optional[str] = Field(None, description="合同编号")


class DeleteSupplyChainSchema(BaseModel):
    id: int = Field(..., description="协议ID")


class UpdateSupplyChainSchema(BaseModel):
    id: int = Field(..., description="协议ID")
    supplier_name: str = Field(..., description="供应商名称")
    type: str = Field(..., description="类型: 设备/物料")
    items: List[SupplyChainItemSchema] = Field(default_factory=list, description="定价明细")
    payment_terms: dict = Field(..., description="结算条款")
