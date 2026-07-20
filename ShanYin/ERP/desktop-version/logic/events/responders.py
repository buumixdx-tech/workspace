"""
内置事件响应器实现
包含规划中定义的核心响应逻辑
"""
from sqlalchemy.orm import Session
from models import TimeRule, MaterialInventory, SKU, SystemEvent
from logic.constants import TimeRuleStatus, LogisticsStatus, SystemConstants, SystemEventType, SystemAggregateType
from datetime import datetime


def time_rule_completion_listener(session: Session, event: SystemEvent):
    """
    时间规则完成响应器
    监听物流主单状态变为 FINISH 后，自动将关联的时间规则触发时间记录下来
    """
    if event.event_type != SystemEventType.LOGISTICS_STATUS_CHANGED:
        return
    
    payload = event.payload or {}
    if payload.get("to") != LogisticsStatus.FINISH:
        return

    # 通过 Logistics 反查 VC ID
    from models import Logistics
    log = session.query(Logistics).get(event.aggregate_id)
    if not log or not log.virtual_contract_id:
        return
    vc_id = log.virtual_contract_id
    
    # 查找该 VC 关联的所有"触发事件=入库/签收"的规则
    from logic.constants import TimeRuleRelatedType, EventType
    rules = session.query(TimeRule).filter(
        TimeRule.related_id == vc_id,
        TimeRule.related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT,
        TimeRule.trigger_event.in_([
            EventType.VCLevel.SUBJECT_SIGNED, 
            EventType.VCLevel.SUBJECT_FINISH,
            EventType.LogisticsLevel.LOGISTICS_FINISH
        ]),
        TimeRule.status == TimeRuleStatus.ACTIVE
    ).all()
    
    for rule in rules:
        rule.trigger_time = datetime.now()
    
    if rules:
        # 记录规则触发子事件
        from logic.events.dispatcher import emit_event
        emit_event(session, SystemEventType.RULES_TRIGGERED_BY_LOGISTICS, SystemAggregateType.TIME_RULE, vc_id, {
            "rule_count": len(rules),
            "trigger_source": f"LOGISTICS_STATUS_CHANGED(FINISH)"
        })


def inventory_low_stock_listener(session: Session, event: SystemEvent):
    """
    库存预警响应器
    监听物料供应事件后，检查剩余库存并自动发出低水位通知
    """
    if event.event_type != SystemEventType.VC_CREATED:
        return
    
    payload = event.payload or {}
    vc_type = payload.get("type")
    
    # 只关注物料供应类型的 VC
    from logic.constants import VCType
    if vc_type != VCType.MATERIAL_SUPPLY:
        return
    
    # 检查所有物料库存的水位
    LOW_STOCK_THRESHOLD = 10  # 低水位阈值

    low_stock_items = []
    materials = session.query(MaterialInventory).filter(MaterialInventory.qty > 0).all()

    for mat in materials:
        if mat.qty <= LOW_STOCK_THRESHOLD:
            sku = session.query(SKU).get(mat.sku_id)
            sku_name = sku.name if sku else f"SKU-{mat.sku_id}"
            point = session.query(Point).get(mat.point_id) if mat.point_id else None
            point_name = point.name if point else f"点位{mat.point_id}"
            low_stock_items.append({
                "sku_id": mat.sku_id,
                "sku_name": sku_name,
                "warehouse": point_name,
                "remaining": mat.qty
            })
    
    if low_stock_items:
        # 发布库存预警事件
        from logic.events.dispatcher import emit_event
        emit_event(session, SystemEventType.INVENTORY_LOW_STOCK_WARNING, SystemAggregateType.MATERIAL_INVENTORY, 0, {
            "low_stock_items": low_stock_items,
            "threshold": LOW_STOCK_THRESHOLD,
            "triggered_by": event.id
        })


# ========== 响应器注册函数 ==========

def register_all_listeners():
    """注册所有内置响应器"""
    from logic.events.listeners import register_listener
    
    register_listener(SystemEventType.LOGISTICS_STATUS_CHANGED, time_rule_completion_listener)
    register_listener(SystemEventType.VC_CREATED, inventory_low_stock_listener)
    
    print("[EventResponders] 已注册内置响应器 (重构版)")
