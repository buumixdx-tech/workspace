from sqlalchemy.orm import Session
from models import TimeRule
from .schemas import TimeRuleSchema
from logic.base import ActionResult
from logic.events.dispatcher import emit_event
from logic.constants import SystemEventType, SystemAggregateType
from datetime import datetime

def save_rule_action(session: Session, payload: TimeRuleSchema) -> ActionResult:
    """保存或更新时间规则 Action"""
    try:
        rule = None
        if hasattr(payload, 'id') and payload.id:
            rule = session.query(TimeRule).get(payload.id)
        
        if not rule:
            rule = TimeRule()
            session.add(rule)
        
        rule.related_id = payload.related_id
        rule.related_type = payload.related_type
        rule.party = payload.party
        rule.trigger_event = payload.trigger_event
        rule.target_event = payload.target_event
        rule.offset = payload.offset
        rule.unit = payload.unit
        rule.direction = payload.direction
        rule.inherit = payload.inherit
        rule.status = payload.status
        rule.timestamp = datetime.now()
        
        session.flush()
        emit_event(session, SystemEventType.RULE_UPDATED, SystemAggregateType.TIME_RULE, rule.id, {"related_id": rule.related_id})
        session.commit()
        return ActionResult(success=True, data={"rule_id": rule.id}, message="规则已保存")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def delete_rule_action(session: Session, rule_id: int) -> ActionResult:
    """删除时间规则 Action"""
    try:
        rule = session.query(TimeRule).get(rule_id)
        if not rule:
            return ActionResult(success=False, error="规则不存在")
        
        session.delete(rule)
        emit_event(session, SystemEventType.RULE_DELETED, SystemAggregateType.TIME_RULE, rule_id)
        session.commit()
        return ActionResult(success=True, message="规则已删除")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def persist_draft_rules_action(session: Session, draft_rules: list, related_type: str, related_id: int) -> ActionResult:
    """持久化草稿规则 Action"""
    try:
        from logic.constants import TimeRuleStatus
        count = 0
        for r in draft_rules:
            new_rule = TimeRule(
                related_id=related_id,
                related_type=related_type,
                party=r.get("party"),
                trigger_event=r.get("trigger_event"),
                target_event=r.get("target_event"),
                offset=r.get("offset"),
                unit=r.get("unit"),
                direction=r.get("direction"),
                inherit=r.get("inherit", 0),
                status=r.get("status", TimeRuleStatus.ACTIVE),
                timestamp=datetime.now()
            )
            session.add(new_rule)
            count += 1
        session.flush()
        emit_event(session, SystemEventType.RULE_UPDATED, SystemAggregateType.TIME_RULE, related_id, {"msg": f"Bulk persisted {count} rules"})
        session.commit()
        return ActionResult(success=True, message=f"已成功持久化 {count} 条规则")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))
