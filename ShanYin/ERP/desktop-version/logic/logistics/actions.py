from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Logistics, ExpressOrder, VirtualContract, SystemEvent
from logic.constants import LogisticsStatus, TimeRuleRelatedType, SystemEventType, SystemAggregateType, VCStatus, VCType
from logic.time_rules import RuleManager
from logic.inventory import inventory_module  # noqa: F401 - inventory_module is in logic/inventory.py (legacy file)
from logic.state_machine import logistics_state_machine
from logic.finance import finance_module
from logic.events.dispatcher import emit_event
from .schemas import CreateLogisticsPlanSchema, ConfirmInboundSchema, UpdateExpressOrderSchema, ExpressOrderStatusSchema
from logic.base import ActionResult

VC_STATUS_BLOCKED_FOR_LOGISTICS = [VCStatus.FINISH, VCStatus.TERMINATED, VCStatus.CANCELLED]

def create_logistics_plan_action(session: Session, payload: CreateLogisticsPlanSchema) -> ActionResult:
    """创建物流发货计划 Action（支持回滚）"""
    try:
        from logic.transactions import serialize_model, serialize_objs

        if not payload.orders:
            return ActionResult(success=False, error="订单列表不能为空")

        vc = session.query(VirtualContract).get(payload.vc_id)
        if not vc:
            return ActionResult(success=False, error="未找到虚拟合同")

        if vc.status in VC_STATUS_BLOCKED_FOR_LOGISTICS:
            return ActionResult(success=False, error=f"该合同状态为【{vc.status}】，不允许新建物流")

        for order_data in payload.orders:
            tracking = order_data.get("tracking_number", "").strip()
            if not tracking:
                return ActionResult(success=False, error="快递单号不能为空")

            addr = order_data.get("address_info", {})
            if not addr:
                return ActionResult(success=False, error="地址信息不能为空")

        # 记录创建前最大的 TimeRule id（用于后续捕获 sync_from_parent 新增的 TimeRule）
        from models import TimeRule
        max_rule_id_before = session.query(func.max(TimeRule.id)).scalar() or 0

        log = session.query(Logistics).filter(Logistics.virtual_contract_id == vc.id).first()
        log_is_new = False
        if not log:
            log = Logistics(virtual_contract_id=vc.id, status=LogisticsStatus.PENDING)
            session.add(log)
            session.flush()
            log_is_new = True
            RuleManager(session).sync_from_parent(TimeRuleRelatedType.LOGISTICS, log.id)

        # 在 flush 之前：记录所有新增对象
        new_objs_before_flush = list(session.new)

        for order_data in payload.orders:
            eo = ExpressOrder(
                logistics_id=log.id,
                tracking_number=order_data["tracking_number"],
                items=order_data["items"],
                address_info=order_data["address_info"],
                status=LogisticsStatus.PENDING
            )
            session.add(eo)

        system_event = emit_event(session, SystemEventType.LOGISTICS_PLAN_CREATED, SystemAggregateType.LOGISTICS, log.id, {
            "vc_id": vc.id,
            "order_count": len(payload.orders)
        })
        session.flush()

        # 捕获所有新增的 TimeRule（sync_from_parent 创建的）
        new_rules = session.query(TimeRule).filter(TimeRule.id > max_rule_id_before).all()

        # snapshot_after：所有新增记录
        snapshot_records = serialize_objs(new_objs_before_flush)
        # ExpressOrders 在 new_objs_before_flush 中，logistics 在 session.new 中（如果新创建）
        if log_is_new:
            snapshot_records.append({"class": "Logistics", "id": log.id, "data": serialize_model(log)})
        for rule in new_rules:
            snapshot_records.append({"class": "TimeRule", "id": rule.id, "data": serialize_model(rule)})
        snapshot_records.append({"class": "SystemEvent", "id": system_event.id, "data": serialize_model(system_event)})
        snapshot_after = {"records": snapshot_records}

        from logic.transactions import create_operation_record
        involved_ids = [o.id for o in session.new if o.__class__.__name__ == "ExpressOrder"]
        if log_is_new:
            involved_ids.append(log.id)
        involved_ids += [r.id for r in new_rules]

        tx_id = create_operation_record(
            session,
            action_name="create_logistics_plan_action",
            ref_type="Logistics",
            ref_id=log.id,
            ref_vc_id=vc.id,
            snapshot_before={},
            snapshot_after=snapshot_after,
            involved_ids=involved_ids,
        )

        session.commit()
        return ActionResult(success=True, data={"log_id": log.id}, message="物流计划已下达")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def confirm_inbound_action(session: Session, payload: ConfirmInboundSchema) -> ActionResult:
    """确认收货/入库 Action（支持回滚）"""
    try:
        from logic.transactions import serialize_model, serialize_objs
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

        # ============ snapshot_before：查询所有可能被修改的现有记录 ============
        snapshot_before = {"records": []}

        # Logistics 旧值
        snapshot_before["records"].append({"class": "Logistics", "id": log.id, "data": serialize_model(log)})

        # VirtualContract 旧值
        if vc:
            snapshot_before["records"].append({"class": "VirtualContract", "id": vc.id, "data": serialize_model(vc)})

        # EquipmentInventory 旧值（按 SN 查询，RETURN 场景）
        if payload.sn_list and vc and vc.type == VCType.RETURN:
            existing_eq = session.query(EquipmentInventory).filter(EquipmentInventory.sn.in_(payload.sn_list)).all()
            for eq in existing_eq:
                snapshot_before["records"].append({"class": "EquipmentInventory", "id": eq.id, "data": serialize_model(eq)})

        # MaterialInventory 旧值（MATERIAL 类）
        if vc and vc.type == VCType.MATERIAL_SUPPLY:
            # 查找被减的 MaterialInventory
            from logic.services import get_logistics_finance_context
            ctx = get_logistics_finance_context(session, payload.log_id)
            if ctx:
                for item in (vc.elements or {}).get("items", []):
                    sku_id = item.get("sku_id")
                    if sku_id:
                        mi = session.query(MaterialInventory).filter(MaterialInventory.sku_id == sku_id).first()
                        if mi:
                            snapshot_before["records"].append({"class": "MaterialInventory", "id": mi.id, "data": serialize_model(mi)})

        # MaterialInventory 旧值（MATERIAL_PROCUREMENT 批次行）
        if vc and vc.type == VCType.MATERIAL_PROCUREMENT and payload.batch_items:
            affected_skus = {bi.sku_id for bi in payload.batch_items}
            for sid in affected_skus:
                rows = session.query(MaterialInventory).filter(
                    MaterialInventory.sku_id == sid,
                    MaterialInventory.point_id.in_({bi.receiving_point_id for bi in payload.batch_items if bi.sku_id == sid})
                ).all()
                for row in rows:
                    snapshot_before["records"].append({"class": "MaterialInventory", "id": row.id, "data": serialize_model(row)})

        # SKU 旧值（MATERIAL_PROCUREMENT 价格更新）
        if vc and vc.type == VCType.MATERIAL_PROCUREMENT:
            for item in (vc.elements or {}).get("items", []):
                sku_id = item.get("sku_id")
                if sku_id:
                    sku = session.query(SKU).get(sku_id)
                    if sku:
                        snapshot_before["records"].append({"class": "SKU", "id": sku.id, "data": serialize_model(sku)})

        # 原采购单旧值（RETURN 场景）
        if vc and vc.type == VCType.RETURN and vc.related_vc_id:
            orig_vc = session.query(VirtualContract).get(vc.related_vc_id)
            if orig_vc:
                snapshot_before["records"].append({"class": "VirtualContract", "id": orig_vc.id, "data": serialize_model(orig_vc)})

        # ============ 执行阶段 ============
        session.begin_nested()

        old_status = log.status
        log.status = LogisticsStatus.FINISH

        inventory_module(log.id, equipment_sn_json=payload.sn_list, batch_items=payload.batch_items, session=session)
        logistics_state_machine(log.id, session=session)
        finance_module(logistics_id=log.id, session=session)

        # 记录当前最大 event id（用于捕获后续 emit_event 创建的事件）
        max_event_id_before = session.query(func.max(SystemEvent.id)).scalar() or 0

        if old_status != LogisticsStatus.FINISH:
            emit_event(session, SystemEventType.LOGISTICS_STATUS_CHANGED, SystemAggregateType.LOGISTICS, log.id, {
                "from": old_status,
                "to": LogisticsStatus.FINISH,
                "vc_id": log.virtual_contract_id,
                "sn_count": len(payload.sn_list) if payload.sn_list else 0
            })

        session.flush()

        # ============ snapshot_after：重新查询所有被修改的记录 ============
        log_ref = session.query(Logistics).get(payload.log_id)
        vc_ref = session.query(VirtualContract).get(log_ref.virtual_contract_id) if log_ref else None

        from logic.transactions import serialize_model as _sm
        snapshot_after_records = []

        # Logistics 和 VirtualContract（重新查询）
        if log_ref:
            snapshot_after_records.append({"class": "Logistics", "id": log_ref.id, "data": _sm(log_ref)})
        if vc_ref:
            snapshot_after_records.append({"class": "VirtualContract", "id": vc_ref.id, "data": _sm(vc_ref)})

        # 新创建的 EquipmentInventory（EQUIPMENT_PROCUREMENT 场景）
        if payload.sn_list and vc_ref and vc_ref.type in [VCType.EQUIPMENT_PROCUREMENT, VCType.STOCK_PROCUREMENT]:
            new_eqs = session.query(EquipmentInventory).filter(EquipmentInventory.virtual_contract_id == vc_ref.id).all()
            for eq in new_eqs:
                snapshot_after_records.append({"class": "EquipmentInventory", "id": eq.id, "data": _sm(eq)})

        # RETURN 场景 EquipmentInventory
        if vc and vc.type == VCType.RETURN and payload.sn_list:
            returned_eqs = session.query(EquipmentInventory).filter(EquipmentInventory.sn.in_(payload.sn_list)).all()
            for eq in returned_eqs:
                snapshot_after_records.append({"class": "EquipmentInventory", "id": eq.id, "data": _sm(eq)})

        # RETURN 原采购单（可能被 deposit_module 更新）
        if vc and vc.type == VCType.RETURN and vc.related_vc_id:
            orig_vc_ref = session.query(VirtualContract).get(vc.related_vc_id)
            if orig_vc_ref:
                snapshot_after_records.append({"class": "VirtualContract", "id": orig_vc_ref.id, "data": _sm(orig_vc_ref)})

        # MaterialInventory 批次行（MATERIAL_PROCUREMENT 新批次）
        if vc_ref and vc_ref.type == VCType.MATERIAL_PROCUREMENT and payload.batch_items:
            new_mi_rows = session.query(MaterialInventory).filter(
                MaterialInventory.latest_purchase_vc_id == vc_ref.id
            ).all()
            for row in new_mi_rows:
                snapshot_after_records.append({"class": "MaterialInventory", "id": row.id, "data": _sm(row)})

        # FinancialJournal 和 CashFlowLedger（finance_module 创建）
        from models import FinancialJournal
        fj_records = session.query(FinancialJournal).filter(
            FinancialJournal.ref_type == "Logistics",
            FinancialJournal.ref_id == payload.log_id
        ).all()
        for fj in fj_records:
            snapshot_after_records.append({"class": "FinancialJournal", "id": fj.id, "data": _sm(fj)})
            if fj.cash_flow_record:
                snapshot_after_records.append({"class": "CashFlowLedger", "id": fj.cash_flow_record.id, "data": _sm(fj.cash_flow_record)})

        # SystemEvent（emit_event 创建的）
        new_events = session.query(SystemEvent).filter(SystemEvent.id > max_event_id_before).all()
        for ev in new_events:
            snapshot_after_records.append({"class": "SystemEvent", "id": ev.id, "data": _sm(ev)})

        # JSON 文件
        import os, json as _json
        from logic.finance.engine import VOUCHER_DIR
        snapshot_files = []
        voucher_path = os.path.join(VOUCHER_DIR, f"Logistics_{payload.log_id}.json")
        if os.path.exists(voucher_path):
            with open(voucher_path, "r", encoding="utf-8") as f:
                snapshot_files.append({"path": voucher_path, "content": _json.load(f)})

        snapshot_after = {"records": snapshot_after_records, "files": snapshot_files}

        from logic.transactions import create_operation_record
        involved_ids = [log.id]
        if vc_ref:
            involved_ids.append(vc_ref.id)
        if vc and vc.type == VCType.RETURN and vc.related_vc_id:
            involved_ids.append(vc.related_vc_id)

        tx_id = create_operation_record(
            session,
            action_name="confirm_inbound_action",
            ref_type="Logistics",
            ref_id=log.id,
            ref_vc_id=vc.id if vc else None,
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            involved_ids=involved_ids,
        )

        session.commit()
        return ActionResult(success=True, message="收货入库及财务同步完成")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def update_express_order_action(session: Session, payload: UpdateExpressOrderSchema) -> ActionResult:
    """更新快递单信息 Action（支持回滚）"""
    try:
        o = session.query(ExpressOrder).get(payload.order_id)
        if not o:
            return ActionResult(success=False, error="未找到快递单")

        from logic.transactions import serialize_model
        snapshot_before = {"records": [{"class": "ExpressOrder", "id": o.id, "data": serialize_model(o)}]}

        session.begin_nested()

        o.tracking_number = payload.tracking_number
        o.address_info = payload.address_info

        system_event = emit_event(session, SystemEventType.EXPRESS_ORDER_UPDATED, SystemAggregateType.EXPRESS_ORDER, o.id, {"tracking": o.tracking_number})

        from logic.transactions import serialize_model as _sm
        snapshot_after = {"records": [
            {"class": "ExpressOrder", "id": o.id, "data": _sm(o)},
            {"class": "SystemEvent", "id": system_event.id, "data": _sm(system_event)},
        ]}

        from logic.transactions import create_operation_record
        tx_id = create_operation_record(
            session,
            action_name="update_express_order_action",
            ref_type="ExpressOrder",
            ref_id=o.id,
            snapshot_before=snapshot_before,
            involved_ids=[o.id],
        )

        session.commit()
        return ActionResult(success=True, message="信息已更新")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def update_express_order_status_action(session: Session, payload: ExpressOrderStatusSchema) -> ActionResult:
    """推进快递单状态 Action（支持回滚）"""
    try:
        o = session.query(ExpressOrder).get(payload.order_id)
        if not o:
            return ActionResult(success=False, error="未找到快递单")

        log = session.query(Logistics).get(payload.logistics_id)
        vc = session.query(VirtualContract).get(log.virtual_contract_id) if log else None

        from logic.transactions import serialize_model
        snapshot_before = {"records": []}
        snapshot_before["records"].append({"class": "ExpressOrder", "id": o.id, "data": serialize_model(o)})
        if log:
            snapshot_before["records"].append({"class": "Logistics", "id": log.id, "data": serialize_model(log)})
        if vc:
            snapshot_before["records"].append({"class": "VirtualContract", "id": vc.id, "data": serialize_model(vc)})

        session.begin_nested()

        old_status = o.status
        o.status = payload.target_status

        # logistics_state_machine 内部会 emit_event + flush，内部 flush 会把 event 从 session.new 移除
        # 所以先记录当前 max event id，确定后续新增 event 的范围
        from sqlalchemy import func
        max_event_id_before = session.query(func.max(SystemEvent.id)).scalar() or 0

        logistics_state_machine(payload.logistics_id, o.id, session=session)

        event2 = emit_event(session, SystemEventType.EXPRESS_ORDER_STATUS_CHANGED, SystemAggregateType.EXPRESS_ORDER, o.id, {"from": old_status, "to": payload.target_status})

        # Re-query 所有被修改的记录（状态机可能改了 Logistics 和 VC）
        log_ref = session.query(Logistics).get(payload.logistics_id)
        vc_ref = session.query(VirtualContract).get(log_ref.virtual_contract_id) if log_ref else None
        o_ref = session.query(ExpressOrder).get(o.id)

        # 查出本次 action 新增的所有 SystemEvent
        from logic.transactions import serialize_model as _sm
        new_events = session.query(SystemEvent).filter(SystemEvent.id > max_event_id_before).all()

        snapshot_after_records = [_sm(o_ref)]
        if log_ref:
            snapshot_after_records.append(_sm(log_ref))
        if vc_ref:
            snapshot_after_records.append(_sm(vc_ref))
        for ev in new_events:
            snapshot_after_records.append({"class": "SystemEvent", "id": ev.id, "data": _sm(ev)})
        snapshot_after = {"records": snapshot_after_records}

        from logic.transactions import create_operation_record
        involved_ids = [o.id]
        if log:
            involved_ids.append(log.id)
        if vc:
            involved_ids.append(vc.id)
        tx_id = create_operation_record(
            session,
            action_name="update_express_order_status_action",
            ref_type="ExpressOrder",
            ref_id=o.id,
            snapshot_before=snapshot_before,
            involved_ids=involved_ids,
        )

        session.commit()
        return ActionResult(success=True, message=f"快递单已推进至 {payload.target_status}")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))

