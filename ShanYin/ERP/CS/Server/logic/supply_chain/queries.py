"""
供应链领域 - UI专用查询层

本模块提供供应链相关的UI查询函数，返回格式化字典供UI层直接使用。
遵循CQRS模式，只处理读操作，不涉及写操作。
"""

from typing import List, Dict, Optional, Any
from sqlalchemy import func, cast, String
from sqlalchemy.orm import joinedload
from models import (
    get_session, SupplyChain, Supplier, SKU
)
from logic.constants import (
    SKUType
)
from logic.master import get_partner_relations


# ============================================================================
# 1. 供应链协议相关查询
# ============================================================================

def get_supply_chain_with_pricing(
    session,
    sc_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    获取带有定价信息的供应链协议列表（专用于UI采购表单）
    
    Args:
        session: 数据库会话
        sc_type: 协议类型过滤（equipment/material）
    
    Returns:
        格式化后的供应链协议列表，包含定价详情
    """
    query = session.query(SupplyChain).options(joinedload(SupplyChain.items)).join(Supplier)

    if sc_type:
        query = query.filter(SupplyChain.type == sc_type)

    chains = query.order_by(SupplyChain.id.desc()).all()
    
    result = []
    for chain in chains:
        supplier = session.query(Supplier).get(chain.supplier_id)
        
        # 解析定价配置
        pricing_dict = chain.get_pricing_dict()
        
        result.append({
            "id": chain.id,
            "supplier_id": chain.supplier_id,
            "supplier_name": supplier.name if supplier else "未知供应商",
            "supplier": {"name": supplier.name} if supplier else None,
            "type": chain.type,
            "pricing_dict": pricing_dict,
            "payment_terms": chain.payment_terms or {},
            "contract_id": chain.contract_id
        })
    
    return result


def get_supply_chains_for_ui(
    session_arg=None,
    supplier_id: Optional[int] = None,
    sc_type: Optional[str] = None,
    status: Optional[str] = None,
    search_keyword: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    获取供应链协议列表（专用于UI展示）
    
    Args:
        session_arg: 可选的数据库会话，如果不传则自动创建
        supplier_id: 供应商ID过滤
        sc_type: 协议类型过滤（equipment/material）
        status: 状态过滤
        search_keyword: 搜索关键词（协议ID、供应商名称）
        limit: 返回数量限制
    
    Returns:
        格式化后的供应链协议列表
    """
    own_session = False
    if session_arg is None:
        session = get_session()
        own_session = True
    else:
        session = session_arg
    try:
        query = session.query(SupplyChain).join(Supplier)
        
        if supplier_id:
            query = query.filter(SupplyChain.supplier_id == supplier_id)
        
        if sc_type:
            query = query.filter(SupplyChain.type == sc_type)
        
        
        if search_keyword:
            query = query.filter(
                (SupplyChain.id.cast(String).contains(search_keyword)) |
                (Supplier.name.contains(search_keyword))
            )
        
        chains = query.order_by(SupplyChain.id.desc()).limit(limit).all()
        
        result = []
        for chain in chains:
            supplier = session.query(Supplier).get(chain.supplier_id)

            # 解析定价配置
            pricing_dict = chain.get_pricing_dict()

            # 解析结算条款
            payment_terms = chain.payment_terms or {}

            # 统计SKU数量
            sku_count = len(pricing_dict)

            # pricing_preview 现在是 sku_id，需要转换为名称用于显示
            preview_names = []
            for sku_id_key in list(pricing_dict.keys())[:5]:
                sku_id_int = int(sku_id_key) if str(sku_id_key).isdigit() else None
                if sku_id_int:
                    sku_obj = session.query(SKU).get(sku_id_int)
                    preview_names.append(sku_obj.name if sku_obj else sku_id_key)
                else:
                    preview_names.append(sku_id_key)

            result.append({
                "id": chain.id,
                "supplier_id": chain.supplier_id,
                "supplier_name": supplier.name if supplier else "未知供应商",
                "supplier": {"name": supplier.name} if supplier else None,
                "type": chain.type,
                "type_label": _get_sc_type_label(chain.type),
                "status": "active",
                "status_label": "正常",
                "pricing_count": sku_count,
                "pricing_preview": preview_names,  # 转换为 SKU 名称用于显示
                "payment_terms": {
                    "prepayment_ratio": payment_terms.get("prepayment_ratio", 0),
                    "prepayment_ratio_pct": int(payment_terms.get("prepayment_ratio", 0) * 100),
                    "balance_period": payment_terms.get("balance_period", 0),
                    "day_rule": payment_terms.get("day_rule", "自然日"),
                    "start_trigger": payment_terms.get("start_trigger", "入库")
                },
                "contract_id": chain.contract_id,
                "created_at": "",
                "updated_at": "",
                "partners": get_partner_relations(
                    owner_type="supply_chain",
                    owner_id=chain.id,
                    active_only=True
                )
            })

        return result
    finally:
        if own_session:
            session.close()


def get_supply_chain_detail_for_ui(sc_id: int) -> Optional[Dict[str, Any]]:
    """
    获取供应链协议详情（专用于UI展示）
    
    Args:
        sc_id: 供应链协议ID
    
    Returns:
        格式化后的供应链协议详情，如果不存在则返回None
    """
    session = get_session()
    try:
        chain = session.query(SupplyChain).options(joinedload(SupplyChain.items)).get(sc_id)
        if not chain:
            return None
        
        supplier = session.query(Supplier).get(chain.supplier_id)
        
        # 解析定价配置
        try:
            pricing_dict = chain.get_pricing_dict() if hasattr(chain, 'get_pricing_dict') else {}
            if not isinstance(pricing_dict, dict):
                pricing_dict = {}
        except Exception:
            pricing_dict = {}

        # 格式化定价明细（pricing_config 的 key 已改为 sku_id，需查询 SKU 名称用于显示）
        pricing_details = []
        sku_name_map = {}
        if pricing_dict:
            for sku_id_key, price in pricing_dict.items():
                sku_id_int = int(sku_id_key) if str(sku_id_key).isdigit() else None
                if sku_id_int:
                    sku_obj = session.query(SKU).get(sku_id_int)
                    sku_display_name = sku_obj.name if sku_obj else sku_id_key
                    sku_name_map[sku_id_key] = sku_display_name
                else:
                    sku_display_name = sku_id_key
                price_val = price.get("price") if isinstance(price, dict) else (price if isinstance(price, (int, float)) else 0)
                is_floating = price.get("is_floating", False) if isinstance(price, dict) else (price == "浮动" if isinstance(price, str) else False)
                pricing_details.append({
                    "sku_id": sku_id_int,
                    "sku_name": sku_display_name,
                    "price": price_val,
                    "price_display": f"¥{price_val:,.2f}" if isinstance(price_val, (int, float)) else str(price),
                    "is_floating": is_floating
                })
        
        # 解析结算条款
        payment_terms = chain.payment_terms if isinstance(chain.payment_terms, dict) else {}

        return {
            "id": chain.id,
            "supplier_id": chain.supplier_id,
            "supplier_name": supplier.name if supplier else "未知供应商",
            "supplier": {"name": supplier.name} if supplier else None,
            "supplier_contact": supplier.info if supplier else {},
            "type": chain.type,
            "type_label": _get_sc_type_label(chain.type),
            "status": "active",
            "status_label": "正常",
            "pricing_details": pricing_details,
            "sku_name_map": sku_name_map,
            "pricing_count": len(pricing_details),
            "payment_terms": {
                "prepayment_ratio": payment_terms.get("prepayment_ratio", 0),
                "prepayment_ratio_pct": int(payment_terms.get("prepayment_ratio", 0) * 100),
                "balance_period": payment_terms.get("balance_period", 0),
                "day_rule": payment_terms.get("day_rule", "自然日"),
                "start_trigger": payment_terms.get("start_trigger", "入库")
            },
            "contract_id": chain.contract_id,
            "notes": "",
            "created_at": "",
            "updated_at": "",
            "partners": get_partner_relations(
                owner_type="supply_chain",
                owner_id=chain.id,
                active_only=True
            )
        }
    finally:
        session.close()


# ============================================================================
# 3. 私有辅助函数
# ============================================================================

def _get_status_label(status: Optional[str]) -> str:
    """获取状态中文标签"""
    status_map = {
        "active": "正常",
        "inactive": "停用",
        "pending": "待审核",
        "verified": "已认证",
    }
    return status_map.get(status, status or "未知")


def _get_sc_type_label(sc_type: Optional[str]) -> str:
    """获取供应链类型中文标签"""
    type_map = {
        SKUType.EQUIPMENT: "设备",
        SKUType.MATERIAL: "物料",
        "equipment": "设备",
        "material": "物料",
    }
    return type_map.get(sc_type, sc_type or "未知")
