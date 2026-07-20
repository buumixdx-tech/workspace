"""
时间规则领域 - UI专用查询层

本模块提供时间规则相关的UI查询函数，返回格式化字典供UI层直接使用。
遵循CQRS模式，只处理读操作，不涉及写操作。
"""

from typing import List, Dict, Optional, Any
from sqlalchemy import func, cast, String
from models import (
    get_session, TimeRule, Business, VirtualContract, SupplyChain, Supplier
)
from logic.constants import (
    TimeRuleStatus, TimeRuleRelatedType, TimeRuleDirection, TimeRuleInherit
)


# ============================================================================
# 1. 时间规则列表查询
# ============================================================================

def get_time_rules_for_ui(
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
    status_list: Optional[List[str]] = None,
    party: Optional[str] = None,
    search_keyword: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    获取时间规则列表（专用于UI展示）
    
    Args:
        related_type: 关联类型过滤（business/vc/supply_chain）
        related_id: 关联对象ID过滤
        status_list: 状态过滤列表
        party: 责任方过滤
        search_keyword: 搜索关键词（规则ID、触发事件等）
        limit: 返回数量限制
    
    Returns:
        格式化后的时间规则列表
    """
    session = get_session()
    try:
        query = session.query(TimeRule)
        
        # 关联类型过滤
        if related_type:
            query = query.filter(TimeRule.related_type == related_type)
        
        # 关联对象ID过滤
        if related_id:
            query = query.filter(TimeRule.related_id == related_id)
        
        # 状态过滤
        if status_list:
            query = query.filter(TimeRule.status.in_(status_list))
        
        # 责任方过滤
        if party:
            query = query.filter(TimeRule.party == party)
        
        # 搜索关键词
        if search_keyword:
            query = query.filter(
                (cast(TimeRule.id, String).contains(search_keyword)) |
                (TimeRule.trigger_event.contains(search_keyword)) |
                (TimeRule.target_event.contains(search_keyword))
            )
        
        rules = query.order_by(TimeRule.timestamp.desc()).limit(limit).all()
        
        result = []
        for rule in rules:
            # 获取关联对象信息
            related_info = _get_related_object_info(session, rule)
            
            result.append({
                "id": rule.id,
                "related_type": rule.related_type,
                "related_type_label": _get_related_type_label(rule.related_type),
                "related_id": rule.related_id,
                "related_name": related_info.get("name", "未知"),
                "related_detail": related_info.get("detail", ""),
                "party": rule.party,
                "party_label": _get_party_label(rule.party),
                "trigger_event": rule.trigger_event,
                "target_event": rule.target_event,
                "offset": rule.offset,
                "unit": rule.unit,
                "direction": rule.direction,
                "direction_label": _get_direction_label(rule.direction),
                "status": rule.status,
                "status_label": _get_status_label(rule.status),
                "flag_time": rule.flag_time.strftime("%Y-%m-%d %H:%M") if rule.flag_time else None,
                "created_at": rule.timestamp.strftime("%Y-%m-%d %H:%M") if rule.timestamp else "",
                "updated_at": rule.resultstamp.strftime("%Y-%m-%d %H:%M") if rule.resultstamp else ""
            })
        
        return result
    finally:
        session.close()


def get_time_rule_detail_for_ui(rule_id: int) -> Optional[Dict[str, Any]]:
    """
    获取时间规则详情（专用于UI展示）
    
    Args:
        rule_id: 时间规则ID
    
    Returns:
        格式化后的时间规则详情，如果不存在则返回None
    """
    session = get_session()
    try:
        rule = session.query(TimeRule).get(rule_id)
        if not rule:
            return None
        
        # 获取关联对象信息
        related_info = _get_related_object_info(session, rule)
        
        return {
            "id": rule.id,
            "related_type": rule.related_type,
            "related_type_label": _get_related_type_label(rule.related_type),
            "related_id": rule.related_id,
            "related_name": related_info.get("name", "未知"),
            "related_detail": related_info.get("detail", ""),
            "party": rule.party,
            "party_label": _get_party_label(rule.party),
            "trigger_event": rule.trigger_event,
            "target_event": rule.target_event,
            "offset": rule.offset,
            "unit": rule.unit,
            "direction": rule.direction,
            "direction_label": _get_direction_label(rule.direction),
            "flag_time": rule.flag_time.strftime("%Y-%m-%d %H:%M") if rule.flag_time else None,
            "status": rule.status,
            "status_label": _get_status_label(rule.status),
            "created_at": rule.timestamp.strftime("%Y-%m-%d %H:%M") if rule.timestamp else "",
            "updated_at": rule.timestamp.strftime("%Y-%m-%d %H:%M") if rule.timestamp else ""
        }
    finally:
        session.close()


# ============================================================================
# 2. 时间规则统计查询
# ============================================================================

def get_time_rules_dashboard_summary() -> Dict[str, Any]:
    """
    获取时间规则仪表盘汇总数据（专用于UI展示）
    
    Returns:
        包含统计数据的字典
    """
    session = get_session()
    try:
        # 按状态统计
        status_counts = {}
        for status in [TimeRuleStatus.ACTIVE, TimeRuleStatus.HAS_RESULT, TimeRuleStatus.ENDED, TimeRuleStatus.INACTIVE]:
            count = session.query(TimeRule).filter(TimeRule.status == status).count()
            status_counts[status] = count
        
        # 按关联类型统计
        type_counts = {}
        for rel_type in [TimeRuleRelatedType.BUSINESS, TimeRuleRelatedType.VIRTUAL_CONTRACT, TimeRuleRelatedType.SUPPLY_CHAIN]:
            count = session.query(TimeRule).filter(TimeRule.related_type == rel_type).count()
            type_counts[rel_type] = count
        
        # 今日更新规则数
        from datetime import datetime, timedelta
        today = datetime.now().date()
        today_count = session.query(TimeRule).filter(
            func.date(TimeRule.timestamp) == today
        ).count()
        
        # 即将触发规则数（已标记时间且未执行）
        upcoming_count = session.query(TimeRule).filter(
            TimeRule.flag_time.isnot(None),
            TimeRule.status.in_([TimeRuleStatus.ACTIVE, TimeRuleStatus.HAS_RESULT])
        ).count()
        
        return {
            "summary": {
                "total": sum(status_counts.values()),
                "active": status_counts.get(TimeRuleStatus.ACTIVE, 0),
                "triggered": status_counts.get(TimeRuleStatus.HAS_RESULT, 0),
                "executed": status_counts.get(TimeRuleStatus.ENDED, 0),
                "inactive": status_counts.get(TimeRuleStatus.INACTIVE, 0),
                "today_updated": today_count,
                "upcoming": upcoming_count
            },
            "by_type": {
                "business": type_counts.get(TimeRuleRelatedType.BUSINESS, 0),
                "virtual_contract": type_counts.get(TimeRuleRelatedType.VIRTUAL_CONTRACT, 0),
                "supply_chain": type_counts.get(TimeRuleRelatedType.SUPPLY_CHAIN, 0)
            }
        }
    finally:
        session.close()


# ============================================================================
# 3. 私有辅助函数
# ============================================================================

def _get_related_object_info(session, rule) -> Dict[str, str]:
    """获取关联对象信息"""
    if rule.related_type == TimeRuleRelatedType.BUSINESS:
        obj = session.query(Business).get(rule.related_id)
        if obj:
            customer = session.query(ChannelCustomer).get(obj.customer_id)
            return {
                "name": f"业务-{obj.id}",
                "detail": f"客户: {customer.name if customer else '未知'}"
            }
    elif rule.related_type == TimeRuleRelatedType.VIRTUAL_CONTRACT:
        obj = session.query(VirtualContract).get(rule.related_id)
        if obj:
            return {
                "name": f"合同-{obj.id}",
                "detail": f"类型: {obj.type}"
            }
    elif rule.related_type == TimeRuleRelatedType.SUPPLY_CHAIN:
        obj = session.query(SupplyChain).get(rule.related_id)
        if obj:
            supplier = session.query(Supplier).get(obj.supplier_id)
            return {
                "name": f"供应链-{obj.id}",
                "detail": f"供应商: {supplier.name if supplier else '未知'}"
            }
    
    return {"name": "未知", "detail": "关联对象不存在"}


def _get_related_type_label(related_type: str) -> str:
    """获取关联类型中文标签"""
    type_map = {
        TimeRuleRelatedType.BUSINESS: "业务",
        TimeRuleRelatedType.VIRTUAL_CONTRACT: "虚拟合同",
        TimeRuleRelatedType.SUPPLY_CHAIN: "供应链",
    }
    return type_map.get(related_type, related_type)


def _get_party_label(party: Optional[str]) -> str:
    """获取责任方中文标签"""
    party_map = {
        "ourselves": "我方",
        "customer": "客户",
        "supplier": "供应商",
        "third_party": "第三方",
    }
    return party_map.get(party, party or "未知")


def _get_direction_label(direction: Optional[str]) -> str:
    """获取方向中文标签"""
    direction_map = {
        TimeRuleDirection.BEFORE: "标杆时间之前",
        TimeRuleDirection.AFTER: "标杆时间之后",
    }
    return direction_map.get(direction, direction or "未知")


def _get_status_label(status: Optional[str]) -> str:
    """获取状态中文标签"""
    status_map = {
        TimeRuleStatus.ACTIVE: "正常",
        TimeRuleStatus.HAS_RESULT: "有结果",
        TimeRuleStatus.ENDED: "已结束",
        TimeRuleStatus.INACTIVE: "停用",
    }
    return status_map.get(status, status or "未知")


# ============================================================================
# 4. 新增：get_rules_for_entity 和 get_rule_by_id 函数
# ============================================================================

def get_inherited_time_rules(
    session,
    related_id: int,
    related_type: str,
    include_self: bool = True
) -> List[Dict[str, Any]]:
    """
    获取可继承的时间规则列表（专用于UI展示）
    
    该函数查找与给定实体相关联的时间规则，包括直接定义的和可继承的规则。
    
    Args:
        session: 数据库会话
        related_id: 关联对象ID
        related_type: 关联类型（business/vc/supply_chain）
        include_self: 是否包含自身定义的规则
    
    Returns:
        格式化后的可继承时间规则列表
    """
    result = []
    
    # 如果包含自身定义的规则
    if include_self:
        rules = session.query(TimeRule).filter(
            TimeRule.related_id == related_id,
            TimeRule.related_type == related_type,
            TimeRule.status.in_([TimeRuleStatus.ACTIVE, TimeRuleStatus.HAS_RESULT])
        ).all()
        
        for r in rules:
            result.append({
                "id": r.id,
                "related_type": r.related_type,
                "related_id": r.related_id,
                "party": r.party,
                "trigger_event": r.trigger_event,
                "target_event": r.target_event,
                "offset": r.offset,
                "unit": r.unit,
                "direction": r.direction,
                "status": r.status,
                "flag_time": r.flag_time.strftime("%Y-%m-%d %H:%M") if r.flag_time else None,
                "source": "直接定义",
                "is_inherited": False
            })
    
    return result


def get_rules_for_entity(
    session,
    related_id: int,
    related_type: str,
    include_inherited: bool = True
) -> List[Dict[str, Any]]:
    """
    获取与实体关联的所有时间规则
    """
    # 直接关联的规则
    rules = session.query(TimeRule).filter(
        TimeRule.related_id == related_id,
        TimeRule.related_type == related_type
    ).all()
    
    # 如果需要，获取继承的规则 (Logic placeholder)
    if include_inherited:
        # 这里可以添加继承逻辑
        pass
    
    return [
        {
            "id": r.id,
            "party": r.party,
            "trigger_event": r.trigger_event,
            "target_event": r.target_event,
            "offset": r.offset,
            "unit": r.unit,
            "direction": r.direction,
            "status": r.status,
            "flag_time": r.flag_time.strftime("%Y-%m-%d %H:%M") if r.flag_time else None
        }
        for r in rules
    ]


def get_rule_by_id(session, rule_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取时间规则
    """
    rule = session.query(TimeRule).get(rule_id)
    if not rule:
        return None
        
    return {
        "id": rule.id,
        "party": rule.party,
        "trigger_event": rule.trigger_event,
        "target_event": rule.target_event,
        "offset": rule.offset,
        "unit": rule.unit,
        "direction": rule.direction,
        "status": rule.status,
        "flag_time": rule.flag_time.strftime("%Y-%m-%d %H:%M") if rule.flag_time else None
    }


def get_inherited_rules_for_ui(business_id: int, sc_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    获取业务和供应链可继承的规则预览 (专用于 UI 展示)
    """
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        query = session.query(TimeRule).filter(
            ((TimeRule.related_id == business_id) & (TimeRule.related_type == TimeRuleRelatedType.BUSINESS))
        )
        if sc_id:
            query = query.filter(
                ((TimeRule.related_id == business_id) & (TimeRule.related_type == TimeRuleRelatedType.BUSINESS)) |
                ((TimeRule.related_id == sc_id) & (TimeRule.related_type == TimeRuleRelatedType.SUPPLY_CHAIN))
            )
            
        rules = query.filter(TimeRule.inherit != TimeRuleInherit.SELF).all()
        
        result = []
        for r in rules:
            source_name = "业务" if r.related_type == TimeRuleRelatedType.BUSINESS else "供应链"
            result.append({
                "source": f"{source_name}",
                "party": r.party,
                "trigger_event": r.trigger_event,
                "offset": f"{r.offset} {r.unit}",
                "target_event": r.target_event
            })
        return result
    finally:
        session.close()
