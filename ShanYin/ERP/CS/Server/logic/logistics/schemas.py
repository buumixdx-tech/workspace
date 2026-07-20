from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import date


class AddressInfoSchema(BaseModel):
    发货点位Id: int
    发货点位名称: str
    发货地址: str
    发货联系电话: Optional[str] = ""
    收货点位Id: int
    收货点位名称: str
    收货地址: str
    收货联系电话: Optional[str] = ""


class OrderItemSchema(BaseModel):
    sku_id: int
    sku_name: Optional[str] = None
    qty: float


class CreateLogisticsPlanSchema(BaseModel):
    vc_id: int = Field(..., description="关联虚拟合同ID")
    orders: List[Dict] = Field(..., description="快递单列表")
    created_date: Optional[date] = Field(None, description="业务发生日期，不填则按当前日期")

    model_config = {"extra": "allow"}


class BatchItemSchema(BaseModel):
    """物料采购入库批次明细（人工输入）"""
    sku_id: int = Field(..., description="SKU ID")
    production_date: str = Field(..., description="生产日期 YYYYMMDD")
    expiration_date: Optional[str] = Field(None, description="有效期 YYYYMMDD（可选）")
    receiving_point_id: int = Field(..., description="收货点位ID")
    qty: float = Field(..., description="入库数量")
    certificate_filename: Optional[str] = Field(None, description="质检报告文件名（客户端传）")


class ConfirmInboundSchema(BaseModel):
    log_id: int = Field(..., description="物流记录ID")
    sn_list: List[str] = Field([], description="设备序列号列表(物料类可为空)")
    batch_items: Optional[List[BatchItemSchema]] = Field(
        None,
        description="物料采购入库批次明细（MATERIAL_PROCUREMENT 类型必填）"
    )
    created_date: Optional[date] = Field(None, description="业务发生日期，不填则按当前日期")


class UpdateExpressOrderSchema(BaseModel):
    order_id: int = Field(..., description="快递单ID")
    tracking_number: str = Field(..., description="快递单号")
    address_info: dict = Field(..., description="地址信息")


class ExpressOrderStatusSchema(BaseModel):
    order_id: int = Field(..., description="快递单ID")
    target_status: str = Field(..., description="目标状态: 待发货/在途/签收")
    logistics_id: int = Field(..., description="物流记录ID(状态机需要)")
    created_date: Optional[date] = Field(None, description="业务发生日期，不填则按当前日期")
