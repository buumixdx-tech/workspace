from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict
from datetime import datetime

class CreateCashFlowSchema(BaseModel):
    vc_id: int = Field(..., description="关联虚拟合同ID")
    type: str = Field(..., description="款项类型")
    amount: float = Field(..., gt=0, description="金额")
    payer_id: Optional[int] = Field(None, description="付款方银行账户ID")
    payee_id: Optional[int] = Field(None, description="收款方银行账户ID")
    transaction_date: datetime = Field(..., description="交易日期")
    description: Optional[str] = Field("", description="备注")

    @model_validator(mode='after')
    def check_parties(self) -> 'CreateCashFlowSchema':
        if self.payer_id is not None and self.payee_id is not None:
            if self.payer_id == self.payee_id:
                raise ValueError("付款账户与收款账户不能相同")
        return self

class InternalTransferSchema(BaseModel):
    from_acc_id: int = Field(..., description="转出银行账户ID")
    to_acc_id: int = Field(..., description="转入银行账户ID")
    amount: float = Field(..., gt=0, description="转账金额")
    transaction_date: datetime = Field(..., description="交易日期")
    description: Optional[str] = Field("", description="备注")

    @model_validator(mode='after')
    def check_accounts(self) -> 'InternalTransferSchema':
        if self.from_acc_id == self.to_acc_id:
            raise ValueError("转出账户与转入账户不能相同")
        return self

class ExternalFundSchema(BaseModel):
    account_id: int = Field(..., description="银行账户ID")
    fund_type: str = Field(..., description="资金类型")
    amount: float = Field(..., gt=0, description="金额")
    transaction_date: datetime = Field(..., description="交易日期")
    external_entity: str = Field(..., min_length=1, description="外部实体名称")
    description: Optional[str] = Field("", description="备注")
    is_inbound: bool = Field(..., description="true=资金流入, false=资金流出")

class CreateBankAccountSchema(BaseModel):
    owner_type: str = Field(..., min_length=1, description="所有者类型")
    owner_id: Optional[int] = Field(None, description="所有者ID")
    account_info: Dict = Field(..., description="账户信息")
    is_default: bool = Field(False, description="是否为默认账户")

class UpdateBankAccountSchema(BaseModel):
    id: int = Field(..., description="银行账户ID")
    owner_type: str = Field(..., min_length=1, description="所有者类型")
    owner_id: Optional[int] = Field(None, description="所有者ID")
    account_info: Dict = Field(..., description="账户信息")
    is_default: bool = Field(False, description="是否为默认账户")
