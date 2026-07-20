"""
物流领域 - UI专用查询层

本模块提供物流相关的UI查询函数，返回格式化字典供UI层直接使用。
遵循CQRS模式，只处理读操作，不涉及写操作。
"""

from typing import List, Dict, Optional, Any
from sqlalchemy import func, cast, String
from models import (
    get_session, Logistics, ExpressOrder, VirtualContract, Point
)
from logic.constants import (
    LogisticsStatus, VCType, SubjectStatus
)


# ============================================================================
# 1. 物流任务相关查询
# ============================================================================

def get_logistics_by_id(log_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取物流任务详情
    """
    session = get_session()
    try:
        log = session.query(Logistics).get(log_id)
        if not log:
            return None
        return {
            "id": log.id,
            "virtual_contract_id": log.virtual_contract_id,
            "status": log.status,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M") if log.timestamp else None
        }
    finally:
        session.close()


def get_logistics_by_vc(vc_id: int) -> Optional[Dict[str, Any]]:
    """
    根据虚拟合同ID获取关联的物流任务
    
    Args:
        vc_id: 虚拟合同ID
    
    Returns:
        物流任务详情字典，如果不存在则返回None
    """
    session = get_session()
    try:
        log = session.query(Logistics).filter(
            Logistics.virtual_contract_id == vc_id
        ).first()
        
        if not log:
            return None
        
        return {
            "id": log.id,
            "virtual_contract_id": log.virtual_contract_id,
            "status": log.status,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M") if log.timestamp else None,
            "finance_triggered": log.finance_triggered
        }
    finally:
        session.close()


def get_logistics_list_for_ui(
    status_list: Optional[List[str]] = None,
    vc_type_list: Optional[List[str]] = None,
    vc_id: Optional[int] = None,
    search_keyword: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    获取物流任务列表（专用于UI展示）
    
    Args:
        status_list: 物流状态过滤列表
        vc_type_list: 虚拟合同类型过滤列表
        vc_id: 虚拟合同ID过滤
        search_keyword: 搜索关键词（合同描述、物流ID）
        limit: 返回数量限制
    
    Returns:
        格式化后的物流任务列表
    """
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        query = session.query(Logistics).options(
            joinedload(Logistics.virtual_contract),
            joinedload(Logistics.express_orders)
        )
        
        # 状态过滤
        if status_list:
            query = query.filter(Logistics.status.in_(status_list))
        
        # 虚拟合同类型过滤
        if vc_type_list:
            query = query.join(VirtualContract).filter(VirtualContract.type.in_(vc_type_list))
        
        # 虚拟合同ID过滤
        if vc_id:
            query = query.filter(Logistics.virtual_contract_id == vc_id)
        
        # 搜索关键词
        if search_keyword:
            # 如果没 join 过，需要 join 以便搜 description
            if not vc_type_list:
                query = query.join(VirtualContract)
            query = query.filter(
                (VirtualContract.description.contains(search_keyword)) |
                (cast(Logistics.id, String).contains(search_keyword))
            )
        
        logistics_list = query.order_by(Logistics.id.desc()).limit(limit).all()
        
        result = []
        for log in logistics_list:
            vc = log.virtual_contract
            
            # 统计快递单数量 (Already loaded via joinedload)
            express_count = len(log.express_orders)
            
            result.append({
                "id": log.id,
                "vc_id": log.virtual_contract_id,
                "vc_description": vc.description if vc else "N/A",
                "vc_type": vc.type if vc else "N/A",
                "status": log.status,
                "status_label": _get_logistics_status_label(log.status),
                "express_count": express_count,
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M") if log.timestamp else "N/A",
                "finance_triggered": log.finance_triggered,
                "is_return": (vc.type == VCType.RETURN) if vc else False
            })
        
        return result
    finally:
        session.close()


def get_logistics_list_by_vc(vc_id: int) -> List[Dict[str, Any]]:
    """
    获取虚拟合同关联的所有物流批次及快递单 (专用于 UI 展示)
    """
    session = get_session()
    try:
        from sqlalchemy.orm import joinedload
        logs = session.query(Logistics).options(
            joinedload(Logistics.express_orders)
        ).filter(Logistics.virtual_contract_id == vc_id).order_by(Logistics.timestamp.asc()).all()
        
        result = []
        for l in logs:
            orders_data = []
            for o in l.express_orders:
                addr_data = o.address_info or {}
                orders_data.append({
                    "tracking_number": o.tracking_number,
                    "status": o.status,
                    "发货点位": addr_data.get("发货点位名称", "未知"),
                    "收货点位": addr_data.get("收货点位名称", "未知"),
                    "items": o.items or []
                })
            
            result.append({
                "id": l.id,
                "status": l.status,
                "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M") if l.timestamp else "未知",
                "orders": orders_data
            })
        return result
    finally:
        session.close()


def get_express_orders_by_logistics(logistics_id: int) -> List[Dict[str, Any]]:
    """
    获取物流任务下的所有快递单
    """
    session = get_session()
    try:
        orders = session.query(ExpressOrder).filter(ExpressOrder.logistics_id == logistics_id).all()
        return [
            {
                "id": o.id,
                "tracking_number": o.tracking_number,
                "logistics_id": o.logistics_id,
                "status": o.status,
                "address_info": o.address_info,
                "items": o.items,
                "created_at": o.timestamp.strftime("%Y-%m-%d %H:%M") if o.timestamp else ""
            }
            for o in orders
        ]
    finally:
        session.close()


