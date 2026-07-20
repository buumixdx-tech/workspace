from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Logistics, ExpressOrder, VirtualContract, SystemEvent, SKU, Point
from logic.constants import LogisticsStatus, TimeRuleRelatedType, SystemEventType, SystemAggregateType, VCStatus, VCType
from logic.time_rules import RuleManager
from logic.inventory import inventory_module  # noqa: F401 - inventory_module is in logic/inventory.py (legacy file)
from logic.state_machine import logistics_state_machine
from logic.finance import finance_module
from logic.events.dispatcher import emit_event
from .schemas import CreateLogisticsPlanSchema, ConfirmInboundSchema, UpdateExpressOrderSchema, ExpressOrderStatusSchema
from logic.base import ActionResult
from logic.audit_engine import audit_context, set_audit_event_id
from datetime import datetime, date
import orjson

VC_STATUS_BLOCKED_FOR_LOGISTICS = [VCStatus.FINISH, VCStatus.TERMINATED, VCStatus.CANCELLED]

def create_logistics_plan_action(session: Session, payload: CreateLogisticsPlanSchema) -> ActionResult:
    """创建物流发货计划 Action"""
    try:
        with audit_context("create_logistics_plan_action"):
            vc = session.query(VirtualContract).get(payload.vc_id)
            if not vc:
                return ActionResult(success=False, error="未找到虚拟合同")

            if vc.status in VC_STATUS_BLOCKED_FOR_LOGISTICS:
                return ActionResult(success=False, error=f"该合同状态为【{vc.status}】，不允许新建物流")

            if payload.orders:
                for order_data in payload.orders:
                    tracking = order_data.get("tracking_number", "").strip()
                    if not tracking:
                        return ActionResult(success=False, error="快递单号不能为空")
                    addr = order_data.get("address_info")
                    if not addr:
                        return ActionResult(success=False, error="地址信息不能为空")

            # 记录创建前最大的 TimeRule id（用于后续捕获 sync_from_parent 新增的 TimeRule）
            from models import TimeRule
            max_rule_id_before = session.query(func.max(TimeRule.id)).scalar() or 0

            # 建立 SKU 和 Point 的 id→name 映射，用于补全 items 和 address_info
            vc_elements = (vc.elements or {}).get("items", []) if isinstance(vc.elements, dict) else []
            sku_ids = list(set(e.get("sku_id") for e in vc_elements if e.get("sku_id")))
            point_ids = list(set(
                [e.get("shipping_point_id") for e in vc_elements if e.get("shipping_point_id")] +
                [e.get("receiving_point_id") for e in vc_elements if e.get("receiving_point_id")]
            ))
            sku_map = {s.id: s.name for s in session.query(SKU).filter(SKU.id.in_(sku_ids)).all()} if sku_ids else {}
            point_map = {p.id: p.name for p in session.query(Point).filter(Point.id.in_(point_ids)).all()} if point_ids else {}

            def normalize_addr(addr):
                """确保 address_info 是 dict 而非字符串，解析双重编码"""
                if isinstance(addr, str):
                    try:
                        return orjson.loads(addr)
                    except Exception:
                        return {"raw": addr}
                return addr if isinstance(addr, dict) else {}

            def enrich_items(items_list):
                """补全 items 中的 sku_name"""
                result = []
                for it in items_list:
                    item = dict(it) if isinstance(it, dict) else {}
                    if "sku_name" not in item or not item["sku_name"]:
                        sku_id = item.get("sku_id")
                        item["sku_name"] = sku_map.get(sku_id, f"SKU-{sku_id}") if sku_id else "未知"
                    result.append(item)
                return result

            log = session.query(Logistics).filter(Logistics.virtual_contract_id == vc.id).first()
            log_is_new = False
            biz_date = payload.created_date or date.today()
            if not log:
                log = Logistics(
                    virtual_contract_id=vc.id,
                    status=LogisticsStatus.PENDING,
                )
                session.add(log)
                session.flush()
                log_is_new = True
                RuleManager(session).sync_from_parent(TimeRuleRelatedType.LOGISTICS, log.id)

            for order_data in payload.orders:
                raw_addr = order_data.get("address_info", {})
                order_addr = normalize_addr(raw_addr)
                if order_addr.get("发货点位名称") in ("", None) and order_addr.get("发货点位Id"):
                    order_addr["发货点位名称"] = point_map.get(order_addr["发货点位Id"], f"点位-{order_addr['发货点位Id']}")
                if order_addr.get("收货点位名称") in ("", None) and order_addr.get("收货点位Id"):
                    order_addr["收货点位名称"] = point_map.get(order_addr["收货点位Id"], f"点位-{order_addr['收货点位Id']}")

                order_items = order_data.get("items", [])

                eo = ExpressOrder(
                    logistics_id=log.id,
                    tracking_number=order_data["tracking_number"],
                    items=enrich_items(order_items),
                    address_info=order_addr,
                    status=LogisticsStatus.PENDING,
                )
                session.add(eo)
                session.flush()
                evt = emit_event(session, SystemEventType.EXPRESS_ORDER_CREATED, SystemAggregateType.EXPRESS_ORDER, 0, {"placeholder": True})
                evt.aggregate_id = eo.id
                evt.payload = {
                    "tracking_number": order_data["tracking_number"],
                    "logistics_id": log.id,
                    "vc_id": vc.id,
                    "items_count": len(order_items)
                }

            evt = emit_event(session, SystemEventType.LOGISTICS_PLAN_CREATED, SystemAggregateType.LOGISTICS, 0, {"placeholder": True})
            set_audit_event_id(evt.id)
            session.flush()

            evt.aggregate_id = log.id
            evt.payload = {
                "vc_id": vc.id,
                "order_count": len(payload.orders),
                "transaction_date": str(biz_date)
            }

            session.commit()
            return ActionResult(success=True, data={"log_id": log.id}, message="物流计划已下达")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def confirm_inbound_action(session: Session, payload: ConfirmInboundSchema) -> ActionResult:
    """确认收货/入库 Action"""
    try:
        with audit_context("confirm_inbound_action"):
            from models import EquipmentInventory, MaterialInventory, SKU

            log = session.query(Logistics).get(payload.log_id)
            if not log: return ActionResult(success=False, error="未找到物流记录")

            # 获取 VC 类型，设备/库存采购必须提供 SN，物料类允许为空
            vc = session.query(VirtualContract).get(log.virtual_contract_id)
            requires_sn = vc and vc.type in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT]

            if requires_sn and not payload.sn_list:
                return ActionResult(success=False, error="序列号列表不能为空")

            if payload.sn_list and len(payload.sn_list) != len(set(payload.sn_list)):
                return ActionResult(success=False, error="序列号列表中包含重复项")

            # 物料采购入库：batch_items 必填
            if vc and vc.type == VCType.MATERIAL_PROCUREMENT:
                if not payload.batch_items:
                    return ActionResult(success=False, error="物料采购入库必须提供批次信息（batch_items）")
                if log.status == LogisticsStatus.FINISH:
                    return ActionResult(success=False, error="该物流单已完成入库，请勿重复操作")

            if log.status == LogisticsStatus.FINISH:
                return ActionResult(success=False, error="该物流单已完成入库，请勿重复操作")

            existing_sns = []
            if payload.sn_list and vc and vc.type in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT]:
                existing_sns = session.query(EquipmentInventory.sn).filter(EquipmentInventory.sn.in_(payload.sn_list)).all()
            if existing_sns:
                conflict_sns = [s[0] for s in existing_sns]
                return ActionResult(success=False, error=f"SN 冲突：以下序列号已存在于系统库存中 {conflict_sns}")

            session.begin_nested()

            old_status = log.status
            log.status = LogisticsStatus.FINISH
            biz_date = payload.created_date or date.today()

            evt = emit_event(session, SystemEventType.LOGISTICS_STATUS_CHANGED, SystemAggregateType.LOGISTICS, 0, {"placeholder": True})
            set_audit_event_id(evt.id)

            inventory_module(log.id, equipment_sn_json=payload.sn_list, batch_items=payload.batch_items, session=session)
            logistics_state_machine(log.id, session=session, tx_date=biz_date)
            finance_module(logistics_id=log.id, session=session)

            evt.aggregate_id = log.id
            evt.payload = {
                "from": old_status,
                "to": LogisticsStatus.FINISH,
                "vc_id": log.virtual_contract_id,
                "sn_count": len(payload.sn_list) if payload.sn_list else 0,
                "transaction_date": str(biz_date)
            }

            session.commit()
            return ActionResult(success=True, message="收货入库及财务同步完成")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def update_express_order_action(session: Session, payload: UpdateExpressOrderSchema) -> ActionResult:
    """更新快递单信息 Action"""
    try:
        with audit_context("update_express_order_action"):
            o = session.query(ExpressOrder).get(payload.order_id)
            if not o:
                return ActionResult(success=False, error="未找到快递单")

            session.begin_nested()

            o.tracking_number = payload.tracking_number
            o.address_info = payload.address_info

            evt = emit_event(session, SystemEventType.EXPRESS_ORDER_UPDATED, SystemAggregateType.EXPRESS_ORDER, 0, {"placeholder": True})
            set_audit_event_id(evt.id)

            evt.aggregate_id = o.id
            evt.payload = {"tracking": payload.tracking_number}

            session.commit()
            return ActionResult(success=True, message="信息已更新")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def update_express_order_status_action(session: Session, payload: ExpressOrderStatusSchema) -> ActionResult:
    """推进快递单状态 Action"""
    try:
        with audit_context("update_express_order_status_action"):
            o = session.query(ExpressOrder).get(payload.order_id)
            if not o:
                return ActionResult(success=False, error="未找到快递单")

            log = session.query(Logistics).get(payload.logistics_id)
            vc = session.query(VirtualContract).get(log.virtual_contract_id) if log else None

            session.begin_nested()

            old_status = o.status
            o.status = payload.target_status

            tx_date = payload.created_date
            evt = emit_event(session, SystemEventType.EXPRESS_ORDER_STATUS_CHANGED, SystemAggregateType.EXPRESS_ORDER, 0, {"placeholder": True})
            set_audit_event_id(evt.id)

            logistics_state_machine(payload.logistics_id, o.id, session=session, tx_date=tx_date)

            evt.aggregate_id = o.id
            evt.payload = {"from": old_status, "to": payload.target_status, "transaction_date": str(tx_date) if tx_date else None}

            session.commit()
            return ActionResult(success=True, message=f"快递单已推进至 {payload.target_status}")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def bulk_progress_express_orders_action(session: Session, order_ids: list, target_status: str, logistics_id: int, created_date=None) -> ActionResult:
    """批量推进快递单状态 Action"""
    try:
        with audit_context("bulk_progress_express_orders_action"):
            log = session.query(Logistics).get(logistics_id)
            if not log:
                return ActionResult(success=False, error="未找到物流记录")

            # 校验：所有快递单状态必须一致
            orders = session.query(ExpressOrder).filter(ExpressOrder.id.in_(order_ids)).all()
            if not orders:
                return ActionResult(success=False, error="未找到任何快递单")
            statuses = list(set(o.status for o in orders))
            if len(statuses) != 1:
                return ActionResult(success=False, error=f"快递单状态不一致，无法批量操作。当前状态：{statuses}")
            if statuses[0] == LogisticsStatus.SIGNED:
                return ActionResult(success=False, error="快递单已签收，无法继续推进")

            session.begin_nested()

            tx_date = created_date
            evt = emit_event(session, SystemEventType.EXPRESS_ORDER_BULK_PROGRESS, SystemAggregateType.LOGISTICS, 0, {"placeholder": True})
            set_audit_event_id(evt.id)

            for oid in order_ids:
                o = session.query(ExpressOrder).get(oid)
                if o:
                    old_status = o.status
                    o.status = target_status
                    evt_eo = emit_event(session, SystemEventType.EXPRESS_ORDER_STATUS_CHANGED, SystemAggregateType.EXPRESS_ORDER, 0, {"placeholder": True})
                    evt_eo.aggregate_id = o.id
                    evt_eo.payload = {"from": old_status, "to": target_status, "transaction_date": str(tx_date) if tx_date else None}
                    logistics_state_machine(logistics_id, o.id, session=session, tx_date=tx_date)

            evt.aggregate_id = logistics_id
            evt.payload = {"count": len(order_ids), "to": target_status, "transaction_date": str(tx_date) if tx_date else None}

            session.commit()
            return ActionResult(success=True, message=f"已成功批量推进 {len(order_ids)} 个快递单")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))
