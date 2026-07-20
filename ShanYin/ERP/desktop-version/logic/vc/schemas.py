from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import List, Optional, Dict
from datetime import datetime
from logic.time_rules.schemas import TimeRuleSchema


class VCElementSchema(BaseModel):
    """统一 VC elements 条目结构：按(shipping_point_id, receiving_point_id, sku_id, batch_no)唯一确定"""
    model_config = ConfigDict(extra='allow')
    shipping_point_id: int = Field(..., description="发货点位ID")
    receiving_point_id: int = Field(..., description="收货点位ID")
    sku_id: int = Field(..., description="SKU ID")
    batch_no: Optional[str] = Field(None, description="物料批次号（物料供应必填）")
    qty: float = Field(..., gt=0, description="数量")
    price: float = Field(..., ge=0, description="单价")
    deposit: float = Field(default=0.0, ge=0, description="单台押金（设备VC有值，物料VC为0）")
    subtotal: float = Field(..., description="小计金额 = qty × price")
    sn_list: List[str] = Field(default_factory=list, description="设备序列号列表（退货/调拨时填写）")
    addon_business_ids: List[int] = Field(default_factory=list, description="应用的附加业务ID列表（系统自动填充）")

    @field_validator('subtotal', mode='before')
    @classmethod
    def compute_subtotal(cls, v, info):
        # 自动计算小计
        if v is not None:
            return v
        return 0.0

    @model_validator(mode='after')
    def validate_subtotal(self) -> 'VCElementSchema':
        expected = self.qty * self.price
        if self.subtotal < expected - 0.01:
            raise ValueError(f"小计 {self.subtotal} 不能小于 qty×price ({expected})")
        return self

    @property
    def id(self) -> str:
        """自动生成唯一标识：sp{shipping_point_id}_rp{receiving_point_id}_sku{sku_id}_bn{batch_no}"""
        return f"sp{self.shipping_point_id}_rp{self.receiving_point_id}_sku{self.sku_id}_bn{self.batch_no or '-'}"


class CreateProcurementVCSchema(BaseModel):
    """设备采购 Schema

    elements JSON 结构：
    {
        "elements": [{VCElementSchema}],   # 采购明细列表
        "total_amount": float,             # 总金额
        "payment_terms": dict             # 结算条款（prepayment_ratio, balance_period, day_rule, start_trigger）
    }
    """
    business_id: int = Field(..., description="关联业务ID")
    sc_id: Optional[int] = Field(None, description="供应链协议ID")
    elements: List[VCElementSchema] = Field(..., description="采购明细列表")
    total_amt: float = Field(..., ge=0, description="总金额")
    total_deposit: float = Field(..., ge=0, description="总押金")
    payment: Dict = Field(..., description="结算条款")
    description: Optional[str] = Field("", description="备注")

    @model_validator(mode='after')
    def validate_totals(self) -> 'CreateProcurementVCSchema':
        calc_amt = sum(elem.qty * elem.price for elem in self.elements)
        calc_dep = sum(elem.qty * elem.deposit for elem in self.elements)
        if abs(calc_amt - self.total_amt) > 0.01:
            raise ValueError(f"总计金额 ¥{self.total_amt} 与明细计算值 ¥{calc_amt:.2f} 不符")
        if abs(calc_dep - self.total_deposit) > 0.01:
            raise ValueError(f"总计押金 ¥{self.total_deposit} 与明细计算值 ¥{calc_dep:.2f} 不符")
        return self


class CreateStockProcurementVCSchema(BaseModel):
    """库存采购 Schema（向供应商采购设备，不涉及客户押金）

    elements JSON 结构：
    {
        "elements": [{VCElementSchema}],   # 采购明细列表
        "total_amount": float,             # 总金额
        "payment_terms": dict             # 结算条款
    }
    """
    sc_id: int = Field(..., description="供应链协议ID")
    elements: List[VCElementSchema] = Field(..., description="采购明细")
    total_amt: float = Field(..., ge=0, description="总金额")
    payment: Dict = Field(..., description="结算条款")
    description: Optional[str] = Field("", description="备注")


class CreateMatProcurementVCSchema(BaseModel):
    """物料采购 Schema

    elements JSON 结构：
    {
        "elements": [{VCElementSchema}],   # 采购明细列表
        "total_amount": float,             # 总金额
        "payment_terms": dict             # 结算条款
    }
    """
    sc_id: int = Field(..., description="供应链协议ID")
    elements: List[VCElementSchema] = Field(..., description="物料采购明细")
    total_amt: float = Field(..., gt=0, description="总金额")
    payment: Dict = Field(..., description="结算条款")
    description: Optional[str] = Field("", description="备注")