def get_express_orders_for_ui(
    logistics_id: Optional[int] = None,
    status_list: Optional[List[str]] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    获取快递单列表（专用于UI展示）
    
    Args:
        logistics_id: 物流任务ID过滤
        status_list: 状态过滤列表
        limit: 返回数量限制
    
    Returns:
        格式化后的快递单列表
    """
    session = get_session()
    try:
        query = session.query(ExpressOrder)
        
        if logistics_id:
            query = query.filter(ExpressOrder.logistics_id == logistics_id)
        
        if status_list:
            query = query.filter(ExpressOrder.status.in_(status_list))
        
        orders = query.order_by(ExpressOrder.timestamp.desc()).limit(limit).all()
        
        result = []
        for order in orders:
            # 解析地址信息
            addr_info = order.address_info or {}
            
            # 格式化货品明细
            items_summary = _format_express_items(order.items)
            
            result.append({
                "id": order.id,
                "logistics_id": order.logistics_id,
                "tracking_number": order.tracking_number,
                "status": order.status,
                "status_label": _get_logistics_status_label(order.status),
                "status_icon": _get_logistics_status_icon(order.status),
                "point_name": addr_info.get("收货点位名称", addr_info.get("发货点位名称", "未知点位")),
                "address": addr_info.get("address", "未知地址"),
                "items_summary": items_summary,
                "raw_items": order.items,
                "created_at": order.timestamp.strftime("%Y-%m-%d %H:%M") if order.timestamp else "",
                "updated_at": order.timestamp.strftime("%Y-%m-%d %H:%M") if order.timestamp else ""
            })
        
        return result
    finally:
        session.close()


def get_logistics_by_vc_for_ui(vc_id: int) -> List[Dict[str, Any]]:
    """
    按虚拟合同获取物流任务（专用于UI展示）
    
    Args:
        vc_id: 虚拟合同ID
    
    Returns:
        格式化后的物流任务列表
    """
    return get_logistics_list_for_ui(vc_id=vc_id)


def get_logistics_dashboard_summary() -> Dict[str, Any]:
    """
    获取物流仪表盘汇总数据（专用于UI展示）
    
    Returns:
        包含统计数据的字典
    """
    session = get_session()
    try:
        # 各状态物流数量统计
        status_counts = {}
        for status in [LogisticsStatus.PENDING, LogisticsStatus.TRANSIT, LogisticsStatus.SIGNED, LogisticsStatus.FINISH]:
            count = session.query(Logistics).filter(Logistics.status == status).count()
            status_counts[status] = count
        
        # 各状态快递单数量统计
        express_counts = {}
        for status in [LogisticsStatus.PENDING, LogisticsStatus.TRANSIT, LogisticsStatus.SIGNED]:
            count = session.query(ExpressOrder).filter(ExpressOrder.status == status).count()
            express_counts[status] = count
        
        # 今日新增物流数
        from datetime import datetime, timedelta
        today = datetime.now().date()
        today_count = session.query(Logistics).filter(
            func.date(Logistics.timestamp) == today
        ).count()
        
        return {
            "logistics_summary": {
                "total": sum(status_counts.values()),
                "pending": status_counts.get(LogisticsStatus.PENDING, 0),
                "transit": status_counts.get(LogisticsStatus.TRANSIT, 0),
                "signed": status_counts.get(LogisticsStatus.SIGNED, 0),
                "finish": status_counts.get(LogisticsStatus.FINISH, 0),
                "today_new": today_count
            },
            "express_summary": {
                "total": sum(express_counts.values()),
                "pending": express_counts.get(LogisticsStatus.PENDING, 0),
                "transit": express_counts.get(LogisticsStatus.TRANSIT, 0),
                "signed": express_counts.get(LogisticsStatus.SIGNED, 0)
            }
        }
    finally:
        session.close()


# ============================================================================
# 5. 私有辅助函数
# ============================================================================

def _format_express_items(items: Optional[List[Dict]]) -> str:
    """
    格式化快递单货品明细为可读字符串
    
    Args:
        items: 货品明细列表
    
    Returns:
        格式化后的字符串
    """
    if not items:
        return "无明细"
    
    formatted_items = []
    for item in items:
        if isinstance(item, dict):
            name = item.get('sku_name') or item.get('name') or '未知物品'
            qty = item.get('qty', 0)
            formatted_items.append(f"{name} x{qty}")
        else:
            formatted_items.append(str(item))
    
    return "; ".join(formatted_items[:3]) + ("..." if len(formatted_items) > 3 else "")


def _get_logistics_status_label(status: str) -> str:
    """获取物流状态中文标签"""
    status_map = {
        LogisticsStatus.PENDING: "待发货",
        LogisticsStatus.TRANSIT: "运输中",
        LogisticsStatus.SIGNED: "已签收",
        LogisticsStatus.FINISH: "已完成",
    }
    return status_map.get(status, status)


def _get_logistics_status_icon(status: str) -> str:
    """获取物流状态图标"""
    icon_map = {
        LogisticsStatus.PENDING: "⏳",
        LogisticsStatus.TRANSIT: "🚚",
        LogisticsStatus.SIGNED: "✅",
        LogisticsStatus.FINISH: "✅",
    }
    return icon_map.get(status, "📦")
