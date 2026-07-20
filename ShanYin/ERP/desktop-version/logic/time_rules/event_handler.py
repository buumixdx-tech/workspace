"""
事件处理模块

职责：
1. 查询指定事件是否已发生
2. 返回事件发生的时间戳
3. 支持参数化事件查询
"""

from datetime import datetime
from typing import Optional

from models import (
    get_session, VirtualContract, VirtualContractStatusLog, 
    Logistics, ExpressOrder, CashFlow, Contract, Business, SupplyChain
)
from logic.constants import (
    EventType, TimeRuleRelatedType, SubjectStatus, CashStatus, 
    VCStatus, LogisticsStatus, CashFlowType, VCType
)


class EventHandler:
    """
    事件处理模块
    
    通过统一接口查询任意事件的发生时间。
    入参：事件类型、关联对象类型、关联对象ID、可选参数
    返回：事件发生时间 (datetime) 或 None (未发生)
    """
    
    def __init__(self, session=None):
        self.session = session or get_session()
    
    def get_event_time(self, event_type: str, related_type: str, related_id: int,
                       param1: str = None, param2: str = None) -> Optional[datetime]:
        """
        获取事件发生时间
        
        Args:
            event_type: 事件类型 (如 "发货", "款项结清")
            related_type: 关联对象类型 (业务/供应链/虚拟合同/物流)
            related_id: 关联对象 ID
            param1, param2: 可选参数 (如付款比例)
        
        Returns:
            datetime: 事件发生时间，未发生返回 None
        """
        # 特殊事件：绝对日期模式下不需要查询
        if event_type == EventType.Special.ABSOLUTE_DATE:
            return None
        
        # 根据事件类型分发到对应处理器
        handler_map = {
            # === 合同级事件 ===
            EventType.ContractLevel.CONTRACT_SIGNED: self._check_contract_signed,
            EventType.ContractLevel.CONTRACT_EFFECTIVE: self._check_contract_effective,
            EventType.ContractLevel.CONTRACT_EXPIRY: self._check_contract_expiry,
            EventType.ContractLevel.CONTRACT_RENEWED: self._check_contract_renewed,
            EventType.ContractLevel.CONTRACT_TERMINATED: self._check_contract_terminated,
            
            # === 虚拟合同级事件 ===
            EventType.VCLevel.VC_CREATED: self._check_vc_created,
            EventType.VCLevel.VC_STATUS_EXE: self._check_vc_status_exe,
            EventType.VCLevel.VC_STATUS_FINISH: self._check_vc_status_finish,
            EventType.VCLevel.SUBJECT_SHIPPED: self._check_subject_shipped,
            EventType.VCLevel.SUBJECT_SIGNED: self._check_subject_signed,
            EventType.VCLevel.SUBJECT_FINISH: self._check_subject_finish,
            EventType.VCLevel.CASH_PREPAID: self._check_cash_prepaid,
            EventType.VCLevel.CASH_FINISH: self._check_cash_finish,
            EventType.VCLevel.SUBJECT_CASH_FINISH: self._check_subject_cash_finish,
            EventType.VCLevel.DEPOSIT_RECEIVED: self._check_deposit_received,
            EventType.VCLevel.DEPOSIT_RETURNED: self._check_deposit_returned,
            EventType.VCLevel.PAYMENT_RATIO_REACHED: self._check_payment_ratio,
            
            # === 物流级事件 ===
            EventType.LogisticsLevel.LOGISTICS_CREATED: self._check_logistics_created,
            EventType.LogisticsLevel.LOGISTICS_PENDING: self._check_logistics_pending,
            EventType.LogisticsLevel.LOGISTICS_SHIPPED: self._check_logistics_shipped,
            EventType.LogisticsLevel.LOGISTICS_SIGNED: self._check_logistics_signed,
            EventType.LogisticsLevel.LOGISTICS_FINISH: self._check_logistics_finish,
            EventType.LogisticsLevel.EXPRESS_CREATED: self._check_express_created,
            EventType.LogisticsLevel.EXPRESS_SHIPPED: self._check_express_shipped,
            EventType.LogisticsLevel.EXPRESS_SIGNED: self._check_express_signed,
        }
        
        handler = handler_map.get(event_type)
        if handler:
            return handler(related_type, related_id, param1, param2)
        return None
    
    # =========================================================================
    # 辅助方法：关联ID解析
    # =========================================================================
    
    def _resolve_to_vc_id(self, related_type: str, related_id: int) -> Optional[int]:
        """将不同关联类型解析到虚拟合同 ID"""
        if related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT:
            return related_id
        elif related_type == TimeRuleRelatedType.LOGISTICS:
            logistics = self.session.query(Logistics).get(related_id)
            return logistics.virtual_contract_id if logistics else None
        # Business / SupplyChain 级别：返回 None，需要单独处理
        return None
    
    def _resolve_to_logistics_id(self, related_type: str, related_id: int) -> Optional[int]:
        """将不同关联类型解析到物流 ID"""
        if related_type == TimeRuleRelatedType.LOGISTICS:
            return related_id
        return None
    
    def _get_contract_for_business_or_sc(self, related_type: str, related_id: int) -> Optional[Contract]:
        """获取业务或供应链关联的合同"""
        if related_type == TimeRuleRelatedType.BUSINESS:
            biz = self.session.query(Business).get(related_id)
            if biz and biz.details:
                contracts = biz.details.get("contracts", [])
                for c in contracts:
                    if c.get("is_primary"):
                        return self.session.query(Contract).get(c["id"])
        elif related_type == TimeRuleRelatedType.SUPPLY_CHAIN:
            sc = self.session.query(SupplyChain).get(related_id)
            if sc and sc.contract_id:
                return self.session.query(Contract).get(sc.contract_id)
        return None
    
    # =========================================================================
    # 合同级事件处理器
    # =========================================================================
    
    def _check_contract_signed(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查合同签订时间"""
        contract = self._get_contract_for_business_or_sc(related_type, related_id)
        return contract.signed_date if contract else None
    
    def _check_contract_effective(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查合同生效时间"""
        contract = self._get_contract_for_business_or_sc(related_type, related_id)
        return contract.effective_date if contract else None
    
    def _check_contract_expiry(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查合同到期时间"""
        contract = self._get_contract_for_business_or_sc(related_type, related_id)
        return contract.expiry_date if contract else None
    
    def _check_contract_renewed(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查合同更新时间 (暂返回 None，需要额外字段支持)"""
        # TODO: 合同更新需要额外的记录机制
        return None
    
    def _check_contract_terminated(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查合同终止时间 (暂返回 None，需要额外字段支持)"""
        # TODO: 合同终止需要额外的记录机制
        return None
    
    # =========================================================================
    # 虚拟合同级事件处理器
    # =========================================================================
    
    def _check_vc_created(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查虚拟合同创建时间"""
        vc_id = self._resolve_to_vc_id(related_type, related_id)
        if not vc_id:
            return None
        vc = self.session.query(VirtualContract).get(vc_id)
        return vc.status_timestamp if vc else None
    
    def _check_vc_status_exe(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查虚拟合同进入执行状态时间"""
        vc_id = self._resolve_to_vc_id(related_type, related_id)
        if not vc_id:
            return None
        log = self.session.query(VirtualContractStatusLog).filter(
            VirtualContractStatusLog.vc_id == vc_id,
            VirtualContractStatusLog.category == 'status',
            VirtualContractStatusLog.status_name == VCStatus.EXE
        ).order_by(VirtualContractStatusLog.timestamp.asc()).first()
        return log.timestamp if log else None
    
    def _check_vc_status_finish(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查虚拟合同完成时间"""
        vc_id = self._resolve_to_vc_id(related_type, related_id)
        if not vc_id:
            return None
        log = self.session.query(VirtualContractStatusLog).filter(
            VirtualContractStatusLog.vc_id == vc_id,
            VirtualContractStatusLog.category == 'status',
            VirtualContractStatusLog.status_name == VCStatus.FINISH
        ).order_by(VirtualContractStatusLog.timestamp.asc()).first()
        return log.timestamp if log else None
    
    def _check_subject_logistics_ready(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查物流安排完成时间 (已跟随 SubjectStatus 废弃)"""
        return None
    
    def _check_subject_shipped(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查发货时间"""
        vc_id = self._resolve_to_vc_id(related_type, related_id)
        if not vc_id:
            return None
        log = self.session.query(VirtualContractStatusLog).filter(
            VirtualContractStatusLog.vc_id == vc_id,
            VirtualContractStatusLog.category == 'subject',
            VirtualContractStatusLog.status_name == SubjectStatus.SHIPPED
        ).order_by(VirtualContractStatusLog.timestamp.asc()).first()
        return log.timestamp if log else None
    
    def _check_subject_signed(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查签收时间"""
        vc_id = self._resolve_to_vc_id(related_type, related_id)
        if not vc_id:
            return None
        log = self.session.query(VirtualContractStatusLog).filter(
            VirtualContractStatusLog.vc_id == vc_id,
            VirtualContractStatusLog.category == 'subject',
            VirtualContractStatusLog.status_name == SubjectStatus.SIGNED
        ).order_by(VirtualContractStatusLog.timestamp.asc()).first()
        return log.timestamp if log else None
    
    def _check_subject_finish(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查标的完成时间"""
        vc_id = self._resolve_to_vc_id(related_type, related_id)
        if not vc_id:
            return None
        log = self.session.query(VirtualContractStatusLog).filter(
            VirtualContractStatusLog.vc_id == vc_id,
            VirtualContractStatusLog.category == 'subject',
            VirtualContractStatusLog.status_name == SubjectStatus.FINISH
        ).order_by(VirtualContractStatusLog.timestamp.asc()).first()
        return log.timestamp if log else None
    
    def _check_cash_prepaid(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查预付完成时间"""
        vc_id = self._resolve_to_vc_id(related_type, related_id)
        if not vc_id:
            return None
        log = self.session.query(VirtualContractStatusLog).filter(
            VirtualContractStatusLog.vc_id == vc_id,
            VirtualContractStatusLog.category == 'cash',
            VirtualContractStatusLog.status_name == CashStatus.PREPAID
        ).order_by(VirtualContractStatusLog.timestamp.asc()).first()
        return log.timestamp if log else None
    
    def _check_cash_finish(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查款项结清时间"""
        vc_id = self._resolve_to_vc_id(related_type, related_id)
        if not vc_id:
            return None
        log = self.session.query(VirtualContractStatusLog).filter(
            VirtualContractStatusLog.vc_id == vc_id,
            VirtualContractStatusLog.category == 'cash',
            VirtualContractStatusLog.status_name == CashStatus.FINISH
        ).order_by(VirtualContractStatusLog.timestamp.asc()).first()
        return log.timestamp if log else None
    
    def _check_subject_cash_finish(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查货款结清时间 (仅统计预付和履约款达到 100%)"""
        return self._check_payment_ratio(related_type, related_id, "1.0", p2)
    
    def _check_deposit_received(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查押金收齐时间"""
        vc_id = self._resolve_to_vc_id(related_type, related_id)
        if not vc_id:
            return None
        vc = self.session.query(VirtualContract).get(vc_id)
        if not vc or not vc.deposit_info:
            return None
        
        should_receive = vc.deposit_info.get('should_receive', 0)
        if should_receive <= 0:
            return None
        
        # 查询押金资金流，累加到达标的时间点
        cashflows = self.session.query(CashFlow).filter(
            CashFlow.virtual_contract_id == vc_id,
            CashFlow.type == CashFlowType.DEPOSIT
        ).order_by(CashFlow.transaction_date.asc()).all()
        
        cumulative = 0
        for cf in cashflows:
            cumulative += cf.amount
            if cumulative >= should_receive - 0.01:
                return cf.transaction_date
        return None
    
    def _check_deposit_returned(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查押金退还时间 (最后一笔退还押金的时间)"""
        vc_id = self._resolve_to_vc_id(related_type, related_id)
        if not vc_id:
            return None
        
        last_return = self.session.query(CashFlow).filter(
            CashFlow.virtual_contract_id == vc_id,
            CashFlow.type == CashFlowType.RETURN_DEPOSIT
        ).order_by(CashFlow.transaction_date.desc()).first()
        
        return last_return.transaction_date if last_return else None
    
    def _check_payment_ratio(self, related_type, related_id, ratio_param, p2) -> Optional[datetime]:
        """检查付款比例是否达到指定值"""
        vc_id = self._resolve_to_vc_id(related_type, related_id)
        if not vc_id:
            return None
        
        target_ratio = float(ratio_param) if ratio_param else 0.5
        vc = self.session.query(VirtualContract).get(vc_id)
        total_due = vc.elements.get('total_amount', 0) if vc and vc.elements else 0
        
        if total_due <= 0:
            return None
        
        # 查询所有资金流，按时间排序，找到首次达到比例的时间点
        cashflows = self.session.query(CashFlow).filter(
            CashFlow.virtual_contract_id == vc_id,
            CashFlow.type.in_([
                CashFlowType.PREPAYMENT, 
                CashFlowType.FULFILLMENT,
                CashFlowType.REFUND,
                CashFlowType.OFFSET_PAY
            ])
        ).order_by(CashFlow.transaction_date.asc()).all()
        
        cumulative = 0
        for cf in cashflows:
            # 确定金额对进度的贡献方向
            if vc.type == VCType.RETURN:
                # 退货合同：退款是正向进度
                val = cf.amount if cf.type == CashFlowType.REFUND else 0
            else:
                # 正常合同：预付/履约/冲抵是正向，退款是负向扣减
                val = -cf.amount if cf.type == CashFlowType.REFUND else cf.amount
            
            cumulative += val
            if total_due > 0 and cumulative / total_due >= target_ratio:
                return cf.transaction_date
        return None
    
    # =========================================================================
    # 物流级事件处理器
    # =========================================================================
    
    def _check_logistics_created(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查物流创建时间"""
        logistics_id = self._resolve_to_logistics_id(related_type, related_id)
        if not logistics_id:
            return None
        logistics = self.session.query(Logistics).get(logistics_id)
        return logistics.timestamp if logistics else None
    
    def _check_logistics_pending(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查物流待发货时间 (即创建时间)"""
        return self._check_logistics_created(related_type, related_id, p1, p2)
    
    def _check_logistics_shipped(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查物流已发货时间 (所有快递都已发出)"""
        logistics_id = self._resolve_to_logistics_id(related_type, related_id)
        if not logistics_id:
            return None
        
        all_express = self.session.query(ExpressOrder).filter(
            ExpressOrder.logistics_id == logistics_id
        ).all()
        
        if not all_express:
            return None
        
        # 严格逻辑：所有快递必须都不在“待发货”状态
        if all(e.status in [LogisticsStatus.TRANSIT, LogisticsStatus.SIGNED] for e in all_express):
            # 返回最后一个变为发货的时间
            return max(e.timestamp for e in all_express)
        return None
    
    def _check_logistics_signed(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查物流已签收时间 (所有快递都签收)"""
        logistics_id = self._resolve_to_logistics_id(related_type, related_id)
        if not logistics_id:
            return None
        
        all_express = self.session.query(ExpressOrder).filter(
            ExpressOrder.logistics_id == logistics_id
        ).all()
        
        if not all_express:
            return None
        
        # 检查是否所有快递都已签收
        if all(e.status == LogisticsStatus.SIGNED for e in all_express):
            # 返回最后一个签收的时间
            last_signed = max(e.timestamp for e in all_express)
            return last_signed
        return None
    
    def _check_logistics_finish(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查物流完成时间"""
        logistics_id = self._resolve_to_logistics_id(related_type, related_id)
        if not logistics_id:
            return None
        
        logistics = self.session.query(Logistics).get(logistics_id)
        if logistics and logistics.status == LogisticsStatus.FINISH:
            return logistics.timestamp
        return None
    
    def _check_express_created(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查快递单创建时间 (需要 param1 指定快递单号或ID)"""
        # TODO: 需要明确如何指定具体快递单
        return None
    
    def _check_express_shipped(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查快递发出时间 (需要 param1 指定快递单号或ID)"""
        # TODO: 需要明确如何指定具体快递单
        return None
    
    def _check_express_signed(self, related_type, related_id, p1, p2) -> Optional[datetime]:
        """检查快递签收时间 (需要 param1 指定快递单号或ID)"""
        # TODO: 需要明确如何指定具体快递单
        return None
