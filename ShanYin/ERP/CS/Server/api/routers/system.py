from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.deps import get_db, verify_token
from models import VirtualContract, Business, TimeRule, SystemEvent

router = APIRouter(prefix="/api/v1/system", tags=["系统"])


@router.get("/health", summary="健康检查")
def health():
    return {"success": True, "data": {"status": "ok"}, "error": None, "message": "服务正常"}


@router.get("/status", summary="系统状态看板", dependencies=[Depends(verify_token)])
def system_status(session: Session = Depends(get_db)):
    """AI Agent 看板：返回待办、预警、关键指标。"""
    from logic.constants import VCStatus, TimeRuleStatus
    active_vcs = session.query(VirtualContract).filter(VirtualContract.status == VCStatus.EXE).count()
    active_biz = session.query(Business).filter(Business.status.notin_(["业务终止", "业务完成"])).count()
    red_rules = session.query(TimeRule).filter(TimeRule.warning == "红色", TimeRule.status.in_([TimeRuleStatus.ACTIVE, TimeRuleStatus.HAS_RESULT])).count()
    orange_rules = session.query(TimeRule).filter(TimeRule.warning == "橙色", TimeRule.status.in_([TimeRuleStatus.ACTIVE, TimeRuleStatus.HAS_RESULT])).count()
    recent_events = session.query(SystemEvent).filter(SystemEvent.pushed_to_ai == False).count()
    return {
        "success": True,
        "data": {
            "active_virtual_contracts": active_vcs,
            "active_businesses": active_biz,
            "red_alerts": red_rules,
            "orange_alerts": orange_rules,
            "unread_events": recent_events,
        }
    }


@router.get("/tools", summary="AI Agent 工具清单", dependencies=[Depends(verify_token)])
def tool_manifest():
    """返回简化版工具清单，供 AI Agent 发现可用操作。"""
    tools = [
        {"name": "create_customer", "endpoint": "POST /api/v1/master/create-customer", "description": "创建渠道客户", "params": ["name", "info"]},
        {"name": "create_supplier", "endpoint": "POST /api/v1/master/create-supplier", "description": "创建供应商", "params": ["name", "category", "address"]},
        {"name": "create_sku", "endpoint": "POST /api/v1/master/create-sku", "description": "创建SKU", "params": ["supplier_id", "name", "type_level1"]},
        {"name": "create_business", "endpoint": "POST /api/v1/business/create", "description": "创建业务项", "params": ["customer_id"]},
        {"name": "advance_business_stage", "endpoint": "POST /api/v1/business/advance-stage", "description": "推进业务阶段", "params": ["business_id", "next_status"]},
        {"name": "create_procurement_vc", "endpoint": "POST /api/v1/vc/create-procurement", "description": "创建设备采购执行单", "params": ["vc.business_id", "vc.items", "vc.total_amt"]},
        {"name": "create_material_supply_vc", "endpoint": "POST /api/v1/vc/create-material-supply", "description": "创建物料供应执行单", "params": ["vc.business_id", "vc.order"]},
        {"name": "create_return_vc", "endpoint": "POST /api/v1/vc/create-return", "description": "创建退货执行单", "params": ["vc.target_vc_id", "vc.return_direction", "vc.return_items"]},
        {"name": "create_logistics_plan", "endpoint": "POST /api/v1/logistics/create-plan", "description": "创建物流发货计划", "params": ["vc_id", "orders"]},
        {"name": "confirm_inbound", "endpoint": "POST /api/v1/logistics/confirm-inbound", "description": "确认入库", "params": ["log_id", "sn_list"]},
        {"name": "create_cashflow", "endpoint": "POST /api/v1/finance/create-cashflow", "description": "录入资金流水", "params": ["vc_id", "type", "amount", "transaction_date"]},
        {"name": "create_supply_chain", "endpoint": "POST /api/v1/supply-chain/create", "description": "创建供应链协议", "params": ["sc.supplier_id", "sc.type", "sc.items"]},
        {"name": "get_system_status", "endpoint": "GET /api/v1/system/status", "description": "获取系统状态看板（待办、预警）", "params": []},
        {"name": "list_businesses", "endpoint": "GET /api/v1/business/list", "description": "查询业务列表", "params": ["customer_id?", "status?"]},
        {"name": "get_vc_detail", "endpoint": "GET /api/v1/vc/{id}", "description": "查询虚拟合同详情（含物流、资金流、状态时间线）", "params": ["id"]},
        {"name": "get_cashflow_progress", "endpoint": "GET /api/v1/query/cashflow-progress", "description": "查询VC资金流进度", "params": ["vc_id"]},
        {"name": "subscribe_events", "endpoint": "GET /api/v1/events/stream", "description": "订阅实时系统事件(SSE)", "params": []},
    ]
    return {"success": True, "data": {"tools": tools, "openapi_url": "/openapi.json", "docs_url": "/docs"}}
