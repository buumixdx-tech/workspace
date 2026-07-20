from pydantic import BaseModel, Field, field_validator
from typing import Optional

class DeleteMasterDataSchema(BaseModel):
    id: int = Field(..., description="要删除的记录ID")

class CustomerSchema(BaseModel):
    id: Optional[int] = Field(None, description="客户ID")
    name: str = Field(..., min_length=1, description="客户名称")
    info: Optional[str] = Field("", description="客户信息")

    @field_validator('name')
    @classmethod
    def clean_name(cls, v):
        return v.strip()

class PointSchema(BaseModel):
    id: Optional[int] = Field(None, description="点位ID")
    name: str = Field(..., min_length=1, description="点位/仓名称")
    customer_id: Optional[int] = Field(None, description="所属客户ID")
    supplier_id: Optional[int] = Field(None, description="所属供应商ID")
    type: str = Field(..., description="类型")
    address: str = Field(..., min_length=1, description="地址")
    receiving_address: str = Field(..., min_length=1, description="收货地址")

class SupplierSchema(BaseModel):
    id: Optional[int] = Field(None, description="供应商ID")
    name: str = Field(..., min_length=1, description="供应商名称")
    category: str = Field(..., description="供应类别")
    address: str = Field(..., min_length=1, description="地址")

class SKUSchema(BaseModel):
    id: Optional[int] = Field(None, description="SKU ID")
    supplier_id: int = Field(..., description="所属供应商ID")
    name: str = Field(..., min_length=1, description="SKU名称")
    type_level1: str = Field(..., description="一级类型")
    model: Optional[str] = Field("", description="型号")

class PartnerSchema(BaseModel):
    id: Optional[int] = Field(None, description="合作方ID")
    name: str = Field(..., description="合作方名称")
    type: str = Field(..., description="类型")


class PartnerRelationSchema(BaseModel):
    id: Optional[int] = Field(None, description="关联ID")
    partner_id: int = Field(..., description="合作方ID")
    owner_type: str = Field(..., description="归属主体类型 (business/supply_chain/ourselves)")
    owner_id: Optional[int] = Field(None, description="归属主体ID (ourselves时为None)")
    relation_type: str = Field(..., description="合作模式")
    remark: Optional[str] = Field(None, description="备注")


class BankAccountSchema(BaseModel):
    id: Optional[int] = Field(None, description="账号ID")
    owner_type: str = Field(..., description="所有者类型 (Customer/Supplier/Ourselves/Partner)")
    owner_id: Optional[int] = Field(None, description="所有者ID（Ourselves类型时为NULL）")
    bank_name: str = Field(..., description="开户行")
    account_no: str = Field(..., description="账号")
    is_default: bool = Field(False, description="是否为默认账号")