class CreateMaterialSupplyVCSchema(BaseModel):
    """物料供应 Schema

    elements JSON 结构：
    {
        "elements": [{VCElementSchema}],   # 供应明细列表
        "total_amount": float,             # 总金额
        "payment_terms": dict             # 结算条款
    }
    """
    business_id: int = Field(..., description="关联业务ID")
    elements: List[VCElementSchema] = Field(..., description="供应明细列表")
    total_amt: float = Field(..., ge=0, description="总金额")
    description: Optional[str] = Field("", description="备注")


class CreateReturnVCSchema(BaseModel):
    """退货 Schema（可针对设备采购 VC 或库存拨付 VC 退货，押金通过 CashFlow 系统处理）

    elements JSON 结构：
    {
        "elements": [{VCElementSchema}],   # 退货明细列表
        "goods_amount": float,             # 退货货款金额
        "deposit_amount": float,           # 退还押金金额
        "total_refund": float,             # 总退款金额（= goods_amount + deposit_amount）
        "reason": str                      # 退货原因
    }
    """
    target_vc_id: int = Field(..., description="退货目标虚拟合同ID")
    return_direction: str = Field(..., description="退货方向")
    elements: List[VCElementSchema] = Field(..., description="退货明细")
    goods_amount: float = Field(..., ge=0, description="退货货款金额")
    deposit_amount: float = Field(..., ge=0, description="退还押金金额")
    logistics_cost: float = Field(..., ge=0, description="物流费用")
    logistics_bearer: str = Field(..., description="物流费承担方")
    total_refund: float = Field(..., ge=0, description="总退款金额")
    reason: Optional[str] = Field("", description="退货原因")
    description: Optional[str] = Field("", description="备注")

    @model_validator(mode='after')
    def validate_return_elements(self) -> 'CreateReturnVCSchema':
        for elem in self.elements:
            # 物料退货必须指定 batch_no；设备退货通过 sn/sn_list 标识，不要求 batch_no
            has_sn = bool(elem.sn_list) or (elem.sn and elem.sn != "-")
            if elem.batch_no is None and not has_sn:
                raise ValueError("物料退货必须指定 batch_no")
        return self


class AllocateInventorySchema(BaseModel):
    """库存拨付 Schema（自有库存设备拨付给客户，可能涉及押金）

    elements JSON 结构：
    {
        "elements": [{VCElementSchema}],   # 拨付明细列表
        "total_amount": float              # 总金额（通常为 0）
    }
    """
    business_id: int = Field(..., description="目标业务ID")
    elements: List[VCElementSchema] = Field(..., description="拨付明细")
    description: Optional[str] = Field("", description="备注")


class UpdateVCSchema(BaseModel):
    id: int = Field(..., description="VC ID")
    description: Optional[str] = Field(None, description="备注")
    elements: Optional[Dict] = Field(None, description="核心数据负载")
    deposit_info: Optional[Dict] = Field(None, description="押金信息")


class DeleteVCSchema(BaseModel):
    id: int = Field(..., description="VC ID")


# 向后兼容：保留 VCItemSchema 供 operations.py 过渡期使用
class VCItemSchema(BaseModel):
    """向后兼容：旧版 items 结构，逐步废弃"""
    sku_id: int = Field(..., description="SKU ID")
    sku_name: str = Field(..., min_length=1, description="SKU名称")
    receiving_point_id: Optional[int] = Field(None, description="收货点位ID")
    receiving_point_name: Optional[str] = Field(None, description="收货点位名称")
    qty: float = Field(..., gt=0, description="数量")
    price: float = Field(..., ge=0, description="单价")
    deposit: float = Field(default=0.0, ge=0, description="单台押金")
    sn: str = Field("-", description="设备序列号(物料填'-')")
    shipping_point_name: Optional[str] = Field(None, description="发货点位")
    receiving_point_name: Optional[str] = Field(None, description="收货点位")
    target_point_id: Optional[int] = Field(None, description="目标点位ID")
    target_point_name: Optional[str] = Field(None, description="目标点位名称")
    shipping_point_id: Optional[int] = Field(None, description="发货点位ID")

    @field_validator('sku_name', 'receiving_point_name', 'shipping_point_name', 'sn')
    @classmethod
    def clean_strings(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v