def bulk_progress_express_orders_action(session: Session, order_ids: list, target_status: str, logistics_id: int) -> ActionResult:
    """批量推进快递单状态 Action（支持回滚）"""
    try:
        from logic.transactions import serialize_model

        # snapshot_before：所有 ExpressOrder + Logistics + VC 旧值
        snapshot_before = {"records": []}
        for oid in order_ids:
            o = session.query(ExpressOrder).get(oid)
            if o:
                snapshot_before["records"].append({"class": "ExpressOrder", "id": o.id, "data": serialize_model(o)})

        log = session.query(Logistics).get(logistics_id)
        if log:
            snapshot_before["records"].append({"class": "Logistics", "id": log.id, "data": serialize_model(log)})
            vc_for_snapshot = session.query(VirtualContract).get(log.virtual_contract_id)
            if vc_for_snapshot:
                snapshot_before["records"].append({"class": "VirtualContract", "id": vc_for_snapshot.id, "data": serialize_model(vc_for_snapshot)})

        session.begin_nested()

        for oid in order_ids:
            o = session.query(ExpressOrder).get(oid)
            if o:
                o.status = target_status
                logistics_state_machine(logistics_id, o.id, session=session)

        # 记录当前最大 event id，用于后续捕获新增 events
        max_event_id_before = session.query(func.max(SystemEvent.id)).scalar() or 0

        emit_event(session, SystemEventType.EXPRESS_ORDER_BULK_PROGRESS, SystemAggregateType.LOGISTICS, logistics_id, {"count": len(order_ids), "to": target_status})
        session.flush()

        # Re-query all modified records after state machine changes
        log_ref = session.query(Logistics).get(logistics_id)
        vc_ref = session.query(VirtualContract).get(log_ref.virtual_contract_id) if log_ref else None

        from logic.transactions import serialize_model as _sm
        new_events = session.query(SystemEvent).filter(SystemEvent.id > max_event_id_before).all()

        snapshot_after_records = []
        for oid in order_ids:
            o_ref = session.query(ExpressOrder).get(oid)
            if o_ref:
                snapshot_after_records.append({"class": "ExpressOrder", "id": o_ref.id, "data": _sm(o_ref)})
        if log_ref:
            snapshot_after_records.append({"class": "Logistics", "id": log_ref.id, "data": _sm(log_ref)})
        if vc_ref:
            snapshot_after_records.append({"class": "VirtualContract", "id": vc_ref.id, "data": _sm(vc_ref)})
        for ev in new_events:
            snapshot_after_records.append({"class": "SystemEvent", "id": ev.id, "data": _sm(ev)})
        snapshot_after = {"records": snapshot_after_records}

        from logic.transactions import create_operation_record
        involved_ids = order_ids[:]
        if log:
            involved_ids.append(log.id)
        if vc_ref:
            involved_ids.append(vc_ref.id)
        tx_id = create_operation_record(
            session,
            action_name="bulk_progress_express_orders_action",
            ref_type="Logistics",
            ref_id=logistics_id,
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            involved_ids=involved_ids,
        )

        session.commit()
        return ActionResult(success=True, message=f"已成功批量推进 {len(order_ids)} 个快递单")
    except Exception as e:
        session.rollback()
        return ActionResult(success=False, error=str(e))
